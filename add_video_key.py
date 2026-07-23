import asyncio
from database import init_db, AsyncSessionLocal, User, BusinessProfile, VideoApiConfig
from sqlalchemy import select, and_

async def main():
    await init_db()
    async with AsyncSessionLocal() as session:
        user_stmt = select(User).where(User.email == "vinayaksilswal@gmail.com")
        user = (await session.execute(user_stmt)).scalars().first()
        if not user:
            print("User not found in DB")
            return
            
        bp_stmt = select(BusinessProfile).where(BusinessProfile.userId == user.id)
        bp = (await session.execute(bp_stmt)).scalars().first()
        if not bp:
            print("BusinessProfile not found in DB")
            return
            
        stmt = select(VideoApiConfig).where(and_(
            VideoApiConfig.userId == user.id,
            VideoApiConfig.businessProfileId == bp.id
        ))
        config = (await session.execute(stmt)).scalars().first()
        if config:
            config.provider = "json2video"
            config.apiKey = "gsEiKvhWgxufmLNvToFdLTGfMjTiSonGfftnOcRg"
            config.endpoint = "https://api.json2video.com"
        else:
            config = VideoApiConfig(
                userId=user.id,
                businessProfileId=bp.id,
                provider="json2video",
                apiKey="gsEiKvhWgxufmLNvToFdLTGfMjTiSonGfftnOcRg",
                endpoint="https://api.json2video.com"
            )
            session.add(config)
        await session.commit()
        print("Successfully added/updated json2video key for user.")

asyncio.run(main())
