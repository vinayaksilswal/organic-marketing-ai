"""Hand-written brand profiles for the Social Page workspaces.

Every one of them carried the same generated defaults -- "Business
professionals and entrepreneurs seeking growth", pillars of "Industry
Insights / Tips & Guides / Behind the Scenes / Success Stories" -- which is
why a luxury-lifestyle page and an AI-cinema page produced captions that read
identically. The caption writer is given the description, audience, tone and
pillars verbatim, so generic input can only produce generic output.

Two of these are also repositioned. An account described as NSFW cannot be
monetised on Meta at all: the Content Monetization Policies exclude sexually
suggestive material, and the Adult Nudity policy restricts the reach of the
account carrying it. The profiles below describe what those pages can be --
AI cinematic art and fashion editorial -- which is a real, large, monetisable
niche. The imagery has to match the description for that to mean anything;
this file only fixes the half that is text.

    python scripts/write_brand_profiles.py            # show what would change
    python scripts/write_brand_profiles.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

PROFILES = {
    "Billionaire Goal777": dict(
        niche="Luxury lifestyle & wealth motivation",
        description=(
            "Billionaire Goal is a luxury lifestyle and wealth-mindset media page for "
            "people building toward financial independence. The feed is a daily window "
            "into what disciplined ambition eventually buys: superyachts off Saint-Tropez, "
            "hypercars in private collections, penthouse skylines, private aviation and "
            "the quiet details of a life most people only see in films.\n\n"
            "The page is aspirational rather than boastful. Every post is framed as "
            "evidence that the standard exists and is reachable, not as a taunt. The "
            "audience is not here to be told they are behind; they are here to be "
            "reminded what they are working for.\n\n"
            "Captions are short, confident and declarative. They name what is on screen, "
            "attach one idea about the mindset or discipline behind it, and stop. No "
            "life-coaching essays, no fake statistics, no invented quotes from founders. "
            "The imagery carries the aspiration; the words only have to point at it."
        ),
        targetAudience=(
            "Men and women aged 20-40 building businesses or careers toward financial "
            "freedom: early-stage founders, traders, freelancers and ambitious "
            "professionals. They follow luxury and wealth accounts for motivation and "
            "for the aesthetic, and they respond to confidence and restraint rather "
            "than hype or hustle-culture shouting."
        ),
        toneOfVoice=(
            "Confident, aspirational and restrained. Short declarative sentences. "
            "Calm authority rather than excitement. Never preachy, never a lecture."
        ),
        contentPillars=[
            "Superyachts & private aviation",
            "Hypercars and rare collections",
            "Penthouse & architectural luxury",
            "Wealth mindset and discipline",
            "Destinations of the ultra-wealthy",
        ],
        suggestedHashtags=[
            "#luxurylifestyle", "#billionairelifestyle", "#successmindset",
            "#luxury", "#entrepreneurmindset", "#wealthbuilding",
            "#superyacht", "#hypercar", "#luxuryliving", "#motivation",
        ],
        primaryOffer="Follow for daily luxury",
    ),
    "HollyVerse": dict(
        niche="AI cinematic portrait & fashion editorial art",
        description=(
            "HollyVerse is an AI art page in the language of Hollywood cinema. Every "
            "image is an original AI-generated character rendered as a film still: "
            "editorial fashion portraits, golden-hour cinematography, noir lighting, "
            "red-carpet glamour and the visual grammar of studio-era Hollywood.\n\n"
            "The page is positioned as digital art and character design, not as "
            "photography of real people. Characters are original creations. The appeal "
            "is craft -- lighting, styling, composition and the strangeness of images "
            "that look like frames from films that were never made.\n\n"
            "Captions treat each image as a piece of art with a story behind it. One "
            "line of scene-setting, one note on the look or the mood, and a light "
            "prompt for the audience to react. Never claims an image is a photograph, "
            "never names or implies a real actor, and never describes a person's body."
        ),
        targetAudience=(
            "AI art enthusiasts, digital creators, fashion and film aesthetics fans "
            "aged 18-35 who follow midjourney/AI-art accounts, cinematography pages and "
            "editorial fashion feeds. They care about how an image was made and engage "
            "with prompts, styling and technique."
        ),
        toneOfVoice=(
            "Cinematic, atmospheric and art-directed. Descriptive rather than "
            "flirtatious. Reads like a gallery caption or a director's note, never "
            "like a personal ad."
        ),
        contentPillars=[
            "Cinematic AI portraits",
            "Editorial fashion & styling",
            "Lighting and colour study",
            "Character design and world-building",
            "Behind the prompt",
        ],
        suggestedHashtags=[
            "#aiart", "#aiartwork", "#digitalart", "#cinematic",
            "#aigenerated", "#fashioneditorial", "#portraitart",
            "#aiartcommunity", "#conceptart", "#filmaesthetic",
        ],
        primaryOffer="Follow for daily AI art",
    ),
    "BollyVerse": dict(
        niche="AI cinematic art in the language of Indian cinema",
        description=(
            "BollyVerse is an AI art page built on the visual language of Indian "
            "cinema. Original AI-generated characters are rendered as film stills: "
            "monsoon light, festival colour, bridal couture, palace interiors, "
            "song-sequence staging and the saturated romance of classic Bollywood "
            "cinematography.\n\n"
            "The page is digital art and character design, not photography of real "
            "people. Characters are original creations, never likenesses of actors. "
            "The draw is craft and cultural aesthetic -- the styling, the colour, the "
            "sense of a scene from a film that does not exist.\n\n"
            "Captions set the scene in one line, note the look or the mood, and invite "
            "a reaction. Written for an audience that loves the cinema itself. Never "
            "claims an image is a photograph, never names or implies a real actor, and "
            "never describes a person's body."
        ),
        targetAudience=(
            "AI art and Indian cinema fans aged 18-35, in India and across the diaspora. "
            "They follow film aesthetics, fashion and AI-art accounts, and engage with "
            "colour, couture and the nostalgia of classic Bollywood staging."
        ),
        toneOfVoice=(
            "Warm, cinematic and colour-rich. Evocative but restrained. Occasional "
            "Hindi or Hinglish phrasing where it lands naturally, never forced."
        ),
        contentPillars=[
            "Cinematic AI portraits",
            "Bridal and festival couture",
            "Colour, light and set design",
            "Character design and world-building",
            "Behind the prompt",
        ],
        suggestedHashtags=[
            "#aiart", "#bollywoodstyle", "#digitalart", "#aiartwork",
            "#indianfashion", "#cinematic", "#aigenerated",
            "#desiaesthetic", "#conceptart", "#aiartcommunity",
        ],
        primaryOffer="Follow for daily AI art",
    ),
    "Organic Marketing AI": dict(
        niche="Marketing automation software for small businesses",
        description=(
            "Organic Marketing AI runs a small business's social media without the "
            "business having to think about it. Connect Instagram and Facebook, add "
            "your photos and videos once, and the platform writes the captions, picks "
            "what to post next, brands every clip and publishes on your schedule.\n\n"
            "It is built for owners who know they should be posting daily and never "
            "do -- because it is the twentieth thing on a list of nineteen. There is "
            "no content calendar to maintain and no agency retainer. It is $17 a month "
            "and it runs whether or not anyone opens the dashboard.\n\n"
            "The account is the product's own proof. Everything posted here was "
            "scheduled, captioned and published by the software itself. Posts show "
            "real output and real mechanics -- what got posted, why that asset was "
            "chosen, what the automation did overnight -- rather than generic marketing "
            "advice. Concrete and specific; never invents metrics or customer numbers."
        ),
        targetAudience=(
            "Owners of small businesses and solo founders who need consistent social "
            "presence but have no time or team for it: local services, e-commerce "
            "shops, coaches, agencies managing several client accounts. Practical "
            "buyers who care about time saved and want to see the thing working."
        ),
        toneOfVoice=(
            "Plain, direct and practical. Concrete over clever. Short sentences, real "
            "numbers, no marketing-speak. Confident without overselling."
        ),
        contentPillars=[
            "Posted by the software itself",
            "Time saved versus posting by hand",
            "How the automation decides what to post",
            "Small-business social media in practice",
            "Product updates and what shipped",
        ],
        suggestedHashtags=[
            "#smallbusiness", "#socialmediamarketing", "#marketingautomation",
            "#aitools", "#smallbusinessowner", "#contentmarketing",
            "#entrepreneur", "#saas", "#instagramgrowth", "#automation",
        ],
        primaryOffer="Start for $17/month",
    ),
}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    from database import AsyncSessionLocal, BusinessProfile, init_db

    await init_db()
    changed = 0

    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(select(BusinessProfile))).scalars().all()
        by_name = {p.name: p for p in profiles}

        for name, fields in PROFILES.items():
            p = by_name.get(name)
            if p is None:
                print(f"  {name}: no such workspace, skipped")
                continue

            print(f"\n=== {name} ===")
            print(f"  niche     {p.niche!r}  ->  {fields['niche']!r}")
            print(f"  audience  {(p.targetAudience or '')[:48]!r}")
            print(f"         -> {fields['targetAudience'][:48]!r}")
            print(f"  pillars   {(p.contentPillars or [])}")
            print(f"         -> {fields['contentPillars']}")
            print(f"  offer     {p.primaryOffer!r}  ->  {fields['primaryOffer']!r}")
            print(f"  desc      {len(p.description or '')} chars -> {len(fields['description'])} chars")

            if args.apply:
                for k, v in fields.items():
                    setattr(p, k, v)
                # Stops the loop's self-heal from overwriting these with
                # generated defaults, which is where the generic ones came from.
                p.brandAnalysisComplete = True
                changed += 1

        if args.apply:
            await session.commit()

    print()
    if args.apply:
        print(f"Updated {changed} workspace(s). Brand intelligence is rebuilt lazily, "
              f"so the next post for each uses the new profile.")
    else:
        print("Dry run. Re-run with --apply to write these.")
    return 0


if __name__ == "__main__":
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    raise SystemExit(asyncio.run(main()))
