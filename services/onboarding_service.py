"""
=============================================================================
Organic Marketing AI — Onboarding Service
=============================================================================
Handles enterprise-grade multi-tenant onboarding. Encapsulates business logic
for business profile creation, updates, and securely enqueuing background tasks
to the ARQ job queue instead of fragile inline asyncio tasks.
=============================================================================
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from sqlalchemy import select
from loguru import logger

from database import AsyncSessionLocal, BusinessProfile, User
from config import settings
from exceptions import OrganicMarketingException
from services.task_utils import spawn_background


class OnboardingService:
    @staticmethod
    async def create_business_profile(user_id: str, data: dict) -> BusinessProfile:
        """Create a new business profile (workspace) and enqueue background tasks."""
        try:
            async with AsyncSessionLocal() as session:
                profile = BusinessProfile(
                    userId=user_id,
                    name=data.get("name") or "New Workspace",
                    websiteUrl=data.get("websiteUrl"),
                    description=data.get("description"),
                    businessModel=data.get("businessModel") or "General",
                    productCatalogUrl=data.get("productCatalogUrl"),
                )
                session.add(profile)
                await session.commit()
                await session.refresh(profile)

                # Build the brand profile inline rather than only in the
                # background. Everything downstream — captions, video prompts,
                # creative generation — is generic without it, and when the
                # background attempt failed the workspace stayed that way. This
                # takes a few seconds and makes a new business usable
                # immediately. Failure is tolerated: the marketing loop retries,
                # so a rate limit at signup no longer leaves a dead workspace.
                try:
                    from services.creative_service import generate_brand_context

                    ctx = await generate_brand_context(profile)
                    profile.industry = ctx["industry"]
                    profile.targetAudience = ctx["targetAudience"]
                    profile.toneOfVoice = ctx["toneOfVoice"]
                    profile.contentPillars = ctx["contentPillars"]
                    profile.suggestedHashtags = ctx["suggestedHashtags"]
                    profile.brandColors = ctx["brandColors"]
                    profile.brandAnalysisComplete = True
                    await session.commit()
                    await session.refresh(profile)
                    logger.info(f"Brand profile built at creation for workspace {profile.id}")
                except Exception as e:
                    await session.rollback()
                    logger.warning(
                        f"Brand profile could not be built at creation for {profile.id} ({e}); "
                        f"the marketing loop will retry"
                    )

                # Enqueue the heavier work (creatives, catalog sync) in the background
                await OnboardingService._enqueue_onboarding_tasks(user_id, profile.id, profile.productCatalogUrl)

                return profile
        except Exception as e:
            logger.error(f"Failed to create business profile: {e}")
            raise OrganicMarketingException("Failed to create workspace", status_code=500)

    @staticmethod
    async def update_business_profile(user_id: str, data: dict) -> BusinessProfile:
        """Update an existing business profile and enqueue tasks if needed."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(BusinessProfile).where(BusinessProfile.userId == user_id)
                res = await session.execute(stmt)
                profile = res.scalars().first()

                if not profile:
                    # Create one if it doesn't exist
                    profile = BusinessProfile(
                        userId=user_id,
                        name=data.get("name") or "My Business",
                        websiteUrl=data.get("websiteUrl"),
                        description=data.get("description"),
                        businessModel=data.get("businessModel"),
                        productCatalogUrl=data.get("productCatalogUrl"),
                        influencerReferenceUrl=data.get("influencerReferenceUrl"),
                        niche=data.get("niche"),
                    )
                    session.add(profile)
                else:
                    if "name" in data and data["name"] is not None:
                        profile.name = data["name"]
                    if "websiteUrl" in data and data["websiteUrl"] is not None:
                        profile.websiteUrl = data["websiteUrl"]
                    if "description" in data and data["description"] is not None:
                        profile.description = data["description"]
                    if "businessModel" in data and data["businessModel"] is not None:
                        profile.businessModel = data["businessModel"]
                    if "niche" in data and data["niche"] is not None:
                        profile.niche = data["niche"]
                    if "postIntervalHours" in data and data["postIntervalHours"] is not None:
                        profile.postIntervalHours = data["postIntervalHours"]
                    if "creativeGenerationIntervalHours" in data and data["creativeGenerationIntervalHours"] is not None:
                        profile.creativeGenerationIntervalHours = data["creativeGenerationIntervalHours"]
                    if "autoGenerateCreatives" in data and data["autoGenerateCreatives"] is not None:
                        profile.autoGenerateCreatives = data["autoGenerateCreatives"]
                    if "logoUrl" in data and data["logoUrl"] is not None:
                        profile.logoUrl = data["logoUrl"]
                    if "productCatalogUrl" in data and data["productCatalogUrl"] is not None:
                        profile.productCatalogUrl = data["productCatalogUrl"]
                    if "influencerReferenceUrl" in data and data["influencerReferenceUrl"] is not None:
                        profile.influencerReferenceUrl = data["influencerReferenceUrl"]

                await session.commit()
                await session.refresh(profile)

                # Enqueue tasks (brand analysis + creative generation)
                await OnboardingService._enqueue_onboarding_tasks(user_id, profile.id, profile.productCatalogUrl)

                return profile
        except Exception as e:
            logger.error(f"Failed to update business profile: {e}")
            raise OrganicMarketingException("Failed to update workspace", status_code=500)

    @staticmethod
    async def _enqueue_onboarding_tasks(user_id: str, workspace_id: str, product_catalog_url: Optional[str]) -> None:
        """Securely enqueue background tasks to ARQ, with fallback to inline execution if unavailable."""
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            
            # Enqueue auto_populate_workspace task
            await redis_pool.enqueue_job("auto_populate_workspace_task", user_id, workspace_id)
            logger.info(f"Enqueued auto_populate_workspace_task for workspace {workspace_id}")
            
            # Enqueue sync_workspace_catalog task if catalog URL is present
            if product_catalog_url:
                await redis_pool.enqueue_job("sync_workspace_catalog_task", workspace_id)
                logger.info(f"Enqueued sync_workspace_catalog_task for workspace {workspace_id}")
            
            await redis_pool.close()
        except Exception as e:
            logger.warning(f"ARQ queue unavailable. Falling back to inline asyncio execution: {e}")
            from services.creative_service import auto_populate_workspace
            from services.catalog_service import sync_workspace_catalog

            spawn_background(
                auto_populate_workspace(user_id, workspace_id),
                f"auto_populate_workspace({workspace_id})",
            )
            if product_catalog_url:
                spawn_background(
                    sync_workspace_catalog(workspace_id),
                    f"sync_workspace_catalog({workspace_id})",
                )
