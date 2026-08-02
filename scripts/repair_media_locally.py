"""Run the describe-and-brand pass on this machine instead of the server.

Why this exists: branding a clip needs ~310MB of resident memory for ffmpeg,
and the Render starter instance has 512MB total with a web server already in
it. Encodes there are serialised and still leave almost no headroom, so a
250-clip library takes hours and stalls whenever anything else runs.

This is the same code — services.bulk_ingest.finish_pending_media, against the
same database and the same Cloudinary account — driven from a laptop with
cores to spare. Results land in exactly the same place; the dashboard count
drops as it goes.

    python scripts/repair_media_locally.py "Billionaire Goal777"
    python scripts/repair_media_locally.py <workspace-id> --encodes 4

Safe to stop with Ctrl-C and re-run: work already done is detected by the
"_branded" marker in the URL and by the caption being present, so a second run
picks up where the first left off rather than redoing it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import select


def _pending(rows) -> list:
    """Assets still missing a description or a watermark.

    Mirrors the dashboard's own count so the two agree: only postable video
    and images, needing either a caption or the branded marker.
    """
    from services.media_rotation import _is_postable

    out = []
    for m in rows:
        if not _is_postable(m):
            continue
        needs_caption = not (m.caption or m.prompt)
        needs_brand = (m.mimeType or "").startswith("video/") and \
            "_branded" not in (m.url or "")
        if needs_caption or needs_brand:
            out.append(m)
    return out


async def _brand_only(workspace_id, profile, args, started) -> int:
    """Watermark every clip that has not been branded, and nothing else.

    Talks to brand_video_at_url directly rather than going through
    finish_pending_media, so no encode slot is ever held by a vision call.
    """
    from database import AsyncSessionLocal, Media
    from services.video_outro import brand_video_at_url

    slots = asyncio.Semaphore(args.encodes)
    done = 0
    lock = asyncio.Lock()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Media).where(Media.businessProfileId == workspace_id)
        )).scalars().all()
        targets = [
            m.id for m in rows
            if (m.mimeType or "").startswith("video/")
            and m.url and "_branded" not in m.url and m.isActive
        ]
    total = len(targets)
    print(f"  branding {total} clips, {args.encodes} at a time\n", flush=True)

    async def _one(media_id: str):
        nonlocal done
        async with slots:
            try:
                async with AsyncSessionLocal() as session:
                    media = await session.get(Media, media_id)
                    if not media or not media.url or "_branded" in media.url:
                        return
                    url = media.url

                probe: dict = {}
                branded = await brand_video_at_url(
                    url, profile, workspace_id, media_id, probe_out=probe
                )
                if branded and branded != url:
                    async with AsyncSessionLocal() as s2:
                        row = await s2.get(Media, media_id)
                        if row:
                            row.url = branded
                            if probe.get("has_audio") is not None:
                                row.hasAudio = probe["has_audio"]
                            await s2.commit()
            except Exception as e:
                logger.warning(f"Branding failed for {media_id}: {e}")
            finally:
                async with lock:
                    done += 1
                    if done % 5 == 0 or done == total:
                        el = (time.time() - started) / 60
                        rate = done / el if el else 0
                        left = (total - done) / rate if rate else 0
                        print(f"  [{done}/{total}] {el:.1f} min, {rate:.1f}/min, "
                              f"about {left:.0f} min left", flush=True)

    await asyncio.gather(*(_one(mid) for mid in targets))
    return done


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", help="business name or workspace id")
    ap.add_argument("--batch", type=int, default=12,
                    help="assets per batch; the pending list is re-read between batches")
    ap.add_argument("--encodes", type=int, default=3,
                    help="concurrent ffmpeg encodes. Each needs ~310MB and one core")
    ap.add_argument("--describes", type=int, default=3,
                    help="concurrent vision calls. Free models rate-limit above ~4")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=("brand", "describe"), default=None,
                    help="run one job instead of both")
    args = ap.parse_args()

    from database import AsyncSessionLocal, BusinessProfile, Media, init_db

    await init_db()

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, args.workspace)
        if profile is None:
            profile = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == args.workspace)
            )).scalars().first()
        if profile is None:
            print(f"No workspace matching {args.workspace!r}")
            return 1
        workspace_id, name = profile.id, profile.name

    # Local machine, local rules. The server serialises encodes because it has
    # half a gigabyte and a web server to keep answering; here there is neither
    # constraint, and ffmpeg is pinned to one thread each so N encodes use N
    # cores rather than fighting over all of them.
    import services.bulk_ingest as bulk

    bulk._encode_slot = asyncio.Semaphore(args.encodes)
    bulk.MAX_CONCURRENT = args.describes

    from services.bulk_ingest import finish_pending_media

    started = time.time()
    done = 0
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Media).where(Media.businessProfileId == workspace_id)
        )).scalars().all()
        todo = _pending(rows)

    print(f"\n{name}  ({workspace_id})")
    print(f"  {len(rows)} assets, {len(todo)} still need work")
    print(f"  {sum(1 for m in todo if not (m.caption or m.prompt))} without a description")
    print(f"  {sum(1 for m in todo if not m.url or '_branded' not in m.url)} without a watermark")
    print(f"  {args.encodes} concurrent encodes, {args.describes} concurrent descriptions\n")
    if args.dry_run or not todo:
        return 0

    if args.only == "brand":
        # Branding on its own, because coupling it to captioning starves it.
        # finish_pending_media describes an asset and then brands it, both
        # under one pool of workers -- so when the free vision models take
        # their 120-second timeout, every worker sits waiting on the network
        # and the encoder goes completely idle. Measured: zero ffmpeg
        # processes for a solid minute while eight slots blocked on 504s.
        #
        # The two jobs are independent, so run them apart: this keeps every
        # encode slot busy, and descriptions are a separate pass afterwards.
        done = await _brand_only(workspace_id, profile, args, started)
        print(f"\nFinished {done} clips in {(time.time()-started)/60:.1f} minutes")
        return 0

    total = len(todo)
    while True:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                select(Media).where(Media.businessProfileId == workspace_id)
            )).scalars().all()
            batch = [m.id for m in _pending(rows)][: args.batch]
            if args.only == "describe":
                batch = [m.id for m in _pending(rows)
                         if not (m.caption or m.prompt)][: args.batch]
        if not batch:
            break

        await finish_pending_media(workspace_id, batch, profile)
        done += len(batch)

        elapsed = time.time() - started
        rate = done / elapsed if elapsed else 0
        left = max(total - done, 0)
        eta = left / rate / 60 if rate else 0
        print(f"  [{done}/{total}] {elapsed/60:.1f} min elapsed, "
              f"{rate*60:.1f}/min, about {eta:.0f} min left", flush=True)

    print(f"\nFinished {done} assets in {(time.time()-started)/60:.1f} minutes")
    return 0


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="WARNING",
               format="<level>{level: <8}</level> {message}")
    raise SystemExit(asyncio.run(main()))
