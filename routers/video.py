import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from database import AsyncSessionLocal, VideoApiConfig, Media, BusinessProfile
from routers.auth import verify_user, get_workspace_id
from sqlalchemy import select, and_

router = APIRouter(
    prefix="/api/v1/video",
    tags=["Video Studio"],
    dependencies=[Depends(verify_user)],
)

class VideoConfigUpdate(BaseModel):
    provider: str
    apiKey: str
    endpoint: Optional[str] = None

class GeneratePromptRequest(BaseModel):
    prompt: str
    provider: Optional[str] = "json2video"
    resolution: Optional[str] = "1080p"
    duration: Optional[Any] = 15

class RenderVideoRequest(BaseModel):
    provider: str
    payload: Dict[str, Any]
    prompt: str

@router.get("/config")
async def get_video_config(request: Request, user_id: str = Depends(verify_user), workspace_id: Optional[str] = Depends(get_workspace_id)):
    async with AsyncSessionLocal() as session:
        stmt = select(VideoApiConfig).where(and_(
            VideoApiConfig.userId == user_id,
            VideoApiConfig.businessProfileId == workspace_id
        ))
        res = await session.execute(stmt)
        config = res.scalars().first()
        if config:
            return {"success": True, "data": {"provider": config.provider, "apiKey": config.apiKey, "endpoint": config.endpoint}}
        return {"success": True, "data": {"provider": "json2video", "apiKey": "", "endpoint": ""}}

@router.post("/config")
async def save_video_config(data: VideoConfigUpdate, request: Request, user_id: str = Depends(verify_user), workspace_id: Optional[str] = Depends(get_workspace_id)):
    async with AsyncSessionLocal() as session:
        stmt = select(VideoApiConfig).where(and_(
            VideoApiConfig.userId == user_id,
            VideoApiConfig.businessProfileId == workspace_id
        ))
        res = await session.execute(stmt)
        config = res.scalars().first()
        if config:
            config.provider = data.provider
            config.apiKey = data.apiKey
            config.endpoint = data.endpoint
        else:
            config = VideoApiConfig(userId=user_id, businessProfileId=workspace_id, provider=data.provider, apiKey=data.apiKey, endpoint=data.endpoint)
            session.add(config)
        await session.commit()
        return {"success": True, "message": "Video API configuration saved successfully"}

@router.post("/generate-prompt")
async def generate_video_prompt(data: GeneratePromptRequest, request: Request, user_id: str = Depends(verify_user)):
    try:
        user_prompt = (data.prompt or "").strip()
        if not user_prompt:
            user_prompt = "High-converting product showcase video"
            
        provider = data.provider or "json2video"
        
        try:
            duration = int(data.duration) if data.duration is not None else 15
        except (ValueError, TypeError):
            duration = 15

        res_str = (data.resolution or "1080p").lower()
        res_format = "full-hd" if "1080" in res_str or "hd" in res_str else "square"

        # Build valid json2video payload structure
        if provider == "json2video":
            json_payload = {
                "resolution": res_format,
                "quality": "high",
                "fps": 30,
                "draft": False,
                "scenes": [
                    {
                        "comment": "Hook Scene",
                        "duration": min(5, max(3, duration // 3)),
                        "elements": [
                            {
                                "type": "text",
                                "text": f"🔥 {user_prompt[:45]}",
                                "style": "headline",
                                "font": "Outfit",
                                "size": 64,
                                "color": "#ffffff",
                                "position": "center",
                                "animation": "fade-in"
                            },
                            {
                                "type": "image",
                                "url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200",
                                "zoom": "in"
                            }
                        ]
                    },
                    {
                        "comment": "Core Message Scene",
                        "duration": max(4, duration - 7),
                        "elements": [
                            {
                                "type": "text",
                                "text": "Enterprise Performance & Scale",
                                "style": "subheading",
                                "font": "Inter",
                                "size": 42,
                                "color": "#a855f7",
                                "position": "bottom-center"
                            },
                            {
                                "type": "video",
                                "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
                                "volume": 0.8
                            }
                        ]
                    },
                    {
                        "comment": "Call to Action Scene",
                        "duration": min(4, max(2, duration // 4)),
                        "elements": [
                            {
                                "type": "text",
                                "text": "Get Started Today 🚀",
                                "style": "cta",
                                "font": "Outfit",
                                "size": 52,
                                "color": "#10b981",
                                "position": "center"
                            }
                        ]
                    }
                ],
                "audio": {
                    "url": "https://cdn.pixabay.com/audio/2022/05/27/audio_1808fbf07a.mp3",
                    "volume": 0.5
                }
            }
        else:
            json_payload = {
                "provider": provider,
                "prompt": f"Professional high-converting promo video: {user_prompt}",
                "negative_prompt": "blurry, low quality, distorted text, watermark",
                "aspect_ratio": "16:9" if res_format == "full-hd" else "1:1",
                "motion": 5,
                "camera_control": "pan_right",
                "seed": 421908
            }

        return {
            "success": True,
            "prompt": f"Enhanced Cinematic Prompt: {user_prompt} --style modern-enterprise --fps 30",
            "json": json_payload
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate video prompt: {str(e)}")

@router.post("/render")
async def render_video(data: RenderVideoRequest, request: Request, user_id: str = Depends(verify_user), workspace_id: Optional[str] = Depends(get_workspace_id)):
    import httpx
    try:
        # Retrieve user's video API config
        async with AsyncSessionLocal() as session:
            stmt = select(VideoApiConfig).where(and_(
                VideoApiConfig.userId == user_id,
                VideoApiConfig.businessProfileId == workspace_id
            ))
            res = await session.execute(stmt)
            config = res.scalars().first()
            
            from config import settings
            
            if not config or not config.apiKey:
                if settings.json2video_api_key:
                    api_key = settings.json2video_api_key
                else:
                    raise HTTPException(status_code=400, detail="Missing json2video API key. Please configure it in settings.")
            else:
                api_key = config.apiKey
            
        if data.provider != "json2video":
            raise HTTPException(status_code=400, detail="Only json2video is currently supported.")
            
        # Post to JSON2Video API
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.json2video.com/v2/movies", json=data.payload, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"json2video API error: {response.text}")
                
            resp_data = response.json()
            project_url = resp_data.get("project", {}).get("url", "")
            job_id = resp_data.get("project", {}).get("id", str(uuid.uuid4()))
            
        # Optional: Save a placeholder Media object to DB, though standard practice is polling/webhooks
        async with AsyncSessionLocal() as session:
            if not workspace_id:
                bp_stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
                bp = (await session.execute(bp_stmt)).scalars().first()
                if bp:
                    workspace_id = bp.id

            media = Media(
                id=job_id,
                userId=user_id,
                businessProfileId=workspace_id,
                filename=f"AI_Render_{job_id}.mp4",
                mimeType="video/mp4",
                url=project_url, # Usually this is a dashboard URL until it's rendered, or we just store the status
                notes="PROCESSING"
            )
            session.add(media)
            await session.commit()

        return {
            "success": True,
            "message": "Video rendering started! It will be available shortly.",
            "mediaId": job_id,
            "videoUrl": project_url,
            "status": "PROCESSING"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Render failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")

