"""
=============================================================================
Organic Marketing AI — Video Pipeline Service
=============================================================================
Executes the complex creative video pipeline (formerly n8n automation).
1. Scrape product URL (Jina.ai)
2. Vision Analysis (Gemini/Claude via OpenRouter)
3. Marketing Intelligence (LLM)
4. Creative Engine v3 (Rule-based weights)
5. Prompt Generator (LLM)
=============================================================================
"""

import json
import httpx
from typing import Dict, Any, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from services.ai_service import LLM_TIMEOUT, MARKETING_MODEL

VISION_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"
TEXT_MODEL = "google/gemma-4-31b-it:free"

async def scrape_product_url(url: str) -> str:
    """Smart URL Scraper using jina.ai"""
    if not url or url.strip() == "":
        return "No URL provided."
        
    jina_url = f"https://r.jina.ai/{url}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(jina_url)
            resp.raise_for_status()
            content = resp.text
            # Limit length to avoid blowing up context window
            return content[:15000]
    except Exception as e:
        logger.warning(f"Jina scrape failed for {url}: {e}")
        return "Failed to scrape URL."

@retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
async def image_vision_analysis(image_url: str) -> str:
    """Analyze image using OpenRouter Vision capabilities."""
    if not image_url:
        return "No image provided."
        
    prompt = """Analyze this product image carefully. Extract and return a strict YAML block (and nothing else) covering:
- primary_color (hex)
- secondary_color (hex)
- typography_style
- visual_tone (e.g. minimalist, energetic, corporate)
- key_elements (list of physical objects visible)
- product_placement (how the product is framed)
"""
    
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://organicmarketing.ai",
        "X-Title": "Organic Marketing AI",
    }
    
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
    }
    
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

async def marketing_intelligence_synthesis(product_name: str, scrape_content: str, vision_yaml: str) -> Dict[str, Any]:
    """Synthesize data into a marketing JSON profile."""
    prompt = f"""You are an elite marketing strategist. Combine the following data into a detailed JSON marketing intelligence profile.
    
Product Name: {product_name}
Scraped Content: {scrape_content}
Vision Analysis YAML: {vision_yaml}

Return valid JSON with the following keys:
- product_intelligence (product_type, value_proposition, key_features)
- audience_intelligence (primary_audience, decision_driver)
- visual_identity (brand_colors, visual_tone)
- creative_strategy (hero_marketing_hook, cta_recommendation)
"""
    from services.ai_service import _call_openrouter
    
    response = await _call_openrouter(prompt, json_response=True, model=TEXT_MODEL)
    try:
        # Clean markdown if present
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response[:-3]
        return json.loads(response.strip())
    except Exception as e:
        logger.error(f"Failed to parse marketing intelligence JSON: {e}")
        return {"error": "Failed to synthesize intelligence"}

def run_creative_engine(intelligence_json: Dict[str, Any], goal: str) -> Dict[str, Any]:
    """Calculate creative format weights (JavaScript port)."""
    # Simple port of the JS logic
    ptype = intelligence_json.get("product_intelligence", {}).get("product_type", "digital")
    
    # Base weights
    weights = {
        "cinematic_showcase": 50,
        "ugc_testimonial": 50,
        "fast_cut_features": 50,
        "lifestyle_integration": 50
    }
    
    if "physical" in ptype.lower() or "apparel" in ptype.lower():
        weights["cinematic_showcase"] += 30
        weights["lifestyle_integration"] += 30
    else:
        weights["fast_cut_features"] += 30
        weights["ugc_testimonial"] += 20
        
    if goal == "conversion":
        weights["ugc_testimonial"] += 40
        weights["fast_cut_features"] += 20
    elif goal == "brand_awareness":
        weights["cinematic_showcase"] += 40
        weights["lifestyle_integration"] += 20
        
    recommended_format = max(weights.items(), key=lambda x: x[1])[0]
    
    return {
        "recommended_format": recommended_format,
        "format_weights": weights
    }

async def generate_prompt(intelligence: Dict[str, Any], creative_strategy: Dict[str, Any], image_url: str) -> str:
    """Generate final Veo 3.1 video prompt."""
    prompt = f"""You are a master video director generating a prompt for the Google Veo 3.1 AI video model.
Your goal is to create a 5-part prompt based on the marketing intelligence and creative strategy.

Intelligence: {json.dumps(intelligence)}
Strategy: {json.dumps(creative_strategy)}
Reference Image URL: {image_url}

Create a single paragraph prompt matching the Veo 3.1 requirement:
[Subject/Action] + [Camera Movement/Framing] + [Lighting] + [Atmosphere/Vibe] + [Specific Details]

Output ONLY the raw prompt string, nothing else.
"""
    from services.ai_service import _call_openrouter
    result = await _call_openrouter(prompt, model=TEXT_MODEL)
    return result.strip()

async def execute_video_pipeline(product_name: str, product_url: str, image_url: str, goal: str = "conversion") -> Dict[str, Any]:
    """Execute the full end-to-end creative video pipeline."""
    logger.info(f"Starting video pipeline for {product_name}")
    
    # 1. Scrape
    scrape_content = await scrape_product_url(product_url)
    
    # 2. Vision
    vision_yaml = await image_vision_analysis(image_url)
    
    # 3. Intelligence
    intelligence = await marketing_intelligence_synthesis(product_name, scrape_content, vision_yaml)
    
    # 4. Creative Engine
    creative_strategy = run_creative_engine(intelligence, goal)
    
    # 5. Prompt Generation
    final_prompt = await generate_prompt(intelligence, creative_strategy, image_url)
    
    logger.info("Video pipeline completed successfully.")
    
    # 6. JSON2Video Payload Generation
    colors = intelligence.get('visual_identity', {}).get('brand_colors', {})
    primary_color = colors.get('primary_dark', '#000000')
    accent_color = colors.get('secondary_accent', '#ffffff')
    
    json2video_payload = {
        "resolution": "square",
        "quality": "high",
        "fps": 30,
        "draft": False,
        "scenes": [
            {
                "comment": "Hero Intro",
                "duration": 4,
                "elements": [
                    {
                        "type": "image",
                        "src": image_url,
                        "style": "pan_right",
                        "zoom": 1.1
                    },
                    {
                        "type": "text",
                        "text": f"Discover {product_name}",
                        "style": "headline",
                        "font": "Outfit",
                        "size": 72,
                        "color": "#ffffff",
                        "position": "center",
                        "x": 0, "y": -200, "width": 800
                    }
                ]
            },
            {
                "comment": "Creative Strategy Hook",
                "duration": 5,
                "elements": [
                    {
                        "type": "image",
                        "src": image_url,
                        "style": "zoom_in"
                    },
                    {
                        "type": "text",
                        "text": intelligence.get('creative_strategy', {}).get('hero_marketing_hook', 'Upgrade your lifestyle.'),
                        "style": "normal",
                        "font": "Outfit",
                        "size": 48,
                        "color": accent_color,
                        "position": "center",
                        "x": 0, "y": 0, "width": 800
                    }
                ]
            }
        ]
    }
    
    return {
        "status": "success",
        "intelligence": intelligence,
        "creative_strategy": creative_strategy,
        "veo_prompt": final_prompt,
        "image_url": image_url,
        "json2video_payload": json2video_payload
    }
