"""
Enable Row-Level Security (RLS) on tenant-specific tables.
"""
import asyncio
from sqlalchemy import text
from loguru import logger
from database import init_db, close_db

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

async def enable_rls():
    engine = await init_db()
    async with engine.begin() as conn:
        for table in TENANT_TABLES:
            logger.info(f"Enabling RLS on table: {table}")
            
            # Enable RLS on the table
            await conn.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;'))
            
            # Drop policy if it already exists (to allow re-running the script)
            await conn.execute(text(f'DROP POLICY IF EXISTS tenant_isolation_policy ON "{table}";'))
            
            # Create the RLS policy
            # Using NULLIF to handle cases where the setting might be an empty string if misconfigured, though not strictly necessary.
            policy_sql = f"""
            CREATE POLICY tenant_isolation_policy ON "{table}"
                FOR ALL
                USING ("businessProfileId" = current_setting('app.current_workspace', true));
            """
            await conn.execute(text(policy_sql))
            
            # Force RLS for table owners as well (optional, but good for superusers)
            await conn.execute(text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;'))
            
    await close_db()
    logger.info("RLS enabled successfully on all tenant tables.")

if __name__ == "__main__":
    asyncio.run(enable_rls())
