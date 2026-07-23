import asyncio
import httpx

async def list_models():
    async with httpx.AsyncClient() as ac:
        resp = await ac.get("https://openrouter.ai/api/v1/models")
        data = resp.json()
        free_models = [m["id"] for m in data["data"] if "free" in m["id"].lower()]
        print("Free models:")
        for m in free_models:
            print(m)

asyncio.run(list_models())
