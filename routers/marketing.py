"""
=============================================================================
Organic Marketing AI — Marketing Router (Enterprise SQLAlchemy)
=============================================================================
Handles the marketing dashboard UI and manual override endpoints for:
  - Social media post management (list, create manual, edit)
  - Email campaign management (list, create manual, edit)
  - Manual media upload with AI caption generation override
  - Audience management
  - Marketing logs and media catalog

All endpoints use SQLAlchemy 2.0 Async ORM.
All endpoints are authenticated via JWT.
=============================================================================
"""

from __future__ import annotations

import os
import re
import shutil
import urllib.parse
import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from sqlalchemy import select, and_, func
from database import (
    get_tenant_session,
    User,
    Audience,
    BusinessProfile,
    MarketingState,
    SocialCampaign,
    SocialPost,
    EmailCampaign,
    MarketingLog,
    Media,
    utc_now,
)
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel

from routers.auth import verify_user
from services.ai_service import generate_campaign_email, generate_campaign_variation
from services.email_service import send_email_blast
from services.social_service import (
    post_to_facebook,
    post_to_instagram,
    update_facebook_post,
    update_instagram_post,
)
from services.scheduler import execute_marketing_loop
from services.storage_service import upload_media_to_cloudinary

router = APIRouter(
    prefix="/api/v1/marketing",
    tags=["Marketing"],
    dependencies=[Depends(verify_user)],
)
templates = Jinja2Templates(directory="templates")

# Ensure uploads directory exists
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =============================================================================
# Request/Response Models
# =============================================================================
class SocialPostUpdate(BaseModel):
    """Model for updating an existing social post."""
    caption: Optional[str] = None
    scheduledAt: Optional[str] = None
    status: Optional[str] = None

class EmailCampaignUpdate(BaseModel):
    """Model for updating an existing email campaign."""
    subject: Optional[str] = None
    bodyText: Optional[str] = None
    bodyHtml: Optional[str] = None
    scheduledAt: Optional[str] = None
    status: Optional[str] = None

class ManualEmailRequest(BaseModel):
    """Model for creating a manual email campaign."""
    generateAiEmail: bool = False
    productId: Optional[str] = None
    manualSubject: str = ""
    manualBodyHtml: str = ""
    manualBodyText: str = ""

class AutoApproveUpdate(BaseModel):
    autoApprove: bool

# =============================================================================
# Dashboard
# =============================================================================
@router.get("/")
async def marketing_root() -> RedirectResponse:
    """Redirect /marketing to /marketing/dashboard."""
    return RedirectResponse(url="/marketing/dashboard")

@router.get("/dashboard")
async def marketing_dashboard(request: Request) -> Any:
    """Render the marketing automation dashboard page."""
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:

        a_stmt = select(Audience).where(Audience.businessProfileId == workspace_id)
        audiences = (await session.execute(a_stmt)).scalars().all()

        m_stmt = select(MarketingState).where(MarketingState.businessProfileId == workspace_id)
        state = (await session.execute(m_stmt)).scalars().first()
        auto_approve = state.autoApprove if state else False

    return templates.TemplateResponse(
        request=request,
        name="marketing.html",
        context={"title": "Marketing Automation", "audiences": audiences, "autoApprove": auto_approve},
    )

async def get_automation_state(session, workspace_id: str | None, user_id: str | None = None):
    """Return THE automation state row for a workspace, creating it if absent.

    Every reader used to do .first() with no ORDER BY against a table that had
    no uniqueness on businessProfileId, and three code paths created rows. So
    the auto-approve toggle could write one row while the publisher read
    another — the dashboard showed "off" and posts still went out.

    Ordering by createdAt makes the choice deterministic even on a database
    that still holds pre-migration duplicates. New rows are never created
    auto-approving: publishing to a real audience is the owner's call.
    """
    if not workspace_id:
        return None

    stmt = (
        select(MarketingState)
        .where(MarketingState.businessProfileId == workspace_id)
        .order_by(MarketingState.createdAt.asc())
    )
    state = (await session.execute(stmt)).scalars().first()
    if state:
        return state

    owner_id = user_id
    if not owner_id:
        profile = await session.get(BusinessProfile, workspace_id)
        owner_id = getattr(profile, "userId", None)
    if not owner_id:
        # Previously this fell back to "the first User in the table", which
        # attached one tenant's automation state to an unrelated account.
        return None

    state = MarketingState(
        userId=owner_id,
        businessProfileId=workspace_id,
        autoApprove=False,
        postIntervalHours=2,
    )
    session.add(state)
    await session.flush()
    return state


@router.get("/settings")
async def get_marketing_settings(request: Request) -> dict[str, Any]:
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:
        stmt = (
            select(MarketingState)
            .where(MarketingState.businessProfileId == workspace_id)
            .order_by(MarketingState.createdAt.asc())
        )
        state = (await session.execute(stmt)).scalars().first()
        if state:
            return {
                "success": True,
                "autoApprove": state.autoApprove,
                "intervalHours": state.postIntervalHours,
            }
        return {"success": True, "autoApprove": False, "intervalHours": 2}


