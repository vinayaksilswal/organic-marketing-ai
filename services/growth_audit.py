"""A free audit of a stranger's website, built only from what is on it.

The funnel this serves: a visitor pastes a URL, gets something genuinely
useful without an account, and the call to action becomes "publish this plan"
rather than "sign up for our software".

WHY THE SCORE IS A CHECKLIST AND NOT A JUDGEMENT
------------------------------------------------
The obvious version of this feature shows "Brand score: 72, Social
consistency: 38". Those numbers cannot be computed from a website. We have no
access to the visitor's social accounts, so a consistency score is invented,
and an invented number shown to a prospect as a measurement is a lie told to
someone deciding whether to trust us — by a product whose whole pitch is that
it does not invent figures. prompt_engine already gates captions for exactly
this.

So the score here is a count. Each point is one concrete thing a marketing
site either states or does not, checked against the page text, and every one
is returned with its verdict so the visitor can look and disagree. A score
somebody can check is worth more than a score that merely sounds precise.

WHAT THE MODEL IS AND IS NOT ASKED FOR
--------------------------------------
It reads the page and reports what the business appears to sell, to whom, and
what it could post. It is not asked to grade, to estimate reach, or to produce
any number at all — those come from the checklist, in code, where they can be
tested.

The page belongs to a stranger. Whoever controls it controls these bytes, so
the content is fenced before the model sees it.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from loguru import logger

# A shared snapshot per domain. The audit costs a scrape plus a model call, and
# a link that gets shared should not charge us once per visitor.
CACHE_SECONDS = 24 * 60 * 60
_cache: Dict[str, Dict[str, Any]] = {}

MAX_SCRAPE_CHARS = 6000


def normalise_url(raw: str) -> Optional[str]:
    """Accept what people actually type. Return None if it is not a website."""
    value = (raw or "").strip()
    if not value:
        return None

    # "organiflo.com" is what someone types; urlparse needs the scheme.
    if not re.match(r"^https?://", value, re.I):
        value = f"https://{value}"

    try:
        parsed = urlparse(value)
    except Exception:
        return None

    host = (parsed.hostname or "").lower()
    # A dot is not enough: "hello." has one and is not a domain. Require a
    # real label followed by a real TLD.
    if not host or not re.match(r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$", host):
        return None
    # Nobody's marketing site is on localhost, and this endpoint is
    # unauthenticated -- refusing internal hosts keeps it from being pointed at
    # the private network.
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or host.endswith(".local"):
        return None
    if host.startswith("192.168.") or host.startswith("10.") or host.startswith("169.254."):
        return None
    if re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host):
        return None

    return f"{parsed.scheme}://{host}{parsed.path or ''}".rstrip("/")


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


# =============================================================================
# The checklist
#
# Each entry is one thing a page either does or does not do, phrased as what
# the visitor gains by fixing it. Detection is deliberately generous: a false
# "you are missing this" on a page that has it makes the whole audit look
# careless, so each check looks for several spellings of the same idea.
# =============================================================================

_CHECKS: List[Tuple[str, str, str, List[str]]] = [
    (
        "says_what_it_sells",
        "States plainly what you sell",
        "A visitor who cannot tell what you do in one line does not scroll to find out.",
        [],  # judged from the model's reading, not a keyword
    ),
    (
        "names_the_customer",
        "Names who it is for",
        "Copy written for everyone reads as written for nobody.",
        [],
    ),
    (
        "has_a_call_to_action",
        "Asks for one clear action",
        "A page with no ask converts the people who were already going to buy, and nobody else.",
        ["book", "buy", "get started", "start free", "sign up", "contact us",
         "order", "shop now", "request", "call us", "enquire", "inquire",
         "schedule", "subscribe", "try free", "get a quote"],
    ),
    (
        "shows_proof",
        "Shows proof from real customers",
        "Claims made about yourself are discounted. Claims made by customers are not.",
        ["testimonial", "review", "rated", "trusted by", "case study",
         "customers say", "what our clients", "5 star", "five star", "★"],
    ),
    (
        "is_contactable",
        "Gives a way to reach a human",
        "The cost of a missing phone number is every customer who had one question.",
        ["contact", "email us", "phone", "whatsapp", "call ", "@", "tel:", "mailto:"],
    ),
    (
        "answers_objections",
        "Answers the question that stops people buying",
        "Every business has one. Answering it on the page saves the conversation.",
        ["faq", "frequently asked", "how it works", "pricing", "how much",
         "questions", "guarantee", "refund", "shipping", "delivery"],
    ),
    (
        "links_social",
        "Points to somewhere it posts",
        "A site with no feed behind it looks dormant, whatever the copy says.",
        # Only platforms this product can actually publish to. Rewarding a
        # link to somewhere we cannot post would make the checklist misleading.
        ["instagram.com", "facebook.com", "linkedin.com", "youtube.com",
         "x.com/", "twitter.com"],
    ),
]

TOTAL_CHECKS = len(_CHECKS)


def _run_checklist(page_text: str, model_view: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Score the page. Keyword checks read the page; the first two read the
    model's summary, because "states what it sells" is a comprehension
    question rather than a string search."""
    haystack = (page_text or "").lower()
    findings: List[Dict[str, Any]] = []

    for key, label, why, needles in _CHECKS:
        if key == "says_what_it_sells":
            passed = bool((model_view.get("what_they_sell") or "").strip())
        elif key == "names_the_customer":
            passed = bool((model_view.get("who_it_is_for") or "").strip())
        else:
            passed = any(n in haystack for n in needles)

        findings.append({"key": key, "label": label, "why": why, "passed": passed})

    return findings


