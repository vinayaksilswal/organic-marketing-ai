"""
=============================================================================
Organic Marketing AI — TikTok Direct Post Service
=============================================================================
Handles the TikTok Content Posting API (Direct Post).
Flow:
1. creator_info/query (verify permissions)
2. video/init (initialize upload)
3. upload (chunked or direct)
4. poll (wait for TikTok processing)
=============================================================================
"""

import os
import time
import httpx
from typing import Dict, Any, Optional
from loguru import logger
from tenacity import retry, wait_exponential, stop_after_attempt
from config import settings

TIKTOK_API_URL = "https://open.tiktokapis.com/v2"

class TikTokDirectPostService:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def query_creator_info(self) -> Dict[str, Any]:
        """Verify the creator account is eligible for posting."""
        url = f"{TIKTOK_API_URL}/post/publish/creator_info/query/"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code") != "ok":
                raise ValueError(f"TikTok Creator Query Error: {data.get('error')}")
            return data["data"]

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def initialize_video_upload(self, video_size: int, chunk_count: int) -> Dict[str, Any]:
        """Step 1: Init Video Upload."""
        url = f"{TIKTOK_API_URL}/post/publish/video/init/"
        payload = {
            "post_info": {
                "title": "Automated Post",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size // chunk_count if chunk_count > 0 else video_size,
                "total_chunk_count": chunk_count,
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code") != "ok":
                raise ValueError(f"TikTok Video Init Error: {data.get('error')}")
            return data["data"]

    async def upload_video(self, publish_id: str, upload_url: str, video_bytes: bytes) -> bool:
        """Step 2: Upload Video Bytes (simplified for single chunk)."""
        headers = {
            "Content-Range": f"bytes 0-{len(video_bytes)-1}/{len(video_bytes)}",
            "Content-Length": str(len(video_bytes)),
            "Content-Type": "video/mp4"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.put(upload_url, headers=headers, content=video_bytes)
            resp.raise_for_status()
            # TikTok responds with empty body on success 201/200
            return resp.status_code in (200, 201)

    @retry(wait=wait_exponential(min=5, max=20), stop=stop_after_attempt(5))
    async def check_status(self, publish_id: str) -> str:
        """Step 3: Poll for publish status."""
        url = f"{TIKTOK_API_URL}/post/publish/status/fetch/"
        payload = {"publish_id": publish_id}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("data", {}).get("status")
            if status == "PROCESSING_DOWNLOAD":
                raise ValueError("Still processing")
            return status

async def post_to_tiktok(access_token: str, caption: str, video_bytes: bytes) -> Dict[str, Any]:
    """Complete TikTok Direct Post Flow."""
    try:
        service = TikTokDirectPostService(access_token)
        
        # 1. Query creator info
        creator_info = await service.query_creator_info()
        logger.info(f"TikTok Creator Info: {creator_info}")
        
        # 2. Init upload
        init_res = await service.initialize_video_upload(len(video_bytes), 1)
        publish_id = init_res["publish_id"]
        upload_url = init_res["upload_url"]
        
        # 3. Upload bytes
        success = await service.upload_video(publish_id, upload_url, video_bytes)
        if not success:
            return {"success": False, "error": "Video upload PUT failed"}
            
        # 4. Poll
        status = await service.check_status(publish_id)
        return {"success": True, "publish_id": publish_id, "status": status}
    except Exception as e:
        logger.error(f"TikTok Post Error: {e}")
        return {"success": False, "error": str(e)}
