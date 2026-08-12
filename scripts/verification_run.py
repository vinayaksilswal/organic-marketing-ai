"""Publish N real posts per business and report exactly what each platform did.

This PUBLISHES to live public accounts. It calls context_aggregation_task, the
same function the scheduler calls, so what it exercises is the real path --
rotation, folder expansion, caption generation, the policy gate, image
geometry, and both publishers.

Deliberately bypasses the interval gate, which lives in the scheduler rather
than in the task, because the point is to verify now rather than over the next
twelve hours.

Does NOT bypass the pause flag by accident: paused workspaces are skipped
unless named explicitly with --include-paused. Calling the task directly would
otherwise post to an account the user has deliberately silenced.
"""

import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialConnection, SocialPost,
    init_db, utc_now,
)


async def latest_post(workspace_id: str):
    async with AsyncSessionLocal() as session:
        return (await session.execute(
            select(SocialPost)
            .where(SocialPost.businessProfileId == workspace_id)
            .order_by(desc(SocialPost.createdAt))
            .limit(1)
        )).scalars().first()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3, help="posts per business")
    ap.add_argument("--include-paused", action="store_true")
    ap.add_argument("--only", help="run a single business by name")
    ap.add_argument("--exclude", action="append", default=[],
                    help="skip a business by name; repeatable")
    args = ap.parse_args()

    await init_db()
    from worker import context_aggregation_task

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(BusinessProfile, SocialConnection)
            .outerjoin(SocialConnection,
                       SocialConnection.businessProfileId == BusinessProfile.id)
            .order_by(BusinessProfile.name)
        )).all()

    targets = []
    for profile, conn in rows:
        if args.only and profile.name != args.only:
            continue
        if profile.name in args.exclude:
            print(f"SKIP  {profile.name}: excluded")
            continue
        if not conn or not conn.fbPageId:
            print(f"SKIP  {profile.name}: no social connection")
            continue
        if getattr(profile, "automationPaused", False) and not args.include_paused:
            print(f"SKIP  {profile.name}: paused (use --include-paused to override)")
            continue
        targets.append((profile.id, profile.name))

    print(f"\nPublishing {args.count} post(s) each to {len(targets)} business(es): "
          f"{', '.join(n for _, n in targets)}\n")

    tally = {"ig_ok": 0, "ig_bad": 0, "fb_ok": 0, "fb_bad": 0, "runs": 0}

    for workspace_id, name in targets:
        for attempt in range(1, args.count + 1):
            before = await latest_post(workspace_id)
            before_id = before.id if before else None

            print(f"--- {name} post {attempt}/{args.count} ---", flush=True)
            try:
                result = await context_aggregation_task({}, workspace_id)
            except Exception as e:
                print(f"    task raised {type(e).__name__}: {e}", flush=True)
                tally["runs"] += 1
                continue

            tally["runs"] += 1
            post = await latest_post(workspace_id)
            if not post or post.id == before_id:
                print(f"    no post row created — task returned {result!r}", flush=True)
                continue

            is_video = any(
                str(u).lower().endswith((".mp4", ".mov"))
                for u in (post.mediaUrls or [])
            )
            slides = len(post.mediaUrls or [])
            shape = "carousel" if slides > 1 else ("video" if is_video else "image")

            if post.igPostId:
                tally["ig_ok"] += 1
            else:
                tally["ig_bad"] += 1
            if post.fbPostId:
                tally["fb_ok"] += 1
            else:
                tally["fb_bad"] += 1

            fb = "FB ok" if post.fbPostId else "FB --"
            ig = "IG ok" if post.igPostId else "IG --"
            print(f"    {shape} ({slides} file(s))  {post.status}  {fb}  {ig}",
                  flush=True)
            if post.errorLog:
                for segment in post.errorLog.split("|"):
                    segment = segment.strip()
                    if segment:
                        print(f"      {segment[:200]}", flush=True)

            # Meta rate-limits bursts to one account; a short gap keeps the
            # run from measuring throttling rather than correctness.
            await asyncio.sleep(20)

    print("\n" + "=" * 62)
    print(f"runs: {tally['runs']}")
    print(f"Instagram: {tally['ig_ok']} ok, {tally['ig_bad']} missing")
    print(f"Facebook : {tally['fb_ok']} ok, {tally['fb_bad']} missing")


if __name__ == "__main__":
    asyncio.run(main())
