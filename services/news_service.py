"""Industry news, as raw material for LinkedIn posts.

WHY NEWS
--------
A business account that only talks about itself runs out of things to say by
week three, and the posts get steadily more promotional as it does. Commenting
on something that actually happened this week gives an account a reason to
post daily that is not "buy our thing" — which is the whole difference between
an account people follow and one they mute.

LinkedIn especially: it is a text-first feed where a short, opinionated take
on industry news outperforms a product announcement, and where a business with
no photographer can still show up every day.

WHY GOOGLE NEWS RSS
-------------------
It is free and needs no key. That matters here more than it usually would.
Every paid news API bills per request, and a daily fetch for every workspace
is exactly the shape of recurring cost this business cannot take on right now.

WHAT IS NOT DONE HERE
---------------------
No article body is fetched. The headline, source and date are enough to write
a comment on, and scraping the article would mean reproducing somebody else's
copy — the post has to be the customer's opinion about the news, not a
rewrite of the reporting.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx
from loguru import logger

FEED = "https://news.google.com/rss/search"

# Anything older than this is not news any more, and posting about it reads as
# an account that is not paying attention.
MAX_AGE_DAYS = 7

# Google returns the source name appended to the title: "Headline - Reuters".
# It is available separately, so the duplicate is stripped off.
_TRAILING_SOURCE = re.compile(r"\s+-\s+[^-]{2,40}$")


def _query_for(profile: Any) -> str:
    """What to search, built from the business rather than a fixed topic.

    Industry alone returns trade-press noise; industry plus what the business
    actually sells returns things its customers would recognise.
    """
    # Word-level dedupe, not field-level: "SaaS" and "B2B SaaS" are different
    # strings but produce "SaaS B2B SaaS", which narrows the search for no
    # gain. Google News matches on words, so the words are what must be unique.
    words: List[str] = []
    seen = set()
    for attr in ("industry", "businessModel"):
        for word in (getattr(profile, attr, None) or "").split():
            key = word.lower().strip(",.")
            if key and key not in seen:
                seen.add(key)
                words.append(word)

    # Six words is about the ceiling before a news query returns nothing at
    # all. The audience is deliberately left out: it describes who reads the
    # post, not what the news is about, and adding it emptied the results.
    return " ".join(words[:6]) or "small business marketing"


async def fetch(profile: Any, *, limit: int = 8,
                exclude_titles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Recent stories for this business's industry. Never raises.

    Returns [{title, source, link, published}], newest first.
    """
    query = _query_for(profile)

    # Recency has to be asked for in the query, not filtered afterwards.
    # Google News search is relevance-sorted, so a bare query returns articles
    # months old -- measured: 62 results for one query, none from this year's
    # last six months. `when:` makes the feed itself return only recent items.
    dated = f"{query} when:{MAX_AGE_DAYS}d"

    # Region follows the business where it is known, so an Indian business is
    # not handed only US coverage.
    country = (getattr(profile, "country", None) or "IN").upper()
    url = (
        f"{FEED}?q={quote_plus(dated)}"
        f"&hl=en-{country}&gl={country}&ceid={country}:en"
    )

    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Organiflo/1.0"})
        if resp.status_code != 200:
            logger.warning(f"Google News returned {resp.status_code} for '{query}'")
            return []
        root = ET.fromstring(resp.content)
    except Exception as e:
        logger.warning(f"Could not read industry news: {e}")
        return []

    seen = {(t or "").strip().lower() for t in (exclude_titles or [])}
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    stories: List[Dict[str, Any]] = []
    for item in root.iter("item"):
        title = html.unescape((item.findtext("title") or "").strip())
        if not title:
            continue

        source = html.unescape((item.findtext("source") or "").strip())
        if source:
            title = _TRAILING_SOURCE.sub("", title).strip()

        # Already written about. Repeating a story a week later is the fastest
        # way to look automated.
        if title.lower() in seen:
            continue

        published = _parse_date(item.findtext("pubDate"))
        if published and published < cutoff:
            continue

        stories.append({
            "title": title,
            "source": source or "the press",
            "link": (item.findtext("link") or "").strip(),
            "published": published.isoformat() if published else None,
        })

        if len(stories) >= limit:
            break

    logger.info(f"{len(stories)} stories for '{query}'")
    return stories


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(raw.strip(), fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Turning a story into a post
# ---------------------------------------------------------------------------

# Ways to have an opinion about news, so a week of daily posts does not read as
# seven paraphrases of seven headlines.
ANGLES = [
    ("agree_and_extend", "Agree with the story, then add what it misses."),
    ("disagree", "Take the opposite position and say why, carefully."),
    ("what_it_means", "Translate what this means for the reader's own business."),
    ("practical", "Turn it into something the reader can act on this week."),
    ("pattern", "Connect it to a longer trend you have been watching."),
]


def _post_prompt(profile: Any, story: Dict[str, Any], angle_key: str,
                 angle_note: str) -> str:
    name = getattr(profile, "name", "") or "this business"
    industry = getattr(profile, "industry", "") or "business"
    audience = getattr(profile, "targetAudience", "") or "business owners"
    tone = getattr(profile, "toneOfVoice", "") or "direct"

    return (
        f"You write LinkedIn posts for {name}, a {industry} business. Its "
        f"readers are {audience}. Tone: {tone}.\n\n"
        f"TODAY'S STORY\n"
        f"Headline: {story['title']}\n"
        f"Reported by: {story['source']}\n\n"
        f"YOUR ANGLE: {angle_note}\n\n"
        "Write one LinkedIn post reacting to this story.\n\n"
        "Rules:\n"
        "- Open with a line that works alone. LinkedIn hides everything past "
        "about 210 characters behind 'see more', so the first two lines have "
        "to earn the click.\n"
        "- Say something. A post that summarises the headline and stops is "
        "worth nothing; the reader could have read the headline.\n"
        "- Do not invent facts, figures, quotes or details that are not in "
        "the headline. You have the headline and the source, nothing more. If "
        "you need a number you do not have, write the post without one.\n"
        "- No hashtags beyond two. No emoji. No 'Thoughts?' at the end.\n"
        "- 120 words at most.\n"
        f"- Mention {name} only if it is genuinely relevant. A take that has "
        "to advertise is not a take.\n\n"
        'Return ONLY JSON: {"post": "the full text", "hook": "the first line"}'
    )


async def linkedin_post_from_news(profile: Any, story: Dict[str, Any],
                                  angle_index: int = 0) -> Optional[Dict[str, Any]]:
    """One LinkedIn post about one story. Never raises; returns None on failure."""
    from services.ai_service import _call_openrouter

    angle_key, angle_note = ANGLES[angle_index % len(ANGLES)]

    try:
        raw = await _call_openrouter(
            _post_prompt(profile, story, angle_key, angle_note),
            json_response=True,
        )
    except Exception as e:
        logger.warning(f"News post generation failed: {e}")
        return None

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None

    text = (data or {}).get("post") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        return None

    return {
        "content": text.strip(),
        "hook": (data.get("hook") or text.strip().split("\n")[0])[:200],
        "angle": angle_key,
        # Carried so the interface can show what the post is reacting to. A
        # take with no visible source reads as an opinion from nowhere.
        "source_title": story["title"],
        "source_name": story["source"],
        "source_link": story["link"],
    }


# ---------------------------------------------------------------------------
# The weekly newsletter
#
# Same raw material, different job. A LinkedIn post is one opinion about one
# story; a newsletter is the week in the reader's industry, summarised by
# somebody who read it so they did not have to. That is a reason to open an
# email from a business you have not bought anything from yet -- which is the
# only reason a list stays subscribed.
#
# Deliberately not a product announcement with news bolted on. A newsletter
# that is mostly promotion gets unsubscribed once and never opened again.
# ---------------------------------------------------------------------------

def _newsletter_prompt(profile: Any, stories: List[Dict[str, Any]]) -> str:
    name = getattr(profile, "name", "") or "this business"
    industry = getattr(profile, "industry", "") or "business"
    audience = getattr(profile, "targetAudience", "") or "business owners"
    tone = getattr(profile, "toneOfVoice", "") or "direct"

    listed = "\n".join(
        f"{i + 1}. {s['title']} ({s['source']})" for i, s in enumerate(stories)
    )

    return (
        f"You write the weekly email for {name}, a {industry} business. Its "
        f"readers are {audience}. Tone: {tone}.\n\n"
        f"THIS WEEK'S STORIES\n{listed}\n\n"
        "Write the week's email.\n\n"
        "Structure:\n"
        "- A subject line under 55 characters. Say what is inside, not "
        "'Newsletter #14'. No emoji.\n"
        "- One opening line that says what the week was about.\n"
        "- Three to five items. Each: a short bold-worthy heading, then two "
        "or three sentences on what happened and why it matters to the "
        "reader. Name the source.\n"
        "- One closing line.\n\n"
        "Rules:\n"
        "- Do not invent facts, figures or quotes. You have headlines and "
        "sources, nothing else. Write around anything you do not know.\n"
        f"- Mention {name} at most once, and only if it genuinely belongs. "
        "A roundup that is really an advert gets unsubscribed once and never "
        "opened again.\n"
        "- No 'In today's fast-paced world'. No 'Dear valued customer'.\n\n"
        'Return ONLY JSON: {"subject": "...", "preheader": "one line shown '
        'after the subject in the inbox", "items": [{"heading": "...", '
        '"body": "...", "source": "..."}], "intro": "...", "outro": "..."}'
    )


async def weekly_newsletter(profile: Any,
                            stories: Optional[List[Dict[str, Any]]] = None
                            ) -> Optional[Dict[str, Any]]:
    """The week in this business's industry, as a sendable email.

    Returns {subject, preheader, html, text, itemCount} or None. Never raises.
    """
    from services.ai_service import _call_openrouter

    if stories is None:
        stories = await fetch(profile, limit=6)

    # Three is the floor. A "weekly roundup" with one item reads as a business
    # that has nothing to say, which is worse than not sending.
    if len(stories) < 3:
        logger.info(f"Only {len(stories)} stories this week; no newsletter sent.")
        return None

    try:
        raw = await _call_openrouter(_newsletter_prompt(profile, stories),
                                     json_response=True)
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.warning(f"Newsletter generation failed: {e}")
        return None

    if not isinstance(data, dict):
        return None

    subject = (data.get("subject") or "").strip()
    items = [i for i in (data.get("items") or []) if isinstance(i, dict) and i.get("heading")]
    if not subject or not items:
        return None

    return {
        "subject": subject[:120],
        "preheader": (data.get("preheader") or "").strip()[:200],
        "itemCount": len(items),
        "html": _newsletter_html(profile, data, items),
        "text": _newsletter_text(data, items),
    }


def _newsletter_html(profile: Any, data: Dict[str, Any],
                     items: List[Dict[str, Any]]) -> str:
    """Table-based, inline-styled HTML.

    Not because it is pleasant, but because Outlook still ignores most of a
    stylesheet and a newsletter that renders broken in Outlook is a newsletter
    a third of the list never reads.
    """
    name = html.escape(getattr(profile, "name", "") or "")
    intro = html.escape((data.get("intro") or "").strip())
    outro = html.escape((data.get("outro") or "").strip())

    blocks = []
    for item in items:
        heading = html.escape((item.get("heading") or "").strip())
        body = html.escape((item.get("body") or "").strip())
        source = html.escape((item.get("source") or "").strip())
        blocks.append(
            '<tr><td style="padding:0 0 24px 0;">'
            f'<div style="font:600 17px/1.4 -apple-system,Segoe UI,Arial,sans-serif;'
            f'color:#0b1020;margin-bottom:6px;">{heading}</div>'
            f'<div style="font:400 15px/1.6 -apple-system,Segoe UI,Arial,sans-serif;'
            f'color:#3f4658;">{body}</div>'
            + (f'<div style="font:400 13px/1.5 -apple-system,Segoe UI,Arial,sans-serif;'
               f'color:#8a90a2;margin-top:5px;">{source}</div>' if source else "")
            + "</td></tr>"
        )

    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#f6f7fb;padding:28px 12px;"><tr><td align="center">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="max-width:600px;background:#ffffff;border-radius:12px;padding:32px;">'
        + (f'<tr><td style="font:700 14px/1.4 -apple-system,Segoe UI,Arial,sans-serif;'
           f'color:#6d28d9;letter-spacing:0.04em;text-transform:uppercase;'
           f'padding-bottom:18px;">{name}</td></tr>' if name else "")
        + (f'<tr><td style="font:400 16px/1.6 -apple-system,Segoe UI,Arial,sans-serif;'
           f'color:#3f4658;padding-bottom:26px;">{intro}</td></tr>' if intro else "")
        + "".join(blocks)
        + (f'<tr><td style="font:400 15px/1.6 -apple-system,Segoe UI,Arial,sans-serif;'
           f'color:#3f4658;padding-top:6px;border-top:1px solid #e8eaf0;">{outro}</td></tr>'
           if outro else "")
        + "</table></td></tr></table>"
    )


def _newsletter_text(data: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    """The plain-text part. Sending HTML alone is a spam signal, and some
    readers genuinely prefer this one."""
    break_ = chr(10) + chr(10)
    parts = []
    if data.get("intro"):
        parts.append(data["intro"].strip())
    for item in items:
        chunk = (item.get("heading") or "").strip()
        if item.get("body"):
            chunk += chr(10) + item["body"].strip()
        if item.get("source"):
            chunk += chr(10) + f"— {item['source'].strip()}"
        parts.append(chunk)
    if data.get("outro"):
        parts.append(data["outro"].strip())
    return break_.join(parts)
