import asyncio
from loguru import logger
from database import init_db, close_db, AsyncSessionLocal, User, BusinessProfile, SocialCampaign, Media
from sqlalchemy import select
from services.creative_service import auto_populate_workspace
from worker import context_aggregation_task
import uuid

async def test_production_loop():
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # Check existing users
        target_email = "vinayaksilswal@gmail.com"
        stmt = select(User).where(User.email == target_email)
        user = (await session.execute(stmt)).scalars().first()
        
        if not user:
            logger.info(f"Creating user {target_email} for testing.")
            user = User(
                id=str(uuid.uuid4()),
                email=target_email,
                password="hashed_password",
                subscriptionStatus="ACTIVE"
            )
            session.add(user)
            await session.commit()
            
        profile_stmt = select(BusinessProfile).where(BusinessProfile.userId == user.id)
        profile = (await session.execute(profile_stmt)).scalars().first()
        
        if not profile:
            logger.info("Creating business profile for testing.")
            profile = BusinessProfile(
                id=str(uuid.uuid4()),
                userId=user.id,
                name="Test AI Agency",
                websiteUrl="https://example.com",
                description="We are an AI agency testing production loops.",
                businessModel="B2B SaaS"
            )
            session.add(profile)
            await session.commit()
            
        logger.info(f"Found business profile: {profile.name} ({profile.id})")
        
        # Clean existing campaigns to force new ones to trigger
        clean_stmt = select(SocialCampaign).where(SocialCampaign.businessProfileId == profile.id)
        campaigns = (await session.execute(clean_stmt)).scalars().all()
        for c in campaigns:
            await session.delete(c)
        await session.commit()
            
        # Auto-populate creatives
        logger.info("Triggering auto_populate_workspace (Video Generation)...")
        populate_res = await auto_populate_workspace(user.id, profile.id)
        logger.info(f"Auto-populate results: {populate_res}")
        
        # Trigger context aggregation
        logger.info("Triggering context_aggregation_task (Automation loop)...")
        post_res = await context_aggregation_task({}, profile.id)
        logger.info(f"Post results: {post_res}")
                
    await close_db()

if __name__ == "__main__":
    asyncio.run(test_production_loop())
