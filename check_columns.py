import asyncio
import asyncpg
import os
from dotenv import load_dotenv
load_dotenv()

async def test():
    db_url = os.environ.get('DATABASE_URL')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    if 'sslmode=require' in db_url:
        db_url = db_url.replace('sslmode=require', 'ssl=require')
    
    conn = await asyncpg.connect(db_url)
    
    # Query column names
    rows = await conn.fetch('''
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'BusinessProfile'
    ''')
    for row in rows:
        print(f"{row['column_name']}: {row['data_type']}")
        
    await conn.close()

asyncio.run(test())