def _score(findings: List[Dict[str, Any]]) -> int:
    return sum(1 for f in findings if f["passed"])


# =============================================================================
# The audit
# =============================================================================

_SYSTEM = (
    "You read a company's website and report what is actually on it. You never "
    "invent products, customers, numbers, prices or claims. If the page does "
    "not say something, you leave that field empty rather than guessing. You "
    "do not grade, rate or score anything."
)


def _prompt(fenced_page: str, domain: str) -> str:
    return (
        f"Below is the homepage text for {domain}.\n\n"
        f"{fenced_page}\n\n"
        "Report only what the page supports.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "what_they_sell": "one sentence, in plain words, or \\"\\" if the page never says",\n'
        '  "who_it_is_for": "one sentence, or \\"\\" if the page never says",\n'
        '  "content_angles": ["three things this business could post about that '
        'come from its own page, not from marketing in general"],\n'
        '  "week": [\n'
        '    {"day": "Monday", "format": "Reel | Carousel | Image | Text", '
        '"idea": "a specific post for THIS business"}\n'
        "  ]\n"
        "}\n\n"
        "The week must have exactly seven entries, Monday to Sunday. Every idea "
        "must be something this specific business could film or write on the "
        "day. No placeholders, no 'share a tip', no invented statistics."
    )


def _fallback_week(what: str) -> List[Dict[str, str]]:
    """A usable week when the model is unavailable, which on a rate-limited
    free tier is a normal Tuesday rather than an outage."""
    subject = what.strip() or "what you do"
    return [
        {"day": "Monday", "format": "Reel",
         "idea": f"The mistake people make before they come to you, about {subject}"},
        {"day": "Tuesday", "format": "Carousel",
         "idea": "A customer's before and after, in their words"},
        {"day": "Wednesday", "format": "Image",
         "idea": "One thing you offer, explained properly, with the price if you show prices"},
        {"day": "Thursday", "format": "Reel",
         "idea": "Thirty seconds of the work actually happening"},
        {"day": "Friday", "format": "Text",
         "idea": "The question you answer every week, answered once, publicly"},
        {"day": "Saturday", "format": "Image",
         "idea": "Where you are and who you serve nearby"},
        {"day": "Sunday", "format": "Reel",
         "idea": "Why you started, in your own voice"},
    ]


async def run(website_url: str) -> Dict[str, Any]:
    """Audit a website. Never raises; a thin result is better than an error."""
    url = normalise_url(website_url)
    if not url:
        return {"ok": False, "error": "That does not look like a website address."}

    domain = domain_of(url)

    cached = _cache.get(domain)
    if cached and (time.time() - cached["at"]) < CACHE_SECONDS:
        return {**cached["audit"], "cached": True}

    page = ""
    try:
        from services.video_pipeline_service import scrape_product_url

        page = (await scrape_product_url(url)) or ""
    except Exception as e:
        logger.warning(f"Growth audit: could not read {domain}: {e}")

    if not page.strip():
        return {
            "ok": False,
            "domain": domain,
            "error": (
                "We could not read that page. Some sites block automated "
                "readers — that is not a mark against you, and the rest of "
                "Organiflo works from what you tell it directly."
            ),
        }

    # The cap belongs to the model call, not to the checklist. Contact
    # details and social links live in the footer -- the far end of a long
    # page -- so truncating first failed those two checks on every
    # substantial site regardless of the truth. organiflo.com was told it
    # linked to nowhere while its own footer linked to Instagram.
    full_page = page
    page_for_model = page[:MAX_SCRAPE_CHARS]

    view: Dict[str, Any] = {}
    try:
        from services.ai_service import _call_openrouter, _parse_json_response
        from services.untrusted_text import guarded_block

        # A stranger's page. Whoever controls it controls these bytes, and the
        # model cannot tell an instruction from a description.
        fenced = guarded_block(page_for_model, label="website_content", source=url)
        raw = await _call_openrouter(
            _prompt(fenced, domain), system_prompt=_SYSTEM, json_response=True
        )
        view = _parse_json_response(raw) or {}
    except Exception as e:
        logger.warning(f"Growth audit: synthesis failed for {domain}: {e}")

    what = (view.get("what_they_sell") or "").strip()
    who = (view.get("who_it_is_for") or "").strip()

    angles = [a for a in (view.get("content_angles") or []) if isinstance(a, str) and a.strip()][:3]

    week = [
        w for w in (view.get("week") or [])
        if isinstance(w, dict) and (w.get("idea") or "").strip()
    ][:7]
    if len(week) < 7:
        week = _fallback_week(what)

    findings = _run_checklist(full_page, view)
    score = _score(findings)

    audit = {
        "ok": True,
        "domain": domain,
        "url": url,
        "whatTheySell": what,
        "whoItIsFor": who,
        "score": score,
        "outOf": TOTAL_CHECKS,
        # Named so nobody reads it as a grade out of 100.
        "scoreBasis": f"{score} of {TOTAL_CHECKS} things a page needs were found on {domain}.",
        "findings": findings,
        "contentAngles": angles,
        "week": week,
        "cached": False,
    }

    _cache[domain] = {"at": time.time(), "audit": audit}
    return audit
