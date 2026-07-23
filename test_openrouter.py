import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

async def test_openrouter():
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    print("Testing TEXT_MODEL google/gemma-2-9b-it:free...")
    payload = {
        "model": "google/gemma-2-9b-it:free",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    async with httpx.AsyncClient() as ac:
        resp = await ac.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30.0)
        print(resp.status_code)
        print(resp.text)
        
    print("Testing VISION_MODEL meta-llama/llama-3.2-11b-vision-instruct:free...")
    payload = {
        "model": "meta-llama/llama-3.2-11b-vision-instruct:free",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    async with httpx.AsyncClient() as ac:
        resp = await ac.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30.0)
        print(resp.status_code)
        print(resp.text)

asyncio.run(test_openrouter())
