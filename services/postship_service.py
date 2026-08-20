"""
=============================================================================
Organic Marketing AI — PostShip Multi-Platform Engine
=============================================================================
"One click. Every platform, natively."
The same ship line, idea, or product URL rewritten for how each platform
actually reads — not copy-pasted three times:
  1. X (Twitter): Punchy, short-form viral text, build-in-public hook
  2. LinkedIn: Story-driven founder lessons, clean spacing, business value
  3. Reddit: Authentic, zero-fluff builder story with subreddit recommendation
=============================================================================
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
import httpx
from loguru import logger

from services.ai_service import _call_openrouter, MARKETING_MODEL


async def _fetch_url_summary(url: str) -> str:
    """Fetch website HTML and extract title and text snippet."""
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                html = resp.text
                title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else ""
                clean_text = re.sub(r"<[^>]+>", " ", html)
                clean_text = re.sub(r"\s+", " ", clean_text).strip()
                return f"Website Title: {title}\nWebsite Content: {clean_text[:500]}"
    except Exception as e:
        logger.warning(f"PostShip URL fetch failed ({url}): {e}")
    return ""


async def generate_postship_bundle(
    input_text: str,
    url: Optional[str] = None,
    business_name: Optional[str] = None,
    industry: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transform an idea, a ship line, a changelog, or a product URL into 3 native platform posts.
    """
    scraped_context = ""
    target_url = url or (input_text.strip() if input_text.strip().startswith("http") else None)
    if target_url:
        scraped_context = await _fetch_url_summary(target_url)

    source_content = input_text.strip()
    if scraped_context:
        source_content = f"{source_content}\n\n[Website Context]:\n{scraped_context}"

    system_prompt = f"""You are PostShip — an elite social copywriter who writes natively for X (Twitter), LinkedIn, and Reddit.

THE GOLDEN RULE: "One click. Every platform, natively."
Never copy-paste the same copy across platforms. Each platform has a completely different culture, reading rhythm, and formatting standard:

1. X (TWITTER) POST:
- Max 240-270 characters, or short 3-line punchy format.
- Build-in-public, casual, direct, confident, zero corporate fluff.
- Short line breaks. One decisive insight or micro-story.

2. LINKEDIN POST:
- Story-driven, founder vulnerability or business insight.
- Strong hook line on row 1 (stops the scroll before "...see more").
- Generous line breaks (1-2 sentences per paragraph).
- Actionable takeaway or lesson learned. No cringe buzzwords ("humbled and honored").

3. REDDIT POST:
- Highly authentic, candid, zero-bullshit developer/builder tone.
- Subreddit suggestion (e.g., "r/SideProject", "r/SaaS", "r/Entrepreneur", "r/webdev").
- Compelling, non-clickbait Reddit Title.
- Body explaining the exact problem faced, what was built/fixed, and asking the community for honest feedback without sounding salesy.

OUTPUT FORMAT: Return VALID JSON ONLY:
{{
  "x_post": {{
    "handle": "@{business_name.lower().replace(' ', '') if business_name else 'founder'}",
    "display_name": "{business_name or 'Founder'}",
    "content": "<The exact X post text with clean linebreaks>",
    "metrics_estimate": {{ "likes": "310", "retweets": "48", "replies": "12", "views": "21K" }}
  }},
  "linkedin_post": {{
    "author_name": "{business_name or 'Founder'}",
    "headline": "Founder & Builder",
    "hook_line": "<The scroll-stopping first sentence>",
    "content": "<The complete LinkedIn post with clean paragraph spacing>",
    "metrics_estimate": {{ "reactions": "47", "comments": "6" }}
  }},
  "reddit_post": {{
    "subreddit": "r/SideProject",
    "title": "<Intriguing, candid Reddit post title>",
    "body": "<Authentic Reddit markdown post body>",
    "metrics_estimate": {{ "upvotes": "248", "comments": "32" }}
  }}
}}
"""

    user_prompt = f"""Generate the native 3-platform PostShip bundle:
Source Idea / Ship Line / URL:
\"\"\"{source_content}\"\"\"

Business Context: {business_name or 'Startup Builder'} ({industry or 'Tech SaaS'})
"""

    raw_response = await _call_openrouter(
        user_prompt,
        system_prompt=system_prompt,
        json_response=True,
        model=MARKETING_MODEL,
    )

    def _parse_and_normalize(text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        parsed: Dict[str, Any] = {}
        try:
            parsed = json.loads(cleaned)
        except Exception:
            pass

        bname = business_name or "Founder"
        clean_idea = input_text[:80] if input_text else "Shipped writing styles today"

        x = parsed.get("x_post") if isinstance(parsed.get("x_post"), dict) else {}
        li = parsed.get("linkedin_post") if isinstance(parsed.get("linkedin_post"), dict) else {}
        rd = parsed.get("reddit_post") if isinstance(parsed.get("reddit_post"), dict) else {}

        # Normalize X post
        x_content = x.get("content") or f"{clean_idea}.\n\nthe bug that almost stopped me: a render race that only appeared with 2+ tabs open. 3 hours, 1 line fix.\n\nit's always one line."
        x_post = {
            "handle": x.get("handle") or f"@{bname.lower().replace(' ', '')}",
            "display_name": x.get("display_name") or bname,
            "content": str(x_content).strip(),
            "metrics_estimate": x.get("metrics_estimate") or { "likes": "310", "retweets": "48", "replies": "12", "views": "21K" }
        }

        # Normalize LinkedIn post
        li_content = li.get("content") or f"Three weeks on workspace auth. Four people used it.\n\nThen I shipped {clean_idea} in an afternoon — 40 lines — and it's the change people actually thank me for.\n\nBuild the boring thing that works."
        linkedin_post = {
            "author_name": li.get("author_name") or bname,
            "headline": li.get("headline") or f"Founder at {bname}",
            "hook_line": li.get("hook_line") or "Three weeks on workspace auth. Four people used it.",
            "content": str(li_content).strip(),
            "metrics_estimate": li.get("metrics_estimate") or { "reactions": "47", "comments": "6" }
        }

        # Normalize Reddit post
        sub = str(rd.get("subreddit") or "r/SideProject").strip()
        if not sub.startswith("r/"):
            sub = f"r/{sub}"
        reddit_post = {
            "subreddit": sub,
            "title": str(rd.get("title") or f"Spent 3 hours on a bug that was one line. Every time.").strip(),
            "body": str(rd.get("body") or f"Render race that only showed up with 2+ tabs open. Logs looked fine. The fix was one line — it's always one line.\n\nCurious how others track these down when shipping {clean_idea}?").strip(),
            "metrics_estimate": rd.get("metrics_estimate") or { "upvotes": "248", "comments": "32" }
        }

        return {
            "x_post": x_post,
            "linkedin_post": linkedin_post,
            "reddit_post": reddit_post,
        }

    bundle = _parse_and_normalize(raw_response)
    bundle["input_source"] = input_text
    bundle["url"] = target_url
    return bundle
