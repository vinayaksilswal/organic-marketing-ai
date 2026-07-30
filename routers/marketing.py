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
import shutil
import urllib.parse
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

@router.get("/settings")
async def get_marketing_settings(request: Request) -> dict[str, Any]:
    workspace_id = request.headers.get("x-workspace-id")
    async with get_tenant_session(workspace_id) as session:
        stmt = select(MarketingState).where(MarketingState.businessProfileId == workspace_id)
        state = (await session.execute(stmt)).scalars().first()
        if state:
            return {
                "success": True, 
                "autoApprove": state.autoApprove, 
                "intervalHours": state.postIntervalHours
            }
        return {"success": True, "autoApprove": False, "intervalHours": 2}

@router.post("/settings/auto-approve")
async def toggle_auto_approve(
    data: AutoApproveUpdate, request: Request
) -> dict[str, Any]:
    try:
        workspace_id = request.headers.get('x-workspace-id')
        async with get_tenant_session(workspace_id) as session:
            stmt = select(MarketingState).where(MarketingState.businessProfileId == request.headers.get("x-workspace-id"))
            state = (await session.execute(stmt)).scalars().first()
            if state:
                state.autoApprove = data.autoApprove
            else:
                user_stmt = select(User)
                first_user = (await session.execute(user_stmt)).scalars().first()
                if first_user:
                    workspace_id = request.headers.get("x-workspace-id")
                    state = MarketingState(userId=first_user.id, businessProfileId=workspace_id, autoApprove=data.autoApprove)
                    session.add(state)
            if state:
                await session.commit()
                await session.refresh(state)

            return {"success": True, "autoApprove": state.autoApprove if state else False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class IntervalUpdate(BaseModel):
    intervalHours: int

@router.post("/settings/interval")
async def update_interval(data: IntervalUpdate, request: Request) -> dict[str, Any]:
    try:
        workspace_id = request.headers.get("x-workspace-id")
        async with get_tenant_session(workspace_id) as session:

            stmt = select(MarketingState).where(MarketingState.businessProfileId == workspace_id)
            state = (await session.execute(stmt)).scalars().first()
            if state:
                state.postIntervalHours = data.intervalHours
            else:
                user_stmt = select(User)
                first_user = (await session.execute(user_stmt)).scalars().first()
                if first_user:
                    state = MarketingState(userId=first_user.id, businessProfileId=workspace_id, postIntervalHours=data.intervalHours)
                    session.add(state)
            if state:
                await session.commit()
                return {"success": True, "intervalHours": state.postIntervalHours}
            return {"success": False, "message": "Could not update interval"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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


async def _generate_post_caption(profile, media) -> str:
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

    known = [f"Business name: {brand_name}"]
    if description: known.append(f"What it does (from their own site): {description}")
    if website:     known.append(f"Website: {website}")
    if industry:    known.append(f"Industry: {industry}")
    if niche:       known.append(f"Niche: {niche}")
    if audience:    known.append(f"Target audience: {audience}")
    if pillars:     known.append(f"Content themes: {', '.join(pillars)}")
    known.append(f"Tone of voice: {tone}")

    asset_lines = []
    if asset_caption:
        asset_lines.append(f"The visual shows: {asset_caption[:900]}")
    if asset_prompt and asset_prompt != asset_caption:
        asset_lines.append(f"It was generated from this brief: {asset_prompt[:600]}")
    if not asset_caption and not asset_prompt:
        # Be explicit rather than letting the model invent a scene.
        asset_lines.append(
            "No description of the visual is available — write about the "
            "business itself and do not describe what is on screen."
        )
    if asset_tags:   asset_lines.append(f"Asset tags: {asset_tags}")
    asset_lines.append(f"Format: {'short video / reel' if is_video else 'single image'}")

    system_prompt = (
        "You are an elite, enterprise-grade social media copywriter specializing in high-converting ads and organic content for top-tier brands. "
        "You craft compelling, persuasive, and authentic copy that drives engagement and action. You never invent facts, metrics, offers or features that "
        "were not explicitly provided."
    )

    prompt = (
        "Write ONE highly engaging, enterprise-grade social media caption for the post described below.\n\n"
        "=== THE BUSINESS ===\n" + "\n".join(known) + "\n\n"
        "=== THIS POST'S VISUAL ===\n" + "\n".join(asset_lines) + "\n\n"
        "=== REQUIREMENTS ===\n"
        "1. Structure the caption using a proven marketing framework (e.g., AIDA or PAS).\n"
        "2. Hook the reader immediately with a scroll-stopping first line. Never open with the brand name.\n"
        "3. Connect the message to the visual seamlessly, providing clear value.\n"
        "4. Keep it punchy, professional, yet approachable. Avoid overused buzzwords ('unlock', 'elevate', 'game-changer', 'revolutionize').\n"
        "5. Conclude with a singular, strong, and actionable Call-To-Action (CTA).\n"
        "6. Never put a URL in the caption — use 'link in bio' or similar if necessary.\n"
        "7. Invent nothing: no fake statistics, customer counts, or discounts.\n"
        "8. Final line: include 3-5 hyper-relevant industry hashtags. Do NOT use generic tags like #love or #instagood.\n\n"
        "Output ONLY the caption. No preamble, no quotes, no explanation."
    )

    try:
        from services.ai_service import _call_openrouter
        caption = (await _call_openrouter(prompt, system_prompt=system_prompt)).strip()
        # Models sometimes wrap output in quotes or add a lead-in line.
        if caption.startswith('"') and caption.endswith('"'):
            caption = caption[1:-1].strip()
        for lead in ("Caption:", "Here's the caption:", "Here is the caption:"):
            if caption.lower().startswith(lead.lower()):
                caption = caption[len(lead):].strip()
        if caption:
            return caption[:2200]  # Instagram's caption limit
        logger.warning(f"Caption generation returned empty for workspace {getattr(profile, 'id', '?')}")
    except Exception as e:
        logger.warning(f"Caption generation failed, using brand template: {e}")

    # Fallback still says something true about the business rather than filler.
    tags = " ".join(hashtags[:5]) if hashtags else "#b2b #technology"
    if description:
        first = description.split(".")[0].strip()
        return f"{first}.\n\nMore at {website or brand_name}.\n\n{tags}"
    return f"Something new from {brand_name}. Take a look and tell us what you think.\n\n{tags}"


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
async def run_automation_manually(request: Request) -> dict[str, Any]:
    """Manually run automation to generate a social post synchronously based on settings."""
    workspace_id = request.headers.get("x-workspace-id")
    try:
        async with get_tenant_session(workspace_id) as session:
            # 1. Check autoApprove setting
            state_stmt = select(MarketingState).where(MarketingState.businessProfileId == workspace_id)
            state = (await session.execute(state_stmt)).scalars().first()
            auto_approve = state.autoApprove if state else False
            interval_hours = state.postIntervalHours if state else 2
            
            # 2. Pick a media asset from this workspace's catalog. Prefer the
            #    least-recently-created so the rotation does not repeat one
            #    asset by chance the way random selection did.
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

            import random
            chosen = random.choice(postable)
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
                platform="INSTAGRAM",
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
            if parsed.netloc:
                url = f"{base_url_str}{parsed.path}"
                if parsed.query:
                    url += f"?{parsed.query}"
            
            # Ensure it has ?type=video if it's a video
            if url.lower().split("?")[0].endswith((".mp4", ".mov", ".webm", ".avi", ".mkv")):
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
    """Generates an AI caption for a given product ID without creating a post."""
    workspace_id = request.headers.get('x-workspace-id')
    async with get_tenant_session(workspace_id) as session:
                        media_urls.append(f"{base_url}{final_url}{url_suffix}")

        # 2. Setup Campaign and Caption
        campaign = None
        if product_id:
            campaign = await session.get(SocialCampaign, product_id)
            if campaign and not media_urls and campaign.mediaUrl:
                media_urls.append(campaign.mediaUrl)

        caption = manual_caption or ""
        if generate_ai_caption.lower() == "true" and campaign:
            caption = await generate_campaign_variation(campaign.baseCaption)
        
        import re
        caption = re.sub(r"http\S+", "", caption).strip()

        # 3. Create Record
        post = SocialPost(
            businessProfileId=workspace_id,
            campaignId=campaign.id if campaign else None,
            platform=platform,
            type="MANUAL",
            caption=caption,
            mediaUrls=media_urls,
            scheduledAt=datetime.now(),
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


        if platform in ("FACEBOOK", "BOTH"):
            try:
                fb_post_id = await post_to_facebook(workspace_id, message=caption, media_urls=media_urls)
                if not fb_post_id:
                    errors.append("FB: Post returned None")
            except Exception as e:
                errors.append(f"FB: {str(e)}")

        if platform in ("INSTAGRAM", "BOTH"):
            try:
                ig_post_id = await post_to_instagram(workspace_id, message=caption, media_urls=media_urls)
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

        # Update post record with results
        post.status = "POSTED" if is_success else "FAILED"
        post.postedAt = datetime.now() if is_success else None
        post.errorLog = " | ".join(errors) if errors else None
        post.fbPostId = fb_post_id
        post.igPostId = ig_post_id
        await session.commit()

        post_data["status"] = post.status
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
    campaign_id: str, data: EmailCampaignUpdate, request: Request
) -> Any:
    """Edit an existing email campaign record (SQLAlchemy). If publishing a draft, send the email."""
    workspace_id = request.headers.get('x-workspace-id')
    async with get_tenant_session(workspace_id) as session:
        existing = await session.get(EmailCampaign, campaign_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Campaign not found")

        publishing_draft = existing.status in ("DRAFT", "FAILED") and data.status == "SENT"

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
                result = await send_email_blast(
                    subject=subject,
                    html_body=body_html,
                    text_body=body_text,
                )
                is_success = result.get("success", False)
                recipient_count = result.get("count", 0)
                error_log = result.get("error")

                existing.status = "SENT" if is_success else "FAILED"
                existing.sentAt = datetime.now() if is_success else None
                existing.recipientCount = recipient_count
                existing.errorLog = error_log
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
                html_body=body_html,
                text_body=body_text,
            )
            is_success = result.get("success", False)
            recipient_count = result.get("count", 0)
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
            else:
                # No Cloudinary configured — keep the bytes locally so the
                # replacement still takes effect rather than silently no-oping.
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
