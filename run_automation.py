import asyncio
from database import init_db, close_db
from services.scheduler import execute_marketing_loop

async def main():
    await init_db()
    print("Running AI automation 5 times...")
    for i in range(5):
        print(f"Run {i+1}...")
        try:
            await execute_marketing_loop()
            print(f"Run {i+1} complete.")
        except Exception as e:
            print(f"Run {i+1} failed: {e}")
        
    await close_db()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
