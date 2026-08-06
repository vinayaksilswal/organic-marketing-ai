"""List published posts whose captions declare adult content.

Meta's sexual solicitation policy acts on caption text alone, and App Review
includes a human looking at what an app publishes. Seventy-eight live captions
on these accounts describe the pages as adult content in plain words, which is
grounds to reject the whole app -- blocking every future customer, not only the
pages that carry them.

This only reports. Deleting published posts is irreversible and outward-facing,
and the Instagram deletion endpoint needs `instagram_manage_contents`, which
these tokens do not carry -- requesting it means another App Review, which is
the thing being unblocked. So the IDs are printed and the removal is yours.

    python scripts/list_policy_risk_posts.py
    python scripts/list_policy_risk_posts.py --workspace HollyVerse --full
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", help="limit to one business by name")
    ap.add_argument("--full", action="store_true", help="print whole captions")
    ap.add_argument("--out", default="policy-risk-posts.txt")
    args = ap.parse_args()

    from database import AsyncSessionLocal, BusinessProfile, SocialPost, init_db
    from services.caption_policy import find_violations

    await init_db()
    lines: list[str] = []

    async with AsyncSessionLocal() as session:
        profiles = {
            p.id: p.name
            for p in (await session.execute(select(BusinessProfile))).scalars().all()
        }
        posts = (await session.execute(
            select(SocialPost).order_by(SocialPost.createdAt.desc())
        )).scalars().all()

    flagged = []
    for p in posts:
        name = profiles.get(p.businessProfileId, "?")
        if args.workspace and name != args.workspace:
            continue
        violations = find_violations(p.caption or "")
        if violations:
            flagged.append((name, p, violations))

    if not flagged:
        print("No published caption contains prohibited terms.")
        return 0

    by_workspace: dict = {}
    for name, p, v in flagged:
        by_workspace.setdefault(name, []).append((p, v))

    print(f"\n{len(flagged)} published post(s) carry prohibited caption text.\n")
    print(f"{'business':22} {'posts':>6} {'on facebook':>12} {'on instagram':>13}")
    for name, items in by_workspace.items():
        print(f"{name[:22]:22} {len(items):>6} "
              f"{sum(1 for p, _ in items if p.fbPostId):>12} "
              f"{sum(1 for p, _ in items if p.igPostId):>13}")

    for name, items in by_workspace.items():
        lines.append(f"\n{'=' * 70}\n{name}  —  {len(items)} post(s)\n{'=' * 70}")
        for p, v in items:
            lines.append(f"\n[{p.createdAt:%Y-%m-%d %H:%M}]  terms: {', '.join(v)}")
            if p.fbPostId:
                lines.append(f"  facebook  {p.fbPostId}")
                lines.append(f"            https://www.facebook.com/{p.fbPostId}")
            if p.igPostId:
                lines.append(f"  instagram {p.igPostId}")
            caption = (p.caption or "").strip()
            lines.append("  caption:  " + (caption if args.full else caption[:160]))

    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nFull list with post ids written to {args.out}")
    print(
        "\nInstagram posts have to be removed in the app: deleting them through\n"
        "the API needs instagram_manage_contents, which these tokens do not have.\n"
        "Facebook posts can be deleted from the Page, or via the Graph API with\n"
        "pages_manage_posts if that permission is granted."
    )
    return 0


if __name__ == "__main__":
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    raise SystemExit(asyncio.run(main()))