@router.post("/settings/auto-approve")
async def toggle_auto_approve(
    data: AutoApproveUpdate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Select a business first.")

    async with get_tenant_session(workspace_id) as session:
        state = await get_automation_state(session, workspace_id, user_id)
        if not state:
            raise HTTPException(status_code=404, detail="That business could not be found.")

        state.autoApprove = data.autoApprove
        await session.commit()
        await session.refresh(state)

        logger.info(
            f"Auto-approve set to {state.autoApprove} for workspace {workspace_id} by user {user_id}"
        )
        return {"success": True, "autoApprove": state.autoApprove}


class IntervalUpdate(BaseModel):
    intervalHours: int


@router.post("/settings/interval")
async def update_interval(
    data: IntervalUpdate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Select a business first.")
    if data.intervalHours < 1 or data.intervalHours > 168:
        raise HTTPException(status_code=400, detail="Interval must be between 1 and 168 hours.")

    async with get_tenant_session(workspace_id) as session:
        state = await get_automation_state(session, workspace_id, user_id)
        if not state:
            raise HTTPException(status_code=404, detail="That business could not be found.")

        state.postIntervalHours = data.intervalHours
        await session.commit()
        await session.refresh(state)
        return {"success": True, "intervalHours": state.postIntervalHours}

_BANNED_CAPTION_PHRASES = (
    "unlock", "elevate", "game-changer", "game changer", "revolutioni",
    "seamless", "cutting-edge", "cutting edge", "leverage", "synergy",
    "empower", "supercharge", "take it to the next level",
    "in today's fast-paced", "in a world where", "let that sink in",
    "here's the truth nobody", "the analytical layer", "black box",
    "signal gets lost", "needle barely",
)

# "Most X don't have a Y problem. They have a Z problem." and its cousins.
_BANNED_OPENER_RE = re.compile(
    r"^\s*(most \w+ (don't|do not) have a .{0,40}problem"
    r"|it'?s not about .{0,40}\bit'?s about"
    r"|let'?s talk about"
    r"|here'?s the truth)",
    re.IGNORECASE,
)


# Camera and edit language. A caption containing these is retelling the shot
# list instead of writing copy — "watch the terminal light up with FIPS badges,
# then pan to a CycloneDX CBOM export" was a real generated caption.
_SHOT_NARRATION_RE = re.compile(
    r"\b(pan(s|ning)? (to|across)|cut(s|ting)? to|zoom(s|ing)? (in|out)"
    r"|the (shot|camera|frame)|close-up|watch (the|it) \w+ light up"
    r"|then (we )?(see|reveal)|slow motion shot)\b",
    re.IGNORECASE,
)

# Reviewer voice. The brand sells the product; it does not rate it.
_REVIEWER_VOICE_RE = re.compile(
    r"\b(our team (tested|tried|reviewed)|we tested|solid pick"
    r"|great (option|choice) for|worth (a look|considering)"
    r"|(highly )?recommend(ed)? for|top pick|our verdict)\b",
    re.IGNORECASE,
)

# Naming the audience segment instead of speaking to it. The qualifier is
# often separated from "for" by a noun — "solid PICK for entrepreneur parents".
_SEGMENT_LABEL_RE = re.compile(
    r"\b(perfect|ideal|great|solid|top|best|made|built|designed)\s+"
    r"(pick|choice|option|fit|match|tool)?\s*for\s+"
    r"(entrepreneur|business|busy|modern|savvy|aspiring|budding|ambitious)\b",
    re.IGNORECASE,
)


def _caption_quality_issues(caption: str) -> list[str]:
    """Return the reasons a caption should be rejected, empty if it passes.

    The prompt bans these, but a banned-word list only works if something
    checks. Models reliably drift back into marketing register on retry-free
    generation, which is how "We build the analytical layer that translates raw
    metrics into decisive action" reached a real feed.
    """
    issues = []
    low = caption.lower()

    hits = [p for p in _BANNED_CAPTION_PHRASES if p in low]
    if hits:
        issues.append(f"uses banned marketing filler: {', '.join(hits[:4])}")

    if _BANNED_OPENER_RE.search(caption):
        issues.append("opens with an exhausted LinkedIn formula")

    if _SHOT_NARRATION_RE.search(caption):
        issues.append(
            "retells the camera work instead of writing copy — the reader can "
            "already see the visual"
        )

    if _REVIEWER_VOICE_RE.search(caption):
        issues.append(
            "reviews the product from outside instead of speaking as the brand"
        )

    if _SEGMENT_LABEL_RE.search(caption):
        issues.append("labels the audience as a market segment instead of addressing them")

    body = re.sub(r"#\w+", "", caption)
    words = len(body.split())
    if words > 130:
        issues.append(f"too long at {words} words before hashtags")

    return issues


def _cloudinary_configured() -> bool:
    """Whether this deployment has object storage at all.

    upload_media_to_cloudinary returns None both when Cloudinary is not set up
    and when it rejected the file. Those need opposite handling: the first is a
    normal dev setup that should fall back to local disk, the second is a real
    failure the user must hear about, because the local fallback produces a
    relative URL that Facebook and Instagram cannot fetch.
    """
    from config import settings
    return bool(settings.cloudinary_cloud_name and settings.cloudinary_api_secret)


_URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)


def _strip_urls(text: str | None) -> str:
    """Remove URLs from a caption.

    Instagram does not linkify caption URLs, so a raw link is dead text that
    reads as spam. Copy should say "link in bio" instead. Applied as a
    backstop even though the prompts forbid links — models slip.
    """
    if not text:
        return ""
    cleaned = _URL_RE.sub("", text)
    # Collapse the double spaces and orphaned punctuation a removal leaves.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+([,.!?])", r"\1", cleaned)
    return cleaned.strip()


def _is_postable(media) -> bool:
    """True when this row is an actual publishable asset.

    The catalog also holds prompt-only rows (mimeType text/plain, empty url)
    saved by the Video Studio so the user can copy the prompt. Those are notes,
    not assets — selecting one for a post produced a caption with no image
    attached, or a publish failure.
    """
    if not getattr(media, "isActive", True):
        return False
    url = (getattr(media, "url", None) or "").strip()
    if not url:
        return False
    mime = (getattr(media, "mimeType", None) or "").lower()
    return mime.startswith("image/") or mime.startswith("video/")


async def _account_niche(workspace_id) -> str:
    """The connected Page's own category, as Meta classifies it.

    A niche taken from the platform beats one inferred from a website, and it
    is what stops two businesses on the same login producing interchangeable
    copy. Never fatal — absence just means one less signal.
    """
    if not workspace_id:
        return ""
    try:
        from database import SocialConnection
        async with get_tenant_session(workspace_id) as session:
            conn = (await session.execute(
                select(SocialConnection).where(
                    SocialConnection.businessProfileId == workspace_id
                )
            )).scalars().first()
            return (getattr(conn, "fbPageCategory", None) or "").strip() if conn else ""
    except Exception:
        return ""


async def _generate_post_caption(profile, media, product=None) -> str:
    """Write an on-brand caption for a specific media asset.

    Feeds the model everything actually known about the business and the asset.
    An earlier version passed only name/tone/audience, so captions were generic
    filler that could have described any SaaS — it never learned what the
    business does. The website description and the asset's own generation
    prompt are the two strongest signals and were both being discarded.
    """
    brand_name = getattr(profile, "name", None) or "the brand"
    description = (getattr(profile, "description", None) or "").strip()
    website = getattr(profile, "websiteUrl", None) or ""
    tone = getattr(profile, "toneOfVoice", None) or "confident, specific, no hype"
    audience = getattr(profile, "targetAudience", None) or ""
    industry = getattr(profile, "industry", None) or getattr(profile, "businessModel", None) or ""
    niche = getattr(profile, "niche", None) or ""
    pillars = getattr(profile, "contentPillars", None) or []
    hashtags = getattr(profile, "suggestedHashtags", None) or []

    # What the asset actually depicts. The base caption is authoritative — it
    # is either what the user typed about this asset or the prompt that
    # generated it, and in both cases it beats a filename. The raw generation
    # prompt is kept as a secondary signal when the two differ.
    asset_caption = (getattr(media, "caption", None) or "").strip()
    asset_prompt = (getattr(media, "prompt", None) or "").strip()
    asset_tags = ", ".join(getattr(media, "tags", None) or [])
    is_video = (getattr(media, "mimeType", "") or "").startswith("video/")

    offer = (getattr(profile, "primaryOffer", None) or "").strip()

    # A caption can only be as specific as the profile behind it. When the
    # description is missing or a one-liner, the model has nothing concrete to
    # anchor on and reliably falls back to category-level thought leadership —
    # which is exactly how a generic "we translate metrics into action" caption
    # gets written. Say so rather than letting it improvise.
    if len(description) < 40:
        logger.warning(
            f"Workspace {getattr(profile, 'id', '?')} has a thin brand description "
            f"({len(description)} chars). Captions will be generic until it is filled in."
        )

    known = [f"Business name: {brand_name}"]
    if description: known.append(f"What it does (from their own site): {description}")
    if website:     known.append(f"Website: {website}")
    if industry:    known.append(f"Industry: {industry}")
    if niche:       known.append(f"Niche: {niche}")
    if audience:    known.append(f"Target audience: {audience}")
    if pillars:     known.append(f"Content themes: {', '.join(pillars)}")
    page_category = await _account_niche(getattr(profile, "id", None))
    if page_category:
        known.append(f"The connected Facebook Page is categorised as: {page_category}")

    known.append(f"Tone of voice: {tone}")
    if offer:       known.append(f"The one action to drive (use this exact offer): {offer}")

    # When the post is about a specific catalog item, the product's own facts
    # outrank the brand-level summary — that is what makes an e-commerce post
    # sell a thing rather than describe a company.
    if product is not None:
        p_title = getattr(product, "title", None)
        p_desc = (getattr(product, "description", None) or "").strip()
        p_price = getattr(product, "price", None)
        if p_title: known.append(f"THIS POST IS ABOUT THIS PRODUCT: {p_title}")
        if p_desc:  known.append(f"Product details: {p_desc[:400]}")
        if p_price: known.append(f"Price: {p_price} (state it only if it reads naturally)")

    asset_lines = []
    if asset_caption or asset_prompt:
        # This is a SHOT LIST, not source material. Handing the cinematic
        # prompt over unlabelled made the writer paraphrase it — camera
        # directions and all — so captions opened with lines like
        # "watch the terminal light up, then pan to a CBOM export".
        asset_lines.append(
            "Below is the DIRECTOR'S BRIEF for the attached "
            f"{'video' if is_video else 'image'}. It is camera and lighting "
            "instructions. Read it ONLY to know what the viewer will be "
            "looking at. NEVER retell it, never mention shots, pans, cuts, "
            "screens, terminals or what 'lights up'."
        )
        asset_lines.append(f"--- brief (do not paraphrase) ---\n{(asset_caption or asset_prompt)[:900]}")
    else:
        # Be explicit rather than letting the model invent a scene.
        asset_lines.append(
            "No description of the visual is available — write about the "
            "business itself and do not describe what is on screen."
        )
    if asset_tags:   asset_lines.append(f"Asset tags: {asset_tags}")
    asset_lines.append(f"Format: {'short video / reel' if is_video else 'single image'}")

    system_prompt = (
        "You are the in-house copywriter for this company. You write AS the "
        "brand, to a customer — never about the brand, and never as a reviewer "
        "assessing someone else's product. Your defining trait is "
        "concreteness: a reader must finish the caption knowing what this "
        "specific company does, in plain words. You have contempt for "
        "LinkedIn thought-leadership voice — the abstract problem/insight essay "
        "that could describe any company in the category. You never invent "
        "facts, metrics, offers or features that were not given to you."
    )

    prompt = (
        "Write ONE social media caption for the post described below.\n\n"
        "=== THE BUSINESS ===\n" + "\n".join(known) + "\n\n"
        "=== THIS POST'S VISUAL ===\n" + "\n".join(asset_lines) + "\n\n"
        "=== REQUIREMENTS ===\n"
        "1. CONCRETE, NOT ABSTRACT. Name the actual thing this company does, "
        "using the nouns from its description above. If your caption would "
        "still make sense with a competitor's name swapped in, it has failed. "
        "Never describe the product as 'the layer', 'the framework', 'the "
        "system', 'the platform', 'the solution' or 'the engine' — say what it "
        "literally does.\n"
        "2. HOOK IN UNDER 10 WORDS, AND IT MUST COST THE READER SOMETHING TO "
        "IGNORE. A feature statement is not a hook. Open on the stake, the "
        "cost, the deadline, or a concrete surprising detail. Never open with "
        "the brand name.\n"
        "   Weak: \"curl command returns NIST-compliant PQC scan in seconds\"\n"
        "   Strong: \"Your TLS certificates have an expiry date nobody printed.\"\n"
        "3. NEVER NARRATE THE VISUAL. The brief above is camera direction for "
        "whoever shot the asset — it is not material to retell. Writing "
        "\"watch the terminal light up, then pan to the export\" turns a "
        "caption into a shot list. The reader can already see the picture; "
        "your job is to say what it MEANS for them.\n"
        "4. WRITE AS THE BRAND, TO A CUSTOMER. First person (\"we\", \"our\") "
        "or direct address (\"you\", \"your\"). Never review the product from "
        "outside it: no \"our team tested\", no \"solid pick\", no \"great "
        "option for\". You sell this, you do not rate it.\n"
        "5. SPEAK TO THE AUDIENCE, NEVER LABEL IT. The audience description is "
        "for your targeting, not for the copy. Writing \"perfect for "
        "entrepreneur parents\" or \"ideal for security engineers\" tells the "
        "reader they are a market segment. Address them directly instead.\n"
        "6. SHORT. 40-90 words total, excluding hashtags. Three short "
        "paragraphs maximum. Cut every sentence that is only setting up the "
        "next one.\n"
        "7. AT MOST TWO PIECES OF JARGON. Acronyms and product-internal terms "
        "cost the reader effort. Keep the two that carry real meaning for this "
        "audience and cut the rest — five acronyms in one sentence reads as "
        "noise even to an expert.\n"
        + (
            f'8. End with this exact call to action, word for word: "{offer}". '
            "Do not reword it, shorten it, or swap in your own.\n"
            if offer else
            "8. Conclude with a singular, strong, actionable Call-To-Action. No "
            "specific offer was provided, so keep it soft — invite them to look, "
            "do not promise a trial, discount or result. Avoid the dead phrases "
            "\"check it out\" and \"see it in action\"; say what they will get.\n"
        )
        + "9. Never put a URL in the caption — Instagram does not linkify them, so "
        "a raw link reads as spam and wastes the strongest line. Say 'link in bio'.\n"
        "10. Invent nothing: no fake statistics, customer counts, or discounts.\n"
        "11. Final line: 3-5 hashtags specific to this industry. No #love, no "
        "#instagood, no #business.\n\n"
        "=== BANNED OPENERS ===\n"
        "These formulas are exhausted. Using any of them fails the brief:\n"
        "- \"Most [people] don't have a [X] problem. They have a [Y] problem.\"\n"
        "- \"It's not about X. It's about Y.\"\n"
        "- \"Here's the truth nobody tells you about...\"\n"
        "- \"Let's talk about...\" / \"Let that sink in.\"\n"
        "- \"In today's fast-paced world\" / \"In a world where...\"\n"
        "- Any opener that states a generic industry problem before naming what "
        "this company does.\n\n"
        "=== BANNED WORDS AND PHRASES ===\n"
        "unlock, elevate, game-changer, revolutionise, revolutionize, "
        "seamless, cutting-edge, leverage, synergy, robust, empower, "
        "supercharge, transform your, take it to the next level, needle, "
        "signal vs noise, black box.\n"
        "Also banned as calls to action, because they ask for nothing and "
        "promise nothing: \"check it out\", \"see it in action\", "
        "\"learn more\", \"discover more\", \"don't miss out\".\n\n"
        + (
            ""
            if len(description) >= 40 else
            "=== WARNING: THIN BRAND DATA ===\n"
            "The description above is very short, so you do not know much about "
            "this company. Do NOT compensate by writing about the industry in "
            "general — that produces filler. Stay narrow: write only about what "
            "the visual shows and what the business name and niche imply, and "
            "keep it to two short sentences.\n\n"
        )
        + "=== BEFORE YOU ANSWER ===\n"
        "Check your draft against these. If any answer is no, rewrite it:\n"
        "- Could a reader say what this company sells, in one sentence?\n"
        "- Would the caption break if a competitor's name replaced this one?\n"
        "  (It should.)\n"
        "- Does it sound like the company talking, not someone reviewing it?\n"
        "- Have you avoided retelling the shot — no pans, cuts, screens or\n"
        "  'watch it light up'?\n"
        "- Does the first line cost something to ignore?\n"
        "- Is it under 90 words before hashtags?\n\n"
        "Output ONLY the caption. No preamble, no quotes, no explanation."
    )

    def _clean(text: str) -> str:
        text = (text or "").strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        for lead in ("Caption:", "Here's the caption:", "Here is the caption:"):
            if text.lower().startswith(lead.lower()):
                text = text[len(lead):].strip()
        return text

    try:
        from services.ai_service import _call_openrouter
        caption = _clean(await _call_openrouter(prompt, system_prompt=system_prompt))

        # One corrective pass. Naming the specific failure works far better
        # than asking again, because the model can see what it did wrong.
        issues = _caption_quality_issues(caption)
        if issues:
            logger.info(
                f"Caption rejected for workspace {getattr(profile, 'id', '?')} "
                f"({'; '.join(issues)}), retrying once"
            )
            retry = (
                prompt
                + "\n\n=== YOUR PREVIOUS ATTEMPT WAS REJECTED ===\n"
                + caption
                + "\n\nReasons: "
                + "; ".join(issues)
                + ".\nWrite a different caption that fixes these. Be more "
                "concrete and considerably shorter. Name what the company "
                "actually does in plain words."
            )
            second = _clean(await _call_openrouter(retry, system_prompt=system_prompt))
            # Keep the retry only if it genuinely improved.
            if second and len(_caption_quality_issues(second)) < len(issues):
                caption = second
        # Enforce the no-links rule rather than trusting the model to obey it.
        # The prompt forbids URLs, but models slip, and a raw link in an
        # Instagram caption is unclickable text that reads as spam.
        caption = _strip_urls(caption)
        if caption:
            return caption[:2200]  # Instagram's caption limit
        logger.warning(f"Caption generation returned empty for workspace {getattr(profile, 'id', '?')}")
    except Exception as e:
        logger.warning(f"Caption generation failed, using brand template: {e}")

    # Fallback still says something true about the business rather than filler.
    # It used to end "More at {website}", which put a URL in every fallback
    # caption — the exact thing the generated path is forbidden from doing.
    tags = " ".join(hashtags[:5]) if hashtags else "#b2b #technology"
    cta = offer or "Link in bio."
    if description:
        first = description.split(".")[0].strip()
        return _strip_urls(f"{first}.\n\n{cta}\n\n{tags}")
    return _strip_urls(
        f"Something new from {brand_name}. Take a look and tell us what you think.\n\n{cta}\n\n{tags}"
    )


async def _generate_email_campaign(profile, media) -> dict[str, str] | None:
    """Draft a marketing email for this business.

    Returns {subject, preheader, bodyText, bodyHtml} or None if the model could
    not produce usable output. Never raises — a failed email must not take down
    the social post that shares the same automation run.
    """
    brand_name = getattr(profile, "name", None) or "the brand"
    description = (getattr(profile, "description", None) or "").strip()
    website = getattr(profile, "websiteUrl", None) or ""
    tone = getattr(profile, "toneOfVoice", None) or "direct and credible"
    audience = getattr(profile, "targetAudience", None) or ""
    industry = getattr(profile, "industry", None) or getattr(profile, "businessModel", None) or ""
    asset_prompt = (getattr(media, "prompt", None) or "").strip() if media else ""

    known = [f"Business: {brand_name}"]
    if description: known.append(f"What it does (from their own site): {description}")
    if website:     known.append(f"Website: {website}")
    if industry:    known.append(f"Industry: {industry}")
    if audience:    known.append(f"Audience: {audience}")
    known.append(f"Tone: {tone}")
    if asset_prompt: known.append(f"This campaign's visual shows: {asset_prompt[:400]}")

    system_prompt = (
        "You are a B2B email copywriter. You write short, specific emails that get "
        "replies. You never invent facts, offers, metrics or customer names. You do "
        "not write like a newsletter template."
    )

    prompt = (
        "Write one marketing email for the business below.\n\n"
        "=== THE BUSINESS ===\n" + "\n".join(known) + "\n\n"
        "=== REQUIREMENTS ===\n"
        "- Subject line: under 55 characters, specific, no clickbait, no emoji\n"
        "- Preheader: one line that adds to the subject rather than repeating it\n"
        "- Body: 90-160 words, plain text, short paragraphs\n"
        "- It must be clear what this company actually does\n"
        "- Lead with the reader's problem, not the company\n"
        "- Exactly one call to action\n"
        "- No 'Dear valued customer', no 'I hope this email finds you well'\n"
        "- Invent nothing: no statistics, discounts, testimonials or deadlines\n\n"
        "Return ONLY valid JSON:\n"
        '{"subject": "...", "preheader": "...", "body": "..."}'
    )

    try:
        from services.ai_service import _call_openrouter, _parse_json_response
        raw = await _call_openrouter(prompt, system_prompt=system_prompt, json_response=True)
        data = _parse_json_response(raw) or {}
        subject = (data.get("subject") or "").strip()
        body = (data.get("body") or "").strip()
        preheader = (data.get("preheader") or "").strip()
        if not subject or not body:
            logger.warning("Email generation returned incomplete JSON")
            return None

        paragraphs = "".join(
            f"<p style='margin:0 0 16px;line-height:1.6;color:#111'>{p.strip()}</p>"
            for p in body.split("\n") if p.strip()
        )
        body_html = (
            "<div style=\"font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;"
            "max-width:560px;margin:0 auto;padding:24px;font-size:15px\">"
            f"{paragraphs}"
            f"<p style='margin:24px 0 0;font-size:12px;color:#888'>{brand_name}"
            f"{' &middot; ' + website if website else ''}</p></div>"
        )
        return {"subject": subject[:200], "preheader": preheader, "bodyText": body, "bodyHtml": body_html}
    except Exception as e:
        logger.warning(f"Email generation failed: {e}")
        return None


@router.post("/run-automation")
async def run_automation_manually(
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Manually run automation to generate a social post synchronously based on settings."""
    workspace_id = request.headers.get("x-workspace-id")

    # A run writes a caption with a paid AI call and may publish. Both are
    # metered, so check before doing any of the work.
    from services import billing_service as billing
    allowed, why = await billing.check_quota(user_id, "posts")
    if not allowed:
        raise HTTPException(status_code=402, detail=why)

    try:
        async with get_tenant_session(workspace_id) as session:
            # 1. Read the automation state through the one deterministic path,
            #    so this agrees with what the dashboard toggle wrote.
            state_stmt = (
                select(MarketingState)
                .where(MarketingState.businessProfileId == workspace_id)
                .order_by(MarketingState.createdAt.asc())
            )
            state = (await session.execute(state_stmt)).scalars().first()
            auto_approve = bool(state.autoApprove) if state else False

            # 2. Pick a media asset from this workspace's catalog, least
            #    recently used first, so every asset is published before any
            #    asset repeats.
            media_stmt = (
                select(Media)
                .where(Media.businessProfileId == workspace_id)
                .order_by(Media.createdAt.desc())
            )
            all_media = (await session.execute(media_stmt)).scalars().all()
            postable = [m for m in all_media if _is_postable(m)]

            if not postable:
                # Distinguish "nothing here" from "nothing here that can be
                # posted" — they need different actions from the user.
                if all_media:
                    return {
                        "success": False,
                        "message": (
                            "This catalog only contains prompt notes or deactivated "
                            "assets. Upload an image or video, or render one in AI "
                            "Video Studio, before running automation."
                        ),
                    }
                return {
                    "success": False,
                    "message": "No media in this business's catalog yet. Upload something, or generate a creative first.",
                }

            # Random selection repeated assets by birthday collision — with a
            # six-asset catalog, better than even odds of a repeat within four
            # posts, which is what the timeline was showing.
            from services.media_rotation import select_next_media

            chosen = await select_next_media(session, workspace_id)
            if chosen is None:
                chosen = postable[0]
            media_url = chosen.url

            # 3. Write a real caption from the brand profile and this asset.
            profile = await session.get(BusinessProfile, workspace_id)
            caption = await _generate_post_caption(profile, chosen)

            media_urls = [media_url] if media_url else []

            # 4. With auto-approve on, actually publish. This previously set
            #    status="POSTED" without calling the platform APIs at all, so
            #    the log claimed success while nothing ever reached Facebook or
            #    Instagram.
            fb_post_id = ig_post_id = None
            errors: list[str] = []
            posted_at = None

            if auto_approve:
                try:
                    ig_post_id = await post_to_instagram(workspace_id, message=caption, media_urls=media_urls)
                    if not ig_post_id:
                        errors.append("IG: publish returned no post id")
                except Exception as e:
                    errors.append(f"IG: {e}")

                try:
                    fb_post_id = await post_to_facebook(workspace_id, message=caption, media_urls=media_urls)
                    if not fb_post_id:
                        errors.append("FB: publish returned no post id")
                except Exception as e:
                    errors.append(f"FB: {e}")

            published = bool(fb_post_id or ig_post_id)
            if published:
                posted_at = datetime.now()

            if auto_approve:
                status = "POSTED" if published else "FAILED"
            else:
                status = "DRAFT"

            new_post = SocialPost(
                businessProfileId=workspace_id,
                # This run publishes to Facebook AND Instagram, but the row was
                # labelled INSTAGRAM. Retrying it from Edit/Preview reads this
                # field to decide where to send, so Facebook was silently
                # skipped on every retry.
                platform="BOTH",
                type="AUTO",
                caption=caption,
                mediaUrls=media_urls,
                scheduledAt=datetime.now(),
                status=status,
                fbPostId=fb_post_id,
                igPostId=ig_post_id,
                postedAt=posted_at,
                errorLog=" | ".join(errors) if errors else None,
            )
            session.add(new_post)
            await billing.record_usage(user_id, "posts")

            # 5. Log what actually happened, not what was intended
            if not auto_approve:
                log_note = "Manual run — caption generated, queued as draft for review"
            elif published:
                log_note = f"Manual run — published (fb={bool(fb_post_id)}, ig={bool(ig_post_id)})"
            else:
                log_note = f"Manual run — publish failed: {' | '.join(errors) or 'unknown error'}"

            # 6. Draft an email campaign from the same brand context. Always a
            #    DRAFT — sending to a real list is a separate, deliberate action.
            email_summary = None
            email_data = await _generate_email_campaign(profile, chosen)
            if email_data:
                audience_count = (await session.execute(
                    select(func.count(Audience.id)).where(
                        Audience.businessProfileId == workspace_id,
                        Audience.unsubscribed == False,  # noqa: E712
                    )
                )).scalar() or 0

                email = EmailCampaign(
                    businessProfileId=workspace_id,
                    status="DRAFT",
                    subject=email_data["subject"],
                    bodyText=email_data["bodyText"],
                    bodyHtml=email_data["bodyHtml"],
                    scheduledAt=datetime.now(),
                    recipientCount=audience_count,
                )
                session.add(email)
                email_summary = {
                    "subject": email_data["subject"],
                    "preheader": email_data.get("preheader", ""),
                    "recipientCount": audience_count,
                }
                log_note += f" | email drafted ({audience_count} recipients)"

            log = MarketingLog(
                businessProfileId=workspace_id,
                status="SUCCESS" if (published or not auto_approve) else "FAILED",
                socialSuccess=published,
                emailSuccess=bool(email_data),
                emailCount=1 if email_data else 0,
                errorLog=log_note,
            )
            session.add(log)
            
            await session.commit()
            await session.refresh(new_post)

        if new_post.status == "POSTED":
            message = "Published to your connected accounts."
        elif new_post.status == "FAILED":
            message = f"Caption generated, but publishing failed: {new_post.errorLog}"
        else:
            message = "Draft created. Turn on Auto-Approve to publish automatically."
        if email_summary:
            message += " An email campaign was drafted in Email Suite."

        return {
            "success": new_post.status != "FAILED",
            "message": message,
            "email": email_summary,
            "post": {
                "id": new_post.id,
                "platform": new_post.platform,
                "status": new_post.status,
                "caption": new_post.caption,
                "mediaUrls": new_post.mediaUrls,
                "errorLog": new_post.errorLog,
                "scheduledAt": new_post.scheduledAt.isoformat() if new_post.scheduledAt else None
            }
        }
    except Exception as e:
        logger.error(f"Error in manual run automation: {e}")
        try:
            workspace_id = request.headers.get('x-workspace-id')
            async with get_tenant_session(workspace_id) as session:
                log = MarketingLog(
                    businessProfileId=workspace_id,
                    status="FAILED",
                    socialSuccess=False,
                    errorLog=str(e),
                )
                session.add(log)
                await session.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Social Post Endpoints
# =============================================================================
@router.get("/posts")
async def get_social_posts(request: Request) -> Any:
    """List all social posts, newest first, with product data included."""
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        return []

    async with get_tenant_session(workspace_id) as session:
        stmt = select(SocialPost).where(SocialPost.businessProfileId == workspace_id).order_by(SocialPost.scheduledAt.desc())
        posts = (await session.execute(stmt)).scalars().all()
        # Return serialized format
        return [
            {
                "id": p.id,
                "platform": p.platform,
                "type": p.type,
                "status": p.status,
                "caption": p.caption,
                "mediaUrls": p.mediaUrls,
                "scheduledAt": p.scheduledAt.isoformat() if p.scheduledAt else None,
                "postedAt": p.postedAt.isoformat() if p.postedAt else None,
                # A FAILED row with no reason attached is undebuggable for the
                # user and for support. The reason was always recorded; it just
                # was never returned.
                "errorLog": p.errorLog,
                "fbPostId": p.fbPostId,
                "igPostId": p.igPostId,
            }
            for p in posts
        ]

@router.put("/posts/{post_id}")
async def edit_social_post(
    post_id: str, 
    request: Request,
    caption: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    scheduledAt: Optional[str] = Form(None),
    existing_media: List[str] = Form([]),
    files: List[UploadFile] = File(None)
) -> Any:
    """
    Edit an existing social post (SQLAlchemy).
    Supports updating caption, status, and modifying media (appending files or removing existing).
    """
    workspace_id = request.headers.get('x-workspace-id')
    async with get_tenant_session(workspace_id) as session:
        existing = await session.get(SocialPost, post_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Post not found")

        new_caption = caption

        # Check if we are publishing a draft or retrying a failed post
        publishing_draft = existing.status in ("DRAFT", "FAILED") and status == "POSTED"
        
        # Check if we are updating a live post's caption
        updating_live_caption = existing.status == "POSTED" and new_caption and existing.caption != new_caption

        # Process new file uploads
        new_media_urls: list[str] = []
        if files:
            import uuid
            for file in files:
                if file.filename:
                    file_content = await file.read()
                    media_id = str(uuid.uuid4())
                    
                    cloudinary_res = await upload_media_to_cloudinary(
                        workspace_id=workspace_id or "default",
                        media_id=media_id,
                        filename=file.filename,
                        source=file_content,
                        resource_type="auto"
                    )
                    
                    final_url = cloudinary_res["secure_url"] if cloudinary_res else f"/api/v1/media/{media_id}"
                    mime_type = file.content_type or "application/octet-stream"
                    
                    media = Media(
                        id=media_id,
                        userId=existing.userId,
                        businessProfileId=workspace_id,
                        filename=file.filename,
                        mimeType=mime_type,
                        url=final_url,
                        data=file_content if not cloudinary_res else None,
                    )
                    session.add(media)
                    
                    is_video_ext = mime_type.startswith("video/") or file.filename.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))
                    url_suffix = "?type=video" if is_video_ext else ""
                    
                    if final_url.startswith("http"):
                        new_media_urls.append(final_url)
                    else:
                        base_url = str(request.base_url).rstrip("/")
                        new_media_urls.append(f"{base_url}{final_url}{url_suffix}")

        cleaned_existing_media = []
        base_url_str = str(request.base_url).rstrip("/")
        for url in existing_media:
            parsed = urllib.parse.urlparse(url)
            # Re-host ONLY our own media route, which exists to repoint URLs
            # saved under a stale backend hostname. This previously rewrote
            # EVERY absolute URL, so a Cloudinary link like
            #   https://res.cloudinary.com/<cloud>/video/upload/.../reel.mp4
            # became
            #   https://<this-backend>/video/upload/.../reel.mp4
            # which 404s. Instagram and Facebook fetch the media themselves, so
            # publishing failed with an unfetchable-media error while the
            # automation path — which uses the stored URL untouched — worked.
            is_own_media_route = parsed.path.startswith("/api/v1/media/")

            if parsed.netloc and is_own_media_route:
                url = f"{base_url_str}{parsed.path}"
                if parsed.query:
                    url += f"?{parsed.query}"
            elif not parsed.netloc:
                # A stored relative path. Meta fetches media itself, so it must
                # be absolute or the publish fails.
                url = f"{base_url_str}{url if url.startswith('/') else '/' + url}"

            # ?type=video only means anything to our own media route — it tells
            # that endpoint which content type to serve. Appending it to a CDN
            # URL is at best noise and at worst breaks a signed link.
            if is_own_media_route and url.lower().split("?")[0].endswith(
                (".mp4", ".mov", ".webm", ".avi", ".mkv")
            ):
                if "type=video" not in url.lower():
                    url += "&type=video" if "?" in url else "?type=video"
            cleaned_existing_media.append(url)

        # Combine existing media we want to keep with new media
        final_media_urls = cleaned_existing_media + new_media_urls

        if publishing_draft:
            fb_post_id, ig_post_id = None, None
            errors: list[str] = []
            platform = existing.platform
            media_urls = final_media_urls

            caption_to_post = new_caption or existing.caption or ""

            if platform in ("FACEBOOK", "BOTH"):
                try:
                    fb_post_id = await post_to_facebook(workspace_id, message=caption_to_post, media_urls=media_urls)
                    if not fb_post_id:
                        errors.append("FB: Post returned None")
                except Exception as e:
                    errors.append(f"FB: {str(e)}")

            if platform in ("INSTAGRAM", "BOTH"):
                try:
                    ig_post_id = await post_to_instagram(workspace_id, message=caption_to_post, media_urls=media_urls)
                    if not ig_post_id:
                        errors.append("IG: Post returned None")
                except Exception as e:
                    errors.append(f"IG: {str(e)}")

            if platform == "BOTH":
                is_success = fb_post_id is not None and ig_post_id is not None
            elif platform == "FACEBOOK":
                is_success = fb_post_id is not None
            elif platform == "INSTAGRAM":
                is_success = ig_post_id is not None
            else:
                is_success = False
            
            # Apply changes
            existing.status = "POSTED" if is_success else "FAILED"
            existing.fbPostId = fb_post_id
            existing.igPostId = ig_post_id
            existing.errorLog = " | ".join(errors) if errors else None
            if is_success:
                existing.postedAt = datetime.now()

        elif updating_live_caption:
            if existing.fbPostId:
                try:
                    await update_facebook_post(existing.fbPostId, new_caption)
                except Exception as e:
                    logger.warning(f"Failed to update FB post: {e}")
            if existing.igPostId:
                try:
                    await update_instagram_post(existing.igPostId, new_caption)
                except Exception as e:
                    logger.warning(f"Failed to update IG post: {e}")

        # Apply fields
        existing.mediaUrls = final_media_urls
        if caption is not None:
            existing.caption = caption
        if status is not None and not publishing_draft:
            existing.status = status
        if scheduledAt:
            existing.scheduledAt = datetime.fromisoformat(
                scheduledAt.replace("Z", "+00:00")
            )

        await session.commit()
        await session.refresh(existing)

        return {
            "id": existing.id,
            "platform": existing.platform,
            "status": existing.status,
            "caption": existing.caption,
            "mediaUrls": existing.mediaUrls,
            "scheduledAt": existing.scheduledAt.isoformat() if existing.scheduledAt else None,
            "postedAt": existing.postedAt.isoformat() if existing.postedAt else None,
        }

@router.post("/posts/generate-caption")
async def api_generate_caption(
    request: Request,
    product_id: str = Form(...),
) -> dict[str, Any]:
    """Generate an AI caption for a campaign without creating a post."""
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:
        campaign = await session.get(SocialCampaign, product_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if workspace_id and campaign.businessProfileId and campaign.businessProfileId != workspace_id:
            raise HTTPException(status_code=403, detail="That campaign belongs to another business")

        caption = await generate_campaign_variation(campaign.baseCaption)
        return {"success": True, "caption": _strip_urls(caption)}


@router.post("/posts/manual")
async def create_manual_social_post(
    request: Request,
    platform: str = Form("BOTH"),
    generate_ai_caption: str = Form("false"),
    product_id: Optional[str] = Form(None),
    manual_caption: Optional[str] = Form(""),
    status: str = Form("DRAFT"),
    files: List[UploadFile] = File(None),
) -> dict[str, Any]:
    """Manual override: create — and optionally publish — a social post.

    Media goes to Cloudinary so the URL is publicly fetchable; Instagram
    rejects anything it cannot download, and the previous local-disk path
    produced URLs that died with the container.
    """
    workspace_id = request.headers.get("x-workspace-id")

    # 1. Upload any attached media.
    media_urls: list[str] = []
    if files:
        for file in files:
            if not file or not file.filename:
                continue
            content = await file.read()
            if not content:
                continue
            media_id = str(uuid.uuid4())
            uploaded = await upload_media_to_cloudinary(
                workspace_id=workspace_id or "default",
                media_id=media_id,
                filename=file.filename,
                source=content,
                resource_type="auto",
            )
            if uploaded:
                media_urls.append(uploaded["secure_url"])
            else:
                # No Cloudinary configured — fall back to local disk so the
                # post still carries media rather than silently losing it.
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                safe_name = os.path.basename(file.filename)
                path = os.path.join(UPLOAD_DIR, f"{media_id}_{safe_name}")
                with open(path, "wb") as buffer:
                    buffer.write(content)
                base_url = str(request.base_url).rstrip("/")
                url = f"{base_url}/uploads/{media_id}_{safe_name}"
                is_video_ext = safe_name.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))
                if (file.content_type or "").startswith("video/") or is_video_ext:
                    url += "?type=video"
                media_urls.append(url)

    async with get_tenant_session(workspace_id) as session:
        # 2. Resolve the campaign and settle on a caption.
        campaign = None
        if product_id:
            campaign = await session.get(SocialCampaign, product_id)
            if campaign and workspace_id and campaign.businessProfileId \
                    and campaign.businessProfileId != workspace_id:
                raise HTTPException(status_code=403, detail="That campaign belongs to another business")
            if campaign and not media_urls and campaign.mediaUrl:
                media_urls.append(campaign.mediaUrl)

        caption = manual_caption or ""
        if generate_ai_caption.lower() == "true" and campaign:
            caption = await generate_campaign_variation(campaign.baseCaption)

        # Captions never carry links — Instagram does not make them clickable.
        caption = _strip_urls(caption)

        # 3. Record the post.
        post = SocialPost(
            businessProfileId=workspace_id,
            campaignId=campaign.id if campaign else None,
            platform=platform,
            type="MANUAL",
            caption=caption,
            mediaUrls=media_urls,
            scheduledAt=utc_now(),
            status=status,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        post_data = {
            "id": post.id,
            "platform": post.platform,
            "status": post.status,
            "caption": post.caption,
            "mediaUrls": post.mediaUrls,
            "scheduledAt": post.scheduledAt.isoformat() if post.scheduledAt else None,
            "postedAt": post.postedAt.isoformat() if post.postedAt else None,
        }

        if status == "DRAFT":
            return {"success": True, "post": post_data, "errors": []}

        # 4. Publish.
        errors: list[str] = []
        fb_post_id = ig_post_id = None

        if platform in ("FACEBOOK", "BOTH"):
            try:
                fb_post_id = await post_to_facebook(workspace_id, message=caption, media_urls=media_urls)
                if not fb_post_id:
                    errors.append("FB: publish returned no post id")
            except Exception as e:
                errors.append(f"FB: {e}")

        if platform in ("INSTAGRAM", "BOTH"):
            try:
                ig_post_id = await post_to_instagram(workspace_id, message=caption, media_urls=media_urls)
                if not ig_post_id:
                    errors.append("IG: publish returned no post id")
            except Exception as e:
                errors.append(f"IG: {e}")

        if platform == "BOTH":
            # Either platform succeeding is a real delivery; requiring both
            # marked half-delivered posts FAILED and hid the one that worked.
            is_success = fb_post_id is not None or ig_post_id is not None
        elif platform == "FACEBOOK":
            is_success = fb_post_id is not None
        elif platform == "INSTAGRAM":
            is_success = ig_post_id is not None
        else:
            is_success = False

        post.status = "POSTED" if is_success else "FAILED"
        post.postedAt = utc_now() if is_success else None
        post.errorLog = " | ".join(errors) if errors else None
        post.fbPostId = fb_post_id
        post.igPostId = ig_post_id
        await session.commit()

        post_data["status"] = post.status
        post_data["postedAt"] = post.postedAt.isoformat() if post.postedAt else None
        return {"success": is_success, "post": post_data, "errors": errors}

class PostFromMediaRequest(BaseModel):
    mediaId: Optional[str] = None
    mediaUrl: Optional[str] = None
    customCaption: Optional[str] = None
    platform: str = "BOTH"
    status: str = "POSTED"

@router.post("/posts/from-media")
async def create_post_from_media(
    data: PostFromMediaRequest,
    request: Request,
) -> dict[str, Any]:
    """Create and publish a social post directly from a Media Library asset."""
    workspace_id = request.headers.get("x-workspace-id")
    
    async with get_tenant_session(workspace_id) as session:
        target_url = data.mediaUrl
        target_tags = []

        if data.mediaId:
            media_item = await session.get(Media, data.mediaId)
            if media_item:
                target_url = media_item.url
                target_tags = media_item.tags or []

        if not target_url:
            raise HTTPException(status_code=400, detail="Either mediaId or mediaUrl must be provided")

        # Determine caption
        caption = data.customCaption
        if not caption:
            # Generate AI caption based on workspace profile
            profile = None
            if workspace_id:
                profile = await session.get(BusinessProfile, workspace_id)
            
            biz_name = profile.name if profile else "Our Brand"
            topic = target_tags[0] if target_tags else "Feature Highlight"
            base_prompt = f"Automated social post for {biz_name}. Topic: {topic}. High engagement, emojis, hashtags."
            caption = await generate_campaign_variation(base_prompt)

        # Create SocialPost draft
        post = SocialPost(
            businessProfileId=workspace_id,
            platform=data.platform,
            type="MEDIA_CATALOG",
            caption=caption,
            mediaUrls=[target_url],
            scheduledAt=datetime.now(),
            status="DRAFT" if data.status == "DRAFT" else "POSTED",
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        if data.status == "DRAFT":
            return {"success": True, "post": {"id": post.id, "caption": post.caption, "mediaUrls": post.mediaUrls, "status": "DRAFT"}}

        # Post to Facebook & Instagram & Twitter & LinkedIn
        fb_post_id, ig_post_id = None, None
        errors = []

        if data.platform in ("FACEBOOK", "BOTH"):
            try:
                fb_post_id = await post_to_facebook(workspace_id, message=caption, media_urls=[target_url])
            except Exception as e:
                errors.append(f"FB: {str(e)}")

        if data.platform in ("INSTAGRAM", "BOTH"):
            try:
                ig_post_id = await post_to_instagram(workspace_id, message=caption, media_urls=[target_url])
            except Exception as e:
                errors.append(f"IG: {str(e)}")

        # Update post record
        post.status = "POSTED" if not errors or fb_post_id or ig_post_id else "FAILED"
        post.postedAt = datetime.now()
        post.fbPostId = fb_post_id
        post.igPostId = ig_post_id
        post.errorLog = " | ".join(errors) if errors else None
        await session.commit()

        return {
            "success": True,
            "post": {
                "id": post.id,
                "caption": post.caption,
                "mediaUrls": post.mediaUrls,
                "status": post.status,
            },
            "errors": errors,
        }

# =============================================================================
# Email Campaign Endpoints
# =============================================================================
class EmailConfigUpdate(BaseModel):
    provider: str = "resend"
    apiKey: Optional[str] = None      # blank on edit = keep the existing key
    fromEmail: str
    fromName: Optional[str] = None
    replyTo: Optional[str] = None


@router.get("/email-config")
async def get_email_config(request: Request) -> dict[str, Any]:
    """Whether this business can send email, and from where.

    Never returns the key itself — not even encrypted. The client only needs
    to know whether one is set.
    """
    from config import settings
    from database import EmailConfig

    workspace_id = request.headers.get("x-workspace-id")
    global_ready = bool(
        settings.resend_api_key and "your_resend" not in (settings.resend_api_key or "")
    )

    if not workspace_id:
        return {"success": True, "configured": global_ready, "usingPlatformDefault": global_ready}

    async with get_tenant_session(workspace_id) as session:
        cfg = (await session.execute(
            select(EmailConfig).where(EmailConfig.businessProfileId == workspace_id)
        )).scalars().first()

    if cfg:
        return {
            "success": True,
            "configured": True,
            "usingPlatformDefault": False,
            "provider": cfg.provider,
            "fromEmail": cfg.fromEmail,
            "fromName": cfg.fromName,
            "replyTo": cfg.replyTo,
            "hasKey": bool(cfg.apiKey),
            "lastError": cfg.lastError,
        }

    return {
        "success": True,
        "configured": global_ready,
        "usingPlatformDefault": global_ready,
        "provider": "resend",
        "fromEmail": None,
        "hasKey": False,
    }


@router.post("/email-config")
async def save_email_config(
    data: EmailConfigUpdate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> dict[str, Any]:
    """Store this business's own sending credentials, key encrypted at rest."""
    from database import EmailConfig
    from services.crypto_service import encrypt_token

    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Select a business first.")

    sender = (data.fromEmail or "").strip()
    if "@" not in sender or "." not in sender.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid sender email address.")

    async with get_tenant_session(workspace_id) as session:
        cfg = (await session.execute(
            select(EmailConfig).where(EmailConfig.businessProfileId == workspace_id)
        )).scalars().first()

        if not cfg:
            if not data.apiKey:
                raise HTTPException(
                    status_code=400,
                    detail="An API key is required the first time you connect email.",
                )
            cfg = EmailConfig(
                userId=user_id,
                businessProfileId=workspace_id,
                apiKey=encrypt_token(data.apiKey),
                fromEmail=sender,
            )
            session.add(cfg)
        elif data.apiKey:
            # Blank means "keep the current key" so the form never needs it back.
            cfg.apiKey = encrypt_token(data.apiKey)

        cfg.provider = data.provider or "resend"
        cfg.fromEmail = sender
        cfg.fromName = (data.fromName or "").strip() or None
        cfg.replyTo = (data.replyTo or "").strip() or None
        cfg.lastError = None

        await session.commit()

    logger.info(f"Email sending configured for workspace {workspace_id} as {sender}")
    return {"success": True, "message": f"Email connected. Campaigns will send from {sender}."}


@router.get("/emails")
async def get_email_campaigns(request: Request) -> Any:
    """List all email campaigns, newest first."""
    workspace_id = request.headers.get("x-workspace-id")
    if not workspace_id:
        return []

    async with get_tenant_session(workspace_id) as session:
        stmt = select(EmailCampaign).where(EmailCampaign.businessProfileId == workspace_id).order_by(EmailCampaign.scheduledAt.desc())
        emails = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": e.id,
                "status": e.status,
                "subject": e.subject,
                # The body was always stored and never returned, so the UI
                # could not preview or edit a draft before sending it.
                "bodyText": e.bodyText,
                "bodyHtml": e.bodyHtml,
                "errorLog": e.errorLog,
                "type": getattr(e, "type", "AUTOMATED"),
                "scheduledAt": e.scheduledAt.isoformat() if e.scheduledAt else None,
                "sentAt": e.sentAt.isoformat() if e.sentAt else None,
                "recipientCount": e.recipientCount,
                "openRate": e.openRate,
                "clickRate": e.clickRate,
                "createdAt": e.createdAt.isoformat() if e.createdAt else None,
            }
            for e in emails
        ]

