import asyncio
from sqlalchemy import text
from database import init_db, close_db
from loguru import logger

TENANT_TABLES = [
    "VideoApiConfig",
    "Product",
    "SocialConnection",
    "Audience",
    "MarketingState",
    "SocialCampaign",
    "SocialPost",
    "EmailCampaign",
    "Media",
    "MarketingLog",
]

async def add_column():
    engine = await init_db()
    # Use a connection with autocommit so a failure in one statement doesn't abort the rest
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        for table in TENANT_TABLES:
            logger.info(f"Adding column businessProfileId to {table}...")
            try:
                await conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;'))
            except Exception as e:
                logger.error(f"Failed to add column to {table}: {e}")
                
            try:
                await conn.execute(text(f'ALTER TABLE "{table}" ADD CONSTRAINT "{table}_businessProfileId_fkey" FOREIGN KEY ("businessProfileId") REFERENCES "BusinessProfile"("id") ON DELETE CASCADE;'))
            except Exception as e:
                logger.info(f"Constraint might already exist or failed for {table}: {e}")
                
        print("Done.")
    await close_db()

if __name__ == "__main__":
    asyncio.run(add_column())
