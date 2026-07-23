import asyncio
from database import init_db

async def main():
    try:
        await init_db()
        print('Success')
    except Exception as e:
        print('Error:', e)

if __name__ == "__main__":
    asyncio.run(main())