@router.put("/emails/{campaign_id}")
async def edit_email_campaign(
    campaign_id: str,
    data: EmailCampaignUpdate,
    request: Request,
    user_id: str = Depends(verify_user),
) -> Any:
    """Edit an existing email campaign record (SQLAlchemy). If publishing a draft, send the email."""
    from services import billing_service as billing

    workspace_id = request.headers.get('x-workspace-id')
    async with get_tenant_session(workspace_id) as session:
        existing = await session.get(EmailCampaign, campaign_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if workspace_id and existing.businessProfileId and existing.businessProfileId != workspace_id:
            raise HTTPException(status_code=403, detail="That campaign belongs to another business")

        publishing_draft = existing.status in ("DRAFT", "FAILED") and data.status == "SENT"

        if publishing_draft:
            # Emails are metered per recipient, so reserve against the size of
            # the list rather than counting the campaign as one send.
            recipients = (await session.execute(
                select(func.count(Audience.id)).where(
                    Audience.businessProfileId == workspace_id,
                    Audience.unsubscribed == False,  # noqa: E712
                )
            )).scalar() or 0
            allowed, why = await billing.check_quota(user_id, "emails", max(recipients, 1))
            if not allowed:
                raise HTTPException(status_code=402, detail=why)

        if data.subject is not None:
            existing.subject = data.subject
        if data.bodyText is not None:
            existing.bodyText = data.bodyText
        if data.bodyHtml is not None:
            existing.bodyHtml = data.bodyHtml
        if data.status is not None and not publishing_draft:
            existing.status = data.status
        if data.scheduledAt:
            existing.scheduledAt = datetime.fromisoformat(
                data.scheduledAt.replace("Z", "+00:00")
            )

        if publishing_draft:
            # Trigger sending the email
            subject = data.subject or existing.subject
            body_html = data.bodyHtml or existing.bodyHtml
            body_text = data.bodyText or existing.bodyText
            
            try:
                # The keywords here were html_body/text_body, which this
                # function does not accept — every send raised TypeError and
                # was swallowed into a FAILED status. The count key was wrong
                # too, so recipientCount was always 0.
                result = await send_email_blast(
                    subject=subject,
                    body_html=body_html,
                    body_text=body_text,
                    workspace_id=workspace_id,
                )
                is_success = result.get("success", False)
                recipient_count = result.get("sent_count", 0)
                error_log = result.get("error")

                existing.status = "SENT" if is_success else "FAILED"
                existing.sentAt = datetime.now() if is_success else None
                existing.recipientCount = recipient_count
                existing.errorLog = error_log

                # Charge for what actually left, not what was attempted.
                if recipient_count:
                    await billing.record_usage(user_id, "emails", recipient_count)
            except Exception as e:
                existing.status = "FAILED"
                existing.errorLog = str(e)

        await session.commit()
        await session.refresh(existing)

        return {
            "id": existing.id,
            "status": existing.status,
            "subject": existing.subject,
            "scheduledAt": existing.scheduledAt.isoformat() if existing.scheduledAt else None,
            "sentAt": existing.sentAt.isoformat() if existing.sentAt else None,
            # Without this a failed send returned 200 with no explanation, so
            # the UI could only say "something went wrong".
            "errorLog": existing.errorLog,
            "recipientCount": existing.recipientCount,
        }

@router.post("/emails/manual")
async def create_manual_email(
    data: ManualEmailRequest, request: Request
) -> dict[str, Any]:
    """
    Manual Override: Create and send an email campaign (SQLAlchemy).
    Can either use manual content or AI-generate content from a product.
    """
    subject = data.manualSubject
    body_html = data.manualBodyHtml
    body_text = data.manualBodyText

    social_campaign = None

    workspace_id = request.headers.get('x-workspace-id')
    async with get_tenant_session(workspace_id) as session:
        if data.productId:
            social_campaign = await session.get(SocialCampaign, data.productId)

        # Generate AI email content if requested
        if data.generateAiEmail and social_campaign:
            ai_content = await generate_campaign_email(social_campaign)
            subject = ai_content.get("subject", subject)
            body_html = ai_content.get("bodyHtml", body_html)
            body_text = ai_content.get("bodyText", body_text)

        # Create campaign record
        workspace_id = request.headers.get("x-workspace-id")
        campaign = EmailCampaign(
            businessProfileId=workspace_id,
            campaignId=social_campaign.id if social_campaign else None,
            type="MANUAL",
            subject=subject,
            bodyText=body_text,
            bodyHtml=body_html,
            scheduledAt=datetime.now(),
            status="DRAFT",
        )
        session.add(campaign)
        await session.commit()
        await session.refresh(campaign)

        campaign_data = {
            "id": campaign.id,
            "subject": campaign.subject,
            "status": campaign.status,
        }

        # Send via Resend
        try:
            result = await send_email_blast(
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                workspace_id=workspace_id,
            )
            is_success = result.get("success", False)
            recipient_count = result.get("sent_count", 0)
            error_log = result.get("error")

            campaign.status = "SENT" if is_success else "FAILED"
            campaign.sentAt = datetime.now() if is_success else None
            campaign.recipientCount = recipient_count
            campaign.errorLog = error_log
            await session.commit()

            campaign_data["status"] = campaign.status
            return {"success": is_success, "campaign": campaign_data}

        except Exception as e:
            campaign.status = "FAILED"
            campaign.errorLog = str(e)
            await session.commit()
            raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Audiences, Logs & Media
# =============================================================================
class AudienceCreate(BaseModel):
    email: str
    name: Optional[str] = None
    source: Optional[str] = "manual"
    tags: Optional[List[str]] = []

@router.get("/audiences")
async def get_audiences(request: Request) -> Any:
    """List audience subscribers for the active workspace."""
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:
        stmt = select(Audience).where(Audience.businessProfileId == workspace_id).order_by(Audience.createdAt.desc())
        audiences = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": a.id,
                "email": a.email,
                "name": a.name,
                "source": a.source,
                "unsubscribed": a.unsubscribed,
                "tags": a.tags,
                "createdAt": a.createdAt.isoformat() if a.createdAt else None,
            }
            for a in audiences
        ]

