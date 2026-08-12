"""What already sells, taken from the ads that already sold it.

Two of these businesses have real revenue from Meta ads and almost none from
organic. That gap is not a mystery: the paid side knows which product converts,
which hook stops the scroll, and which format wins, and the organic side was
writing from a brand description that knows none of it.

Measured on the live ad accounts, 90 days to 12 Aug 2026:

    Lumively   "Struggling with your child's handwriting?"  Sank Magic Book
               Rs 5,846 spend -> Rs 54,591 revenue, ROAS 8.1 to 14.3
    MyCart4U   "BUY 1 GET 1 FREE"                           Japanese Massage Cream
               Rs 2,280 spend -> Rs 16,359 revenue, ROAS 6.7 to 9.4
               image creatives beat video by 3-4x on ROAS

A hook that produced a 14x return on paid traffic is the best available
evidence for what to say organically, and it cost real money to learn. Organic
is not paid -- there is no targeting, the reader did not opt in, and a hard
offer repeated every post reads as spam rather than as a sale. So this supplies
the PRODUCT, the PROBLEM and the PROOF, and lets the caption writer find its own
opening. What transfers is the angle; what does not transfer is the ad voice.

Populated per business and stored on the profile. The ads Marketing API could
fill it automatically, but that needs ads_read, which App Review has not
granted -- so it is written once from measured data and re-read on every post.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger


def normalise(raw: Any) -> List[Dict[str, str]]:
    """Coerce stored offers into the shape captions expect."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        product = str(item.get("product") or "").strip()
        if not product:
            continue
        out.append({
            "product": product[:120],
            "problem": str(item.get("problem") or "").strip()[:220],
            "proof": str(item.get("proof") or "").strip()[:220],
            "offer": str(item.get("offer") or "").strip()[:120],
            "audience": str(item.get("audience") or "").strip()[:220],
            "best_format": str(item.get("best_format") or "").strip()[:120],
        })
    return out


def to_caption_guidance(offers: Any) -> str:
    """The paragraph a caption prompt can use, or empty.

    Deliberately instructs against reusing the ad's own wording. An ad hook
    repeated verbatim on every organic post is the fastest way to make a feed
    look like a billboard, and the reader here did not ask to see an ad.
    """
    items = normalise(offers)
    if not items:
        return ""

    lines = [
        "PROVEN DEMAND — this business has real sales, and these are the "
        "products and angles that produced them with paid traffic:"
    ]
    for o in items[:3]:
        bits = [f"Product: {o['product']}"]
        if o["problem"]:
            bits.append(f"the problem it solves: {o['problem']}")
        if o["audience"]:
            bits.append(f"who buys it: {o['audience']}")
        if o["proof"]:
            bits.append(f"evidence: {o['proof']}")
        if o["offer"]:
            bits.append(f"the offer that converted: {o['offer']}")
        if o["best_format"]:
            bits.append(f"format that performed best: {o['best_format']}")
        lines.append("  - " + "; ".join(bits))

    lines.append(
        "Write about ONE of these, choosing the one the attached asset actually "
        "shows. Lead with the problem the buyer already feels, in your own "
        "words -- do not copy the advertising wording, which reads as a "
        "billboard in a feed the reader did not opt into. Name the product "
        "plainly so a reader knows what is being sold. Mention the offer only "
        "if it is genuinely running, and at most as a closing line."
    )
    return "\n".join(lines)


# Written from the ad accounts on 12 Aug 2026. Keyed by workspace name because
# that is stable and readable; the loader matches case-insensitively.
MEASURED: Dict[str, List[Dict[str, str]]] = {
    "Lumively": [
        {
            "product": "Sank Magic Book — reusable handwriting practice book for children",
            "problem": "A child's handwriting is messy and practice means endless wasted paper",
            "audience": "Parents of children aged 3 and above",
            "proof": "Best performing ad returned 14x on spend; over 100 orders to date",
            "offer": "",
            "best_format": "single image",
        }
    ],
    "MyCart4U": [
        {
            "product": "Japanese Massage Cream",
            "problem": "Tension after a long day, with no time or money for a massage",
            "audience": "Adults buying self-care products for home use",
            "proof": "Best performing ad returned 9.4x on spend; over 100 orders to date",
            "offer": "Buy 1 Get 1 Free",
            "best_format": "single image — images outperformed video by 3 to 4 times on return",
        }
    ],
}


def measured_for(profile: Any) -> List[Dict[str, str]]:
    """Any measured offers known for this business, by name."""
    name = (getattr(profile, "name", "") or "").strip().lower()
    for key, offers in MEASURED.items():
        if key.lower() == name:
            return normalise(offers)
    return []


def for_profile(profile: Any) -> List[Dict[str, str]]:
    """Offers stored on the profile, falling back to the measured table."""
    stored = normalise(getattr(profile, "provenOffers", None))
    if stored:
        return stored
    return measured_for(profile)


async def backfill(session: Any) -> int:
    """Write the measured offers onto the businesses they belong to."""
    from sqlalchemy import select

    from database import BusinessProfile

    written = 0
    profiles = (await session.execute(select(BusinessProfile))).scalars().all()
    for p in profiles:
        offers = measured_for(p)
        if not offers:
            continue
        if normalise(getattr(p, "provenOffers", None)):
            continue
        p.provenOffers = offers
        written += 1
        logger.info(f"Proven offers written for {p.name}: {offers[0]['product']}")
    if written:
        await session.commit()
    return written
