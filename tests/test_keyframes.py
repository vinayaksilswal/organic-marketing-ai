"""The two frames a clip is generated between, and what the last one says.

A text-to-video model cannot spell a sentence, which is why the spoken call to
action exists. An image model can, so the frame carrying the brand name and
the offer is generated as a still and the clip is built to land on it.

The call to action is the part with money attached, so it is pinned here: the
composited ffmpeg card and the generated end frame read from one function, and
these tests are what stop them drifting apart again.
"""

import pytest

from services import keyframes as kf
from services.video_outro import outro_text_for


class _P:
    """Minimal stand-in for a BusinessProfile."""

    def __init__(self, **kw):
        self.name = kw.get("name", "Acme")
        self.primaryOffer = kw.get("primaryOffer", "")
        self.websiteUrl = kw.get("websiteUrl", "")
        self.businessModel = kw.get("businessModel", "SaaS")
        self.brandColors = kw.get("brandColors", [])
        self.description = kw.get("description", "")
        self.targetAudience = kw.get("targetAudience", "")


# =============================================================================
# What the end frame asks for
# =============================================================================

def test_ecommerce_with_no_offer_says_shop_now():
    """Both live shops had an empty offer, so the card rendered a brand name
    and nothing to do with it."""
    _, cta, dest = kf.cta_for(_P(businessModel="E-commerce", websiteUrl="https://mycart4u.com/"))
    assert cta == "Shop now"
    assert dest == "mycart4u.com"


def test_a_site_with_no_offer_is_told_where_to_go():
    _, cta, _ = kf.cta_for(_P(businessModel="SaaS", websiteUrl="https://quantcai.in"))
    assert cta == "Visit quantcai.in today"


def test_a_page_asks_for_the_follow():
    _, cta, dest = kf.cta_for(_P(name="BollyVerse", businessModel="Social Page"))
    assert cta == "Follow for more"
    assert dest == "@bollyverse"


@pytest.mark.parametrize("model", ["SaaS", "E-commerce", "Social Page"])
def test_the_business_own_words_win(model):
    """primaryOffer is written from the copy on their own site. A promise they
    have already made publicly beats any default we could invent."""
    offer = "Follow for daily AI art" if model == "Social Page" else "Start free - no card"
    _, cta, _ = kf.cta_for(_P(businessModel=model, primaryOffer=offer))
    assert cta == offer


def test_creators_are_not_forced_into_a_follow():
    """A creator account often does sell something; overwriting a real offer
    with 'Follow for more' loses the sale."""
    _, cta, _ = kf.cta_for(_P(businessModel="Creator", primaryOffer="Join the newsletter"))
    assert cta == "Join the newsletter"


def test_a_path_is_part_of_the_destination():
    """acme.com/pricing is where the offer lives. Truncating to the apex
    domain sends people somewhere else."""
    _, _, dest = kf.cta_for(_P(websiteUrl="https://www.acme.com/pricing"))
    assert dest == "acme.com/pricing"


def test_domains_are_lowercased():
    """'Lumively.com' on an end card reads as a typo rather than a brand."""
    _, _, dest = kf.cta_for(_P(businessModel="E-commerce", websiteUrl="https://Lumively.com"))
    assert dest == "lumively.com"


# =============================================================================
# The spoken line
# =============================================================================

def test_the_spoken_line_does_not_stutter():
    """'Visit quantcai.in today at quantcai.in' - the default already names the
    destination, so appending it again repeats it."""
    line = kf.cta_line(_P(businessModel="SaaS", websiteUrl="https://quantcai.in"))
    assert line.lower().count("quantcai.in") == 1


def test_the_spoken_line_adds_the_destination_when_the_offer_omits_it():
    line = kf.cta_line(_P(businessModel="E-commerce", websiteUrl="https://mycart4u.com"))
    assert line == "Shop now at mycart4u.com."


# =============================================================================
# One source of truth
# =============================================================================

@pytest.mark.parametrize("model,site", [
    ("SaaS", "https://quantcai.in"),
    ("E-commerce", "https://mycart4u.com"),
    ("Social Page", ""),
])
def test_the_card_and_the_frame_cannot_disagree(model, site):
    """These were separate implementations and drifted, so a clip could be
    composited with one offer and generated with another."""
    p = _P(businessModel=model, websiteUrl=site)
    assert outro_text_for(p)[1] == kf.cta_for(p)[1]
    assert outro_text_for(p)[2] == kf.cta_for(p)[2]


# =============================================================================
# The frames themselves
# =============================================================================

@pytest.mark.anyio
async def test_the_last_frame_carries_the_name_and_the_offer_verbatim():
    """Everything that matters on this frame is a fixed string. A model that
    paraphrases turns 'Shop now' into 'Shop Today!' for a business that never
    said it."""
    p = _P(name="MyCart4U", businessModel="E-commerce", websiteUrl="https://mycart4u.com")
    prompt = await kf.last_frame_prompt(p)
    assert '"MyCart4U"' in prompt
    assert '"Shop now"' in prompt
    assert "mycart4u.com" in prompt
    assert "9:16" in prompt


@pytest.mark.anyio
async def test_the_last_frame_stays_spare():
    """Image models render short text well and crowded text badly."""
    prompt = await kf.last_frame_prompt(_P())
    for crowding in ("photograph", "no objects", "no logo", "no decoration"):
        assert crowding in prompt


def test_the_clip_leads_with_a_hook_and_lands_on_the_card():
    assert kf.HOOK_SECONDS == 3.0
    assert kf.OUTRO_SECONDS == 2.0
    assert kf.HOOK_SECONDS + kf.OUTRO_SECONDS < kf.TOTAL_SECONDS