@router.post("/audiences")
async def add_audience(data: AudienceCreate, request: Request) -> Any:
    """Add a new audience contact for the active workspace."""
    workspace_id = request.headers.get("x-workspace-id")
    auth_header = request.headers.get("Authorization")
    user_id = None
    if auth_header and auth_header.startswith("Bearer "):
        try:
            import jwt
            from config import settings
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
        except Exception:
            pass

    workspace_id = request.headers.get('x-workspace-id')
    async with get_tenant_session(workspace_id) as session:
        aud = Audience(
            userId=user_id or "default_user",
            businessProfileId=workspace_id,
            email=data.email,
            name=data.name,
            source=data.source or "manual",
            tags=data.tags or []
        )
        session.add(aud)
        await session.commit()
        await session.refresh(aud)
        return {"success": True, "data": {"id": aud.id, "email": aud.email}}

@router.get("/logs")
async def get_marketing_logs(request: Request) -> Any:
    """List audit and activity execution logs for the active workspace."""
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:
        stmt = select(MarketingLog).where(MarketingLog.businessProfileId == workspace_id).order_by(MarketingLog.createdAt.desc())
        logs = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": l.id,
                "status": l.status,
                "socialSuccess": l.socialSuccess,
                "emailSuccess": l.emailSuccess,
                "emailCount": l.emailCount,
                "errorLog": l.errorLog,
                "createdAt": l.createdAt.isoformat() if l.createdAt else None,
            }
            for l in logs
        ]

