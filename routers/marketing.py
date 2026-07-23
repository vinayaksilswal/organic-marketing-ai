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
from sqlalchemy import select, and_
from database import (
    AsyncSessionLocal,
    User,
    Audience,
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

from auth import verify_credentials
from services.ai_service import generate_campaign_email, generate_campaign_variation
from services.email_service import send_email_blast
from services.social_service import (
    post_to_facebook,
    post_to_instagram,
    update_facebook_post,
    update_instagram_post,
)
from services.scheduler import execute_marketing_loop

router = APIRouter(
    prefix="/marketing",
    tags=["Marketing"],
    dependencies=[Depends(verify_credentials)],
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
    async with AsyncSessionLocal() as session:
        workspace_id = request.headers.get("x-workspace-id")

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

@router.post("/settings/auto-approve")
async def toggle_auto_approve(
    data: AutoApproveUpdate, request: Request
) -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as session:
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
        async with AsyncSessionLocal() as session:
            workspace_id = request.headers.get("x-workspace-id")
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

@router.post("/run-automation")
async def run_automation_manually(request: Request) -> dict[str, Any]:
    """Run the marketing automation loop manually and create audit log."""
    workspace_id = request.headers.get("x-workspace-id")
    try:
        await execute_marketing_loop()

        # Create audit log entry
        async with AsyncSessionLocal() as session:
            log = MarketingLog(
                businessProfileId=workspace_id,
                status="SUCCESS",
                socialSuccess=True,
            )
            session.add(log)
            await session.commit()

        return {"success": True, "message": "Automation loop executed successfully."}
    except Exception as e:
        # Log failure
        try:
            async with AsyncSessionLocal() as session:
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

    async with AsyncSessionLocal() as session:
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
    async with AsyncSessionLocal() as session:
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
            for file in files:
                if file.filename:
                    file_location = os.path.join(UPLOAD_DIR, file.filename)
                    with open(file_location, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    
                    base_url = str(request.base_url).rstrip("/")
                    url = f"{base_url}/uploads/{file.filename}"
                    
                    is_video_ext = file.filename.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))
                    if (file.content_type and file.content_type.startswith("video/")) or is_video_ext:
                        url += "?type=video"
                        
                    new_media_urls.append(url)

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
                    fb_post_id = await post_to_facebook(message=caption_to_post, media_urls=media_urls)
                    if not fb_post_id:
                        errors.append("FB: Post returned None")
                except Exception as e:
                    errors.append(f"FB: {str(e)}")

            if platform in ("INSTAGRAM", "BOTH"):
                try:
                    ig_post_id = await post_to_instagram(message=caption_to_post, media_urls=media_urls)
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
    async with AsyncSessionLocal() as session:
        campaign = await session.get(SocialCampaign, product_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        caption = await generate_campaign_variation(campaign.baseCaption)
        return {"success": True, "caption": caption}


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
    """
    Manual Override: Create and publish a social media post (SQLAlchemy).

    Allows manual media uploads and optional AI caption generation.
    Overrides the automated scheduler flow.
    """
    # Handle file uploads
    media_urls: list[str] = []
    if files:
        for file in files:
            if file.filename:
                file_location = os.path.join(UPLOAD_DIR, file.filename)
                with open(file_location, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                base_url = str(request.base_url).rstrip("/")
                url = f"{base_url}/uploads/{file.filename}"
                
                is_video_ext = file.filename.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))
                if (file.content_type and file.content_type.startswith("video/")) or is_video_ext:
                    url += "?type=video"
                    
                media_urls.append(url)

    caption = manual_caption or ""
    campaign = None

    async with AsyncSessionLocal() as session:
        if product_id:
            campaign = await session.get(SocialCampaign, product_id)
            # If campaign found but no manual media, use campaign media
            if campaign and not media_urls:
                if campaign.mediaUrl:
                    media_urls.append(campaign.mediaUrl)

        # Generate AI caption if requested
        if generate_ai_caption.lower() == "true" and campaign:
            caption = await generate_campaign_variation(campaign.baseCaption)

        # Create the post record
        workspace_id = request.headers.get("x-workspace-id")
        post = SocialPost(
            businessProfileId=workspace_id,
            campaignId=campaign.id if campaign else None,
            platform=platform,
            type="MANUAL",
            caption=caption,
            mediaUrls=media_urls,
            scheduledAt=datetime.now(),
            status="DRAFT",
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
        }

        if status == "DRAFT":
            return {"success": True, "post": post_data, "errors": []}

        # Post to platforms
        fb_post_id, ig_post_id = None, None
        errors: list[str] = []

        if platform in ("FACEBOOK", "BOTH"):
            try:
                fb_post_id = await post_to_facebook(message=caption, media_urls=media_urls)
                if not fb_post_id:
                    errors.append("FB: Post returned None")
            except Exception as e:
                errors.append(f"FB: {str(e)}")

        if platform in ("INSTAGRAM", "BOTH"):
            try:
                ig_post_id = await post_to_instagram(message=caption, media_urls=media_urls)
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
    
    async with AsyncSessionLocal() as session:
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
                fb_post_id = await post_to_facebook(message=caption, media_urls=[target_url])
            except Exception as e:
                errors.append(f"FB: {str(e)}")

        if data.platform in ("INSTAGRAM", "BOTH"):
            try:
                ig_post_id = await post_to_instagram(message=caption, media_urls=[target_url])
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

    async with AsyncSessionLocal() as session:
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
    async with AsyncSessionLocal() as session:
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

    async with AsyncSessionLocal() as session:
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
    async with AsyncSessionLocal() as session:
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

    async with AsyncSessionLocal() as session:
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
    async with AsyncSessionLocal() as session:
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
    async with AsyncSessionLocal() as session:
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
                "createdAt": m.createdAt.isoformat() if m.createdAt else None,
            }
            for m in media_list
        ]

@router.delete("/media/{media_id}")
async def delete_workspace_media(media_id: str, request: Request) -> Any:
    """Delete a media asset from the catalog."""
    async with AsyncSessionLocal() as session:
        media = await session.get(Media, media_id)
        if not media:
            raise HTTPException(status_code=404, detail="Media asset not found")
        await session.delete(media)
        await session.commit()
        return {"success": True, "message": "Media asset deleted successfully"}
