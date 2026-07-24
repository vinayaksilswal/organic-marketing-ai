"""
=============================================================================
Organic Marketing AI — LinkedIn API Service
=============================================================================
Automated LinkedIn Company Page publishing via the LinkedIn REST API.
Supports text posts and article sharing with rich media previews.

Required environment variables:
  - LINKEDIN_ACCESS_TOKEN    (OAuth 2.0 token with w_organization_social scope)
  - LINKEDIN_ORGANIZATION_ID (LinkedIn Company Page numeric ID)

LinkedIn Developer Portal must have "Share on LinkedIn" product approved
and the authenticating user must be an admin of the Company Page.
=============================================================================
"""

from __future__ import annotations

import os
import logging
import httpx
from typing import Optional, Tuple
from database import AsyncSessionLocal, SocialConnection
from sqlalchemy import select
from services.crypto_service import decrypt_token

logger = logging.getLogger("organicai.linkedin")

LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_API_VERSION = "202406"  # LinkedIn versioned API: YYYYMM


class LinkedInService:
    """
    LinkedIn REST API client for automated Company Page publishing.
    Uses the Versioned API with w_organization_social scope.
    """

    def __init__(self):
        self.default_org_id = os.getenv("LINKEDIN_ORGANIZATION_ID", "")

    async def _get_credentials(self, workspace_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Fetch LinkedIn credentials for a specific tenant."""
        async with AsyncSessionLocal() as session:
            stmt = select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
            conn = (await session.execute(stmt)).scalars().first()
            if not conn or not conn.linkedinAccessToken:
                logger.warning(f"No LinkedIn credentials for workspace {workspace_id}")
                return None, None
            
            access_token = decrypt_token(conn.linkedinAccessToken) or conn.linkedinAccessToken
            # For now we use the platform default org ID, in a full version this would be in SocialConnection too.
            org_id = self.default_org_id
            return access_token, org_id

    def _headers(self, access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": LINKEDIN_API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def post_text(self, workspace_id: str, text: str) -> Optional[str]:
        """
        Publish a text-only post to the LinkedIn Company Page.
        
        Args:
            workspace_id: Tenant Workspace ID
            text: Post content (max ~3000 chars recommended).
        
        Returns:
            LinkedIn post URN on success, None on failure.
        """
        access_token, org_id = await self._get_credentials(workspace_id)
        if not access_token or not org_id:
            return None

        payload = {
            "author": f"urn:li:organization:{org_id}",
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{LINKEDIN_API_BASE}/rest/posts",
                    headers=self._headers(access_token),
                    json=payload,
                )

                if resp.status_code in (200, 201):
                    # LinkedIn returns the post URN in the x-restli-id header
                    post_id = resp.headers.get("x-restli-id", "")
                    logger.info(f"LinkedIn post published: {post_id}")
                    return post_id
                else:
                    logger.error(f"LinkedIn post failed [{resp.status_code}]: {resp.text}")
                    return None
        except Exception as e:
            logger.error(f"LinkedIn API error: {e}")
            return None

    async def post_article(
        self,
        workspace_id: str,
        text: str,
        article_url: str,
        article_title: str,
        article_description: str = "",
    ) -> Optional[str]:
        """
        Share an article link on the LinkedIn Company Page with rich preview.
        
        Note: LinkedIn does not reliably scrape OG metadata automatically.
        We must explicitly provide title, description, and the source URL.
        
        Args:
            workspace_id: Tenant Workspace ID
            text: Post commentary text.
            article_url: URL of the article to share.
            article_title: Title for the article preview card.
            article_description: Description for the preview card.
        
        Returns:
            LinkedIn post URN on success, None on failure.
        """
        access_token, org_id = await self._get_credentials(workspace_id)
        if not access_token or not org_id:
            return None

        payload = {
            "author": f"urn:li:organization:{org_id}",
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "article": {
                    "source": article_url,
                    "title": article_title,
                    "description": article_description or text[:200],
                },
            },
            "lifecycleState": "PUBLISHED",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{LINKEDIN_API_BASE}/rest/posts",
                    headers=self._headers(access_token),
                    json=payload,
                )

                if resp.status_code in (200, 201):
                    post_id = resp.headers.get("x-restli-id", "")
                    logger.info(f"LinkedIn article shared: {post_id}")
                    return post_id
                else:
                    logger.error(f"LinkedIn article share failed [{resp.status_code}]: {resp.text}")
                    return None
        except Exception as e:
            logger.error(f"LinkedIn API error: {e}")
            return None

    async def format_b2b_copy(self, caption: str, cta_url: str = "https://organicmarketing.ai") -> str:
        """
        Format a marketing caption into LinkedIn-optimized B2B copy.
        LinkedIn posts perform best with:
        - Opening hook (first 2 lines visible before "see more")
        - Bullet points for scanability
        - Clear CTA at the bottom
        - Hashtags at the very end
        """
        lines = caption.strip().split("\n")
        hook = lines[0] if lines else caption[:150]

        formatted = f"""{hook}

{caption}

🔗 Learn more: {cta_url}

#PostQuantumCryptography #QuantumComputing #Cybersecurity #NIST #PQC #QuantumSafe #TechSecurity"""

        return formatted


# ─── Singleton ───────────────────────────────────────────────────────
linkedin_service = LinkedInService()
