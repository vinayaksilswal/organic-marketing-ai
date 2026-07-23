import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    db_url = os.environ.get('DATABASE_URL')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    if 'sslmode=require' in db_url:
        db_url = db_url.replace('sslmode=require', 'ssl=require')
    
    print("Connecting to DB...")
    conn = await asyncpg.connect(db_url)
    
    queries = [
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "creativeGenerationIntervalHours" INTEGER NOT NULL DEFAULT 2;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "autoGenerateCreatives" BOOLEAN NOT NULL DEFAULT TRUE;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandColors" JSON NOT NULL DEFAULT \'[]\'::json;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandFonts" JSON NOT NULL DEFAULT \'[]\'::json;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "industry" VARCHAR;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "targetAudience" TEXT;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "toneOfVoice" VARCHAR;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "contentPillars" JSON NOT NULL DEFAULT \'[]\'::json;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "suggestedHashtags" JSON NOT NULL DEFAULT \'[]\'::json;',
        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandAnalysisComplete" BOOLEAN NOT NULL DEFAULT FALSE;',
    ]
    
    for q in queries:
        try:
            await conn.execute(q)
            print(f"Executed: {q}")
        except Exception as e:
            print(f"Failed: {q} - {e}")
            
    await conn.close()
    print("Migration done.")

asyncio.run(migrate())