@router.get("/media")
async def get_workspace_media(request: Request) -> Any:
    """List media assets (uploaded and AI rendered) for the active workspace."""
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:
        if workspace_id:
            stmt = select(Media).where(Media.businessProfileId == workspace_id).order_by(Media.createdAt.desc())
        else:
            stmt = select(Media).order_by(Media.createdAt.desc())
        media_list = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": m.id,
                "filename": m.filename,
                "mimeType": m.mimeType,
                "url": m.url,
                "tags": m.tags,
                "aiGenerated": m.aiGenerated,
                "prompt": m.prompt,
                "promptType": m.promptType,
                # Fall back to the generation prompt so pre-migration assets
                # still show their description instead of a bare filename.
                "caption": m.caption or m.prompt,
                "isActive": m.isActive,
                "postable": _is_postable(m),
                "generationStatus": m.generationStatus,
                "generationError": m.generationError,
                "createdAt": m.createdAt.isoformat() if m.createdAt else None,
            }
            for m in media_list
        ]


async def _load_owned_media(session, media_id: str, workspace_id: str | None) -> Media:
    """Fetch a media row, refusing ids that belong to another workspace.

    Row-level security is not currently filtering, so an id alone must never be
    treated as proof of ownership.
    """
    media = await session.get(Media, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media asset not found")
    if workspace_id and media.businessProfileId and media.businessProfileId != workspace_id:
        raise HTTPException(status_code=403, detail="That asset belongs to another business")
    return media


@router.patch("/media/{media_id}")
async def update_workspace_media(
    media_id: str,
    request: Request,
    caption: Optional[str] = Form(None),
    isActive: Optional[bool] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> Any:
    """Update an asset's description, its active flag, or the file itself.

    The dashboard's Edit dialog previously only *claimed* to save — it showed a
    success toast and called nothing. Both the caption and the replacement file
    were thrown away.
    """
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:
        media = await _load_owned_media(session, media_id, workspace_id)

        if caption is not None:
            media.caption = caption.strip() or None

        if isActive is not None:
            media.isActive = isActive

        if file is not None and file.filename:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="The uploaded file was empty.")
            uploaded = await upload_media_to_cloudinary(
                workspace_id=media.businessProfileId or workspace_id or "default",
                media_id=media.id,
                filename=file.filename,
                source=content,
                resource_type="auto",
            )
            if uploaded:
                media.url = uploaded["secure_url"]
                media.data = None
            elif _cloudinary_configured():
                # Storage is set up but refused this file. Saying "saved" here
                # would leave an asset the social platforms cannot fetch.
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Your storage provider rejected this file — it is usually an "
                        "unsupported format or too large. Try an MP4 (H.264) or a JPG/PNG."
                    ),
                )
            else:
                # No object storage configured (local/dev). Keep the bytes so
                # the replacement still takes effect rather than no-oping.
                logger.warning(
                    "No Cloudinary configured; storing media %s locally. Facebook and "
                    "Instagram cannot fetch this URL.", media.id
                )
                media.url = f"/api/v1/media/{media.id}"
                media.data = content
            media.filename = file.filename
            media.mimeType = file.content_type or media.mimeType

        await session.commit()
        await session.refresh(media)
        return {
            "success": True,
            "media": {
                "id": media.id,
                "filename": media.filename,
                "mimeType": media.mimeType,
                "url": media.url,
                "caption": media.caption,
                "prompt": media.prompt,
                "promptType": media.promptType,
                "isActive": media.isActive,
                "postable": _is_postable(media),
            },
        }


