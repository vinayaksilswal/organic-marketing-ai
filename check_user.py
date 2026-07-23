import asyncio
from database import init_db, AsyncSessionLocal, User
from sqlalchemy import select

async def main():
    await init_db()
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User))).scalars().all()
        print(f"Total Users found: {len(users)}")
        for u in users:
            print(f"User: {u.email}")

asyncio.run(main())