@router.delete("/media/{media_id}")
async def delete_workspace_media(media_id: str, request: Request) -> Any:
    """Delete a media asset from the catalog."""
    workspace_id = request.headers.get('x-workspace-id')
    async with get_tenant_session(workspace_id) as session:
        media = await _load_owned_media(session, media_id, workspace_id)
        await session.delete(media)
        await session.commit()
        return {"success": True, "message": "Media asset deleted successfully"}


@router.post("/media/bulk-upload")
async def bulk_upload_media(
    request: Request,
    files: List[UploadFile] = File(...),
    write_captions: bool = Form(True),
    user_id: str = Depends(verify_user),
) -> Any:
    """Upload a whole folder of assets, each with a base caption.

    The base caption is what the post-caption writer reads to know what an
    asset shows. Filenames cannot supply it — a real folder is full of
    `handle_2025-12-23_DSnJoNaklOM_2.mp4` — so each asset is looked at: a frame
    is pulled from every video and described by the vision model.

    Partial success is normal on a large folder. Every file reports its own
    outcome rather than one failure aborting the batch.
    """
    from services.bulk_ingest import ingest_folder

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")

    if not files:
        raise HTTPException(status_code=400, detail="No files supplied")

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if not profile or profile.userId != user_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Read every file before the request body is closed.
        payload = [(f.filename or "upload", await f.read()) for f in files]

        result = await ingest_folder(
            payload, profile, user_id, workspace_id, write_captions=False
        )

        # Persist the ones that made it. Written in one transaction so a
        # storage success is never left without its catalog row.
        for item in result["items"]:
            if not item.get("ok"):
                continue
            session.add(Media(
                id=item["mediaId"],
                userId=user_id,
                businessProfileId=workspace_id,
                filename=item["filename"],
                mimeType=item["mimeType"],
                url=item["url"],
                caption=item.get("caption") or None,
                isActive=True,
            ))
        await session.commit()

    # Captioning runs AFTER the response. A frame extract plus a vision call
    # costs tens of seconds per asset and gunicorn kills the worker at
    # --timeout 120, so doing it inline made every batch of videos return 500.
    # The catalog is usable immediately and descriptions fill in behind it.
    stored_ids = [i["mediaId"] for i in result["items"] if i.get("ok")]
    if write_captions and stored_ids:
        from services.bulk_ingest import describe_pending_media
        from services.task_utils import spawn_background

        spawn_background(
            describe_pending_media(workspace_id, stored_ids, profile),
            f"describe_pending_media({workspace_id}, {len(stored_ids)})",
        )

    return {
        "success": True,
        "captioning": bool(write_captions and stored_ids),
        "message": (
            f"{result['stored']} of {result['total']} added"
            + (" — descriptions are being written now"
               if write_captions and stored_ids else "")
        ),
        **result,
    }
