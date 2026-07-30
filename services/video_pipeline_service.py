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
        
    prompt = """You are an elite computer vision engine and brand intelligence system operating inside an enterprise video creative pipeline. Your function is to extract precise visual, typographic, material, and conceptual data from the provided product image and return it as strictly valid YAML.
HARD CONSTRAINTS:
Return ONLY valid YAML. No markdown fences. No preamble. No explanation. First character = first character of YAML.
ZERO HALLUCINATION: If any field cannot be definitively confirmed from the image, output null. Never infer beyond what is visually certain.
HEX PRECISION: Derive hex values from the dominant pixel cluster. Do not approximate from memory.
PRODUCT PRIMACY: Ignore backgrounds, props, and non-integrated elements. Analyze only the primary commercial subject.
CATEGORY INTELLIGENCE: Classify with commercial precision:
SaaS dashboard / app UI -> digital_interface
Packaged supplement / food -> consumable
Sneaker / clothing / accessory -> apparel
Keyboard / device / hardware -> physical_goods
Financial / data product -> data_product
Service / platform -> service_platform

ANALYSIS ORDER:
Step 1 — Subject ontology:
product: Sellable item dominates (physical or digital)
character: Human or mascot dominates, no prominent product
composite: Product AND human/persona both prominent

Step 2 — Extract all schema fields below with maximum specificity.
YAML SCHEMA:
pipeline_routing:
  subject_classification: <enum: product | character | composite>
  product_category: <enum: physical_goods | digital_interface | apparel | consumable | data_product | service_platform | null>
  product_type_detail: <string: e.g. "B2B crypto API", "DTC skincare serum", "mechanical keyboard", "online education platform">
  creative_complexity: <enum: minimal | moderate | rich>
  is_digital_product: <boolean>
  has_physical_form: <boolean>
brand_and_typography:
  brand_name: <string or null>
  logo_presence: <boolean>
  logo_style: <enum: wordmark | icon | combination | null>
  typography:
    presence: <boolean>
    primary_classification: <enum: serif | sans-serif | script | display | monospace | null>
    weight: <enum: light | regular | bold | black | null>
    text_content: <exact visible text as string, or null>
    mood: <enum: premium | playful | technical | minimal | aggressive | luxury | null>
chromatic_profile:
  dominant_colors:
    - hex: "<#XXXXXX>"
      name: "<descriptive name e.g. Electric Blue, Warm Ivory, Crimson Red>"
      element_association: "<exact element this color belongs to>"
  color_temperature: <enum: cool | warm | neutral>
  contrast_level: <enum: high | medium | low>
  background_color: <hex string or null>
structural_and_material_analysis:
  material_composition: <string: precise texture + material description, or "digital" for UI products>
  geometric_structure: <string: shape, dimensions, layout, symmetry>
  surface_finish: <enum: matte | glossy | metallic | translucent | flat_digital | textured | null>
  product_complexity: <enum: single_hero | multi_component | ui_screen | lifestyle_scene>
  packaging_present: <boolean>
emotional_and_brand_tone:
  perceived_brand_tier: <enum: luxury | premium | mid_market | mass_market | indie | enterprise>
  emotional_resonance: <enum: trust | excitement | calm | urgency | aspiration | playfulness | authority>
  industry_vertical: <string: e.g. "fintech", "edtech", "wellness", "fashion", "developer_tools", "food_beverage", "ecommerce">
  target_buyer_sophistication: <enum: consumer | prosumer | professional | enterprise>
generation_conditioning:
  lighting_profile: <string: precise photometric description>
  camera_perspective: <string: exact angle, distance, lens feel>
  brand_color_hex_list: <comma-separated list of confirmed hex values for downstream use>
  optimized_diffusion_prompt: <dense comma-separated string for latent diffusion model — material, lighting, angle, finish, mood. No background. Min 30 words.>
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

async def marketing_intelligence_synthesis(product_name: str, scrape_content: str, vision_yaml: str, profile: Optional[Any] = None) -> Dict[str, Any]:
    """Synthesize data into a marketing JSON profile."""
    brand_context = ""
    if profile:
        brand_context = f"\nBusiness Profile Data:\n- Industry: {profile.industry}\n- Audience: {profile.targetAudience}\n- Tone: {profile.toneOfVoice}\n- Content Pillars: {profile.contentPillars}\n"
    
    prompt = f"""You are a senior product marketing strategist and brand intelligence engine. Your task is to synthesize all available product data into a comprehensive marketing intelligence profile that will drive AI video creative generation.
YOU HAVE THREE TIERS OF INPUT — use them in this exact priority order:
TIER 1 — USER-PROVIDED CONTEXT (highest trust — always present):
Product Name: {product_name} {brand_context}

TIER 2 — IMAGE ANALYSIS YAML (second highest trust):
{vision_yaml}
This is ground truth for brand identity — never contradict it.

TIER 3 — URL SCRAPED CONTENT (lowest trust):
{scrape_content}

CRITICAL RESILIENCE RULES:
NEVER output null for industry_vertical — infer it from the brand name, logo style, and any visual signals in the YAML even if URL content is empty.
NEVER output generic fallbacks like "technology" or "software" — be specific. A supplement bottle with clean labels = wellness_supplements. A dashboard screenshot with charts = analytics_saas.
If URL content is empty, build the marketing profile from visual identity signals. A product's visual design language reveals its industry, audience, and positioning.
Brand colors come from Tier 2 (Vision YAML) — never guess or approximate them.
Product type comes from BOTH name analysis AND visual signals. "CAI" suffix + educational platform signals = education_platform.

PRODUCT TYPE DETECTION RULES (apply even without URL content):
API / developer product: URL contains "api", "rapidapi", "developer", or technical documentation signals
Education platform: "learn", "course", "academy", "lab", "tutorial" in name or URL, or classroom visual signals
SaaS dashboard: UI screenshot in image, clean interface, metric cards
Physical product: 3D object in image, packaging visible, material texture
Consumable: Bottle, jar, tube, ingredient imagery
Apparel: Clothing, fabric, human wearing product

OUTPUT — valid JSON only. First character = {{ Last character = }}
{{
"product_intelligence": {{
"product_name": "<from form — exact>",
"product_category": "<specific: online education platform | B2B crypto API | DTC skincare | etc.>",
"product_subcategory": "<more specific: live coding courses | real-time order flow data | etc.>",
"product_type": "<enum: digital_saas | physical_goods | consumable | apparel | data_api | education_platform | service>",
"price_tier": "<from URL if available, else infer from brand tier: free | freemium | low_ticket | mid_ticket | high_ticket | enterprise>",
"value_proposition": "<2-3 sentences from URL if available, else construct from name + visual signals>",
"key_features": ["<feature 1 — from URL or inferred>", "<feature 2>", "<feature 3>", "<feature 4>"],
"primary_pain_point_solved": "<be specific — infer from product category if URL unavailable>",
"transformation_statement": "<Before: [state] -> After: [state]>",
"data_confidence": "<enum: high | medium | low — reflects how much URL content was available>"
}},
"audience_intelligence": {{
"primary_audience": "<specific: online learners | algorithmic traders | gym owners>",
"secondary_audience": "<second segment>",
"audience_sophistication": "<beginner | intermediate | expert | mixed>",
"decision_driver": "<logic | emotion | social_proof | authority | scarcity | curiosity | aspiration>",
"platform_affinity": ["<platform 1>", "<platform 2>", "<platform 3>"],
"aesthetic_preference": "<specific visual world they respond to>",
"buying_context": "<impulse | considered | enterprise_cycle | subscription | one_time>",
"objection_to_overcome": "<#1 reason they hesitate>"
}},
"visual_identity": {{
"brand_colors": {{
"primary": "<#hex — from Vision YAML>",
"secondary": "<#hex — from Vision YAML>",
"accent": "<#hex — from Vision YAML or null>",
"background": "<#hex — from Vision YAML>",
"text": "<#hex — from Vision YAML or null>"
}},
"color_names": {{
"primary": "<descriptive name: Electric Blue | Crimson Red | etc.>",
"secondary": "<descriptive name>",
"accent": "<descriptive name or null>"
}},
"typography_personality": "<from Vision YAML typography field>",
"visual_tone": "<cinematic | editorial | raw_ugc | minimalist | corporate | energetic | premium_lifestyle | dark_technical>",
"logo_description": "<exact visual description for video placement — from Vision YAML>",
"competitor_visual_world": "<how similar product ads look — so this product can differentiate>"
}},
"creative_strategy": {{
"hero_marketing_hook": "<specific and original — never generic>",
"secondary_hook": "<different emotional register>",
"tertiary_hook": "<social proof or curiosity angle>",
"proof_point": "<from URL if available, else null>",
"cta_recommendation": "<specific CTA matching product type>",
"emotional_journey": "<exact arc: confusion -> clarity -> empowerment>",
"content_formats_recommended": ["<format 1>", "<format 2>", "<format 3>"],
"forbidden_cliches": ["<cliche 1>", "<cliche 2>"]
}},
"industry_visual_language": {{
"vertical": "<specific: edtech | fintech | wellness | fashion | developer_tools | food_beverage | fitness | enterprise_saas | ecommerce>",
"environment_archetype": "<co-working space | bloomberg terminal | modern gym | minimalist kitchen | dark IDE | university classroom | luxury retail>",
"lighting_signature": "<cold institutional | warm golden hour | dark dramatic rim | soft diffused natural | clean bright studio>",
"human_archetype": "<eager online learner | stressed analyst | confident founder | health-conscious professional | hardcore athlete>",
"prop_language": "<objects that signal authenticity for this vertical>"
}},
"video_creative_parameters": {{
"recommended_aspect_ratio": "<16:9 | 9:16 | 1:1>",
"recommended_duration_seconds": 8,
"pacing": "<slow_cinematic | medium_editorial | fast_ugc | dynamic_mixed>",
"sound_design": "<specific direction: ambient electronic drone | crisp electronic pulse | warm acoustic | high-energy beat>",
"on_screen_text_style": "<minimal | bold_callout | terminal_code | editorial_caption>",
"product_placement_style": "<hero_center | lifestyle_context | ui_closeup | hands_on | environmental>"
}},
"competitive_differentiation": {{
"unique_angle": "<what makes this visually distinct for advertising>",
"trust_signals": ["<signal 1>", "<signal 2>", "<signal 3>"],
"category_codes_to_break": "<visual cliche of this industry to deliberately avoid>"
}},
"scrape_metadata": {{
"url_content_used": "<boolean — was URL content actually useful>",
"scrape_quality_received": "<high | medium | low | failed>",
"primary_data_source": "<url_content | vision_yaml | form_data | combined>"
}}
}}
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
        
    # Detailed format structures mimicking the n8n logic
    creative_formats = {
        "cinematic_showcase": {
            "name": "Cinematic Product Hero",
            "description": "Product is the sole subject. Shot like a luxury commercial — no humans required.",
            "visual_world": "Studio or aspirational environment — product treated as a luxury object",
            "camera_direction": "Macro close-ups, slow orbital dolly, dramatic lighting reveals",
            "pacing": "Slow and deliberate — every frame holds",
            "text_treatment": "Minimal — brand name and one tagline only",
            "avoid": ["humans", "busy backgrounds", "fast cuts", "generic studio white"]
        },
        "ugc_testimonial": {
            "name": "UGC Testimonial",
            "description": "Authentic first-person account from a real user. Handheld, natural environment, zero CGI.",
            "visual_world": "Natural indoor or outdoor environment matching the user's lifestyle",
            "camera_direction": "Handheld selfie — slight sway, natural shake, intimate framing",
            "pacing": "Slow to medium — conversational rhythm",
            "text_treatment": "Minimal — one key callout max",
            "avoid": ["CGI", "corporate settings", "stock-photo feel", "perfect lighting", "scripted delivery"]
        },
        "fast_cut_features": {
            "name": "Product Demo Walkthrough",
            "description": "Screen recording or hands-on demonstration — built for digital or physical products.",
            "visual_world": "Clean screen environment or hands on product — precision framing",
            "camera_direction": "Top-down for physical. Direct screen capture for digital. Cursor movements matter.",
            "pacing": "Medium — deliberate, clear, no rushed cuts",
            "text_treatment": "Callout labels on key features. Clean sans-serif.",
            "avoid": ["cluttered interfaces", "unexplained UI jumps", "too many features at once"]
        },
        "lifestyle_integration": {
            "name": "Lifestyle Aspiration",
            "description": "Product embedded in a desirable lifestyle — buyer sees themselves in the scene.",
            "visual_world": "Aspirational real-world setting — golden hour, urban cool, natural luxury",
            "camera_direction": "Cinematic wide establishing, then intimate medium shots",
            "pacing": "Slow and editorial — fashion film pacing",
            "text_treatment": "Minimal — let visuals carry the story",
            "avoid": ["obvious product pushing", "cheesy smiling models", "generic stock lifestyle"]
        }
    }
    
    modifiers = [
        {"modifier": "golden_hour", "note": "Warm late afternoon sunlight, long shadows, amber tones"},
        {"modifier": "dark_institutional", "note": "Bloomberg-terminal darkness, cold precision, authority"},
        {"modifier": "clean_daylight", "note": "Soft natural diffused light, bright airy environment"},
        {"modifier": "studio_dramatic", "note": "Controlled studio lighting with dramatic shadows and rim light"}
    ]
    
    recommended_format = max(weights.items(), key=lambda x: x[1])[0]
    variation_modifier = modifiers[0] if "physical" in ptype.lower() else modifiers[1]
    
    return {
        "recommended_format": recommended_format,
        "format_weights": weights,
        "creative_format": creative_formats[recommended_format],
        "variation_modifier": variation_modifier
    }

async def generate_prompt(intelligence: Dict[str, Any], creative_strategy: Dict[str, Any], image_url: str) -> str:
    """Generate the final video-model prompt for a 10-second vertical ad.

    Length discipline is the whole game here. Text-to-video models degrade
    past roughly 120 words — they start dropping the subject, the on-screen
    line, or the camera move. A 150-word two-scene brief does not render as a
    richer video, it renders as a vaguer one, because there is no time for a
    second setup in ten seconds. Ninety to a hundred and twenty words spent on
    ONE decisive moment beats a two-act structure every time.
    """
    cf = creative_strategy.get("creative_format", {})
    vm = creative_strategy.get("variation_modifier", {})

    sys_message = """You are an elite creative director writing prompts for AI video used as Instagram Reels, TikToks and paid social ads. You translate a product profile into ONE production-ready prompt for a single 10-second vertical (9:16) clip.

LENGTH DISCIPLINE — THE MOST IMPORTANT RULE:
90-120 words. Never more. These models lose detail past roughly 120 words, so a longer prompt yields a WORSE video, not a richer one. Every word must earn its place. Cut atmosphere adjectives before you cut the subject, the action, or the on-screen line.

TEN SECONDS OF SCREEN TIME — WHAT ACTUALLY FITS:
One continuous shot, or one shot with a single cut at roughly the halfway mark. That is all. Do not write three scenes. Do not write a montage. Pick the single strongest moment in the story and shoot it properly.
- Seconds 0-1: the hook. Something must already be happening on the first frame. No establishing drift, no slow fade in, no logo card.
- Seconds 1-7: the substance. The product does the thing, or the person reacts to it.
- Seconds 7-10: the payoff. A result on screen, a face registering it, or the brand line landing.

THE FIVE-PART FORMULA (in this order, always):
[Cinematography] + [Subject] + [Action] + [Context] + [Style/Ambiance]
- Cinematography: name the shot and the move — "handheld medium close-up, slight sway", "locked-off macro", "slow dolly in on a 35mm lens".
- Subject: front-load a clear identity anchor with stable visual traits. The model holds whatever you name first.
- Action: active, physical verbs — taps, slams, pours, pulls, snaps. Not "showcases", not "highlights", not "represents".
- Context: the environment as an active system — "steam curling off the cup", "dust suspended in hard window light" — not a static backdrop.
- Style/Ambiance: aesthetic, mood, lighting, and lens character. End with surgical negatives: -v oversaturated, plastic, artificial, warped text, extra fingers.

AUDIO (these models generate sound — direct it in one short clause):
Name the ambience and one punctuating sound: "low room tone, a single crisp keystroke click on impact". No music genre essays. No dialogue unless the format is a testimonial, and then at most one short spoken line.

BRAND SAFETY AND TEXT:
- Every visible product name, tagline, UI string or CTA goes in exact double quotes. The model renders quoted text far more reliably.
- At most ONE short on-screen line. Two competing text elements in ten seconds renders as garbled lettering.
- Never invent claims, features, statistics, prices, ratings or customer counts. If it is not in the input data, it does not go in the video.
- Never write a URL or a hex code into the prompt. Name colors in words.

BANNED — these mark a prompt as machine-generated filler:
"futuristic holographic", "neon-lit trading floor", "dynamic and vibrant", "cutting-edge", "seamlessly", "in today's fast-paced world", floating UI panels, flying data particles, generic glowing orbs, endless neon cityscapes.

OUTPUT — valid JSON only. First character { and last character }. No markdown, no array wrapper, no "output" key, no escaped newlines.
{
  "creative_format_used": "<assigned format name>",
  "variation_modifier_applied": "<assigned modifier name>",
  "product_type": "<product type from marketing intel>",
  "prompt": "<one 10-second vertical shot, 90-120 words, five-part formula in order, hook on frame one, at most one quoted on-screen line, one short audio clause, negatives at the end>"
}
"""

    prompt = f"""Translate the product intelligence and assigned creative format below into ONE production-ready 10-second vertical video prompt.

═══════════════════════════════════════════════════════════
INPUT DATA
═══════════════════════════════════════════════════════════
Marketing Intelligence JSON: {json.dumps(intelligence)}
Reference Image URL: {image_url}

Assigned Creative Format: {cf.get('name', '')}
Format Description: {cf.get('description', '')}
Visual World: {cf.get('visual_world', '')}
Camera Direction: {cf.get('camera_direction', '')}
Pacing: {cf.get('pacing', '')}
Text Treatment: {cf.get('text_treatment', '')}
Format Avoid List: {', '.join(cf.get('avoid', []))}
Variation Modifier: {vm.get('modifier', '')}
Modifier Note: {vm.get('note', '')}

═══════════════════════════════════════════════════════════
PRODUCT TYPE VISUAL RULEBOOK — apply the row matching product_type
═══════════════════════════════════════════════════════════
DIGITAL_SAAS / DATA_API
  World: dark IDE, real terminal output, Bloomberg-terminal restraint.
  Human: analyst, developer or founder — precise, unglamorous, focused.
  Props: real UI on a real monitor, mechanical keyboard, coffee going cold.
  Never: holographic dashboards, flying data particles, glowing blue "AI" mist.

PHYSICAL_GOODS
  World: controlled studio light, or the aspirational place the thing gets used.
  Subject: the product is the hero — material, finish, weight, craftsmanship.
  Camera: macro close-ups, orbital dolly, rim light for edge definition.
  Never: floating products, white infinity backdrop unless it is a luxury brand.

CONSUMABLE (food, beverage, supplement, skincare)
  World: kitchen counter, bathroom vanity, a real outdoor moment.
  Subject: the ingredient story — show what is inside it.
  Camera: macro pour, steam, condensation, texture at close range.
  Never: clinical sterile lab, generic stock-photo wellness.

APPAREL
  World: match the brand tier — luxury reads as editorial negative space, streetwear reads as urban grit.
  Subject: fabric movement, fit on a real body, material texture.
  Never: flat lay as the primary shot, plain mannequin.

EDUCATION_PLATFORM
  World: a real desk, a café, a library — never a generic classroom.
  Subject: the face at the moment of understanding.
  Never: graduation caps, stock students high-fiving.

ENTERPRISE_SAAS
  World: modern office, glass, daylight, competent adults.
  Subject: a professional using the product with the result visible on screen.
  Never: empty boardrooms, staged handshakes.

═══════════════════════════════════════════════════════════
MANDATORY RULES
═══════════════════════════════════════════════════════════
RULE 1 — FORMAT COMPLIANCE. Build the whole prompt around the assigned creative format. "ugc_testimonial" means a real face in a real room with zero CGI. "cinematic_product_hero" means no humans and the product as sole subject. Never fall back to a generic tech visual.

RULE 2 — ONE MOMENT, TEN SECONDS, VERTICAL 9:16. One continuous shot, or one cut at the halfway mark at most. No montages, no "then we cut to" chains. The hook must land on the first frame.

RULE 3 — BRAND COLOR ON JUSTIFIED SURFACES. Use the brand's color names on real surfaces that would plausibly carry them — a screen, a label, a wall, a jacket. Never as free-floating light. Never as a hex code.

RULE 4 — QUOTED TEXT, ONCE. Every visible brand string in exact double quotes, and no more than one such element on screen.

RULE 5 — THE VARIATION MODIFIER MUST BE VISIBLE. It has to change the atmosphere, the lighting, or the camera behaviour in a way a viewer would notice. This is what stops every video for this brand looking identical.

RULE 6 — INVENT NOTHING. No statistics, no prices, no ratings, no claims absent from the input data.

RULE 7 — 90-120 WORDS. Count them. A prompt over 120 words will be rejected.

Return the JSON object and nothing else.
"""

    from services.ai_service import _call_openrouter

    combined_prompt = f"{sys_message}\n\nUSER PROMPT:\n{prompt}"
    result = await _call_openrouter(combined_prompt, model=TEXT_MODEL, json_response=True)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
        generated = parsed.get("prompt") or ""
        if generated:
            return generated.strip()
        logger.warning("Video prompt JSON parsed but carried no 'prompt' field")
        return cleaned.strip()
    except Exception as e:
        logger.error(f"Failed to parse generation prompt JSON: {e}")
        return result.strip()


async def execute_video_pipeline(product_name: str, product_url: Optional[str] = None, image_url: str = "", goal: str = "conversion", profile: Optional[Any] = None) -> Dict[str, Any]:
    """Execute the full end-to-end creative video pipeline."""
    logger.info(f"Starting video pipeline for {product_name}")
    
    # 1. Scrape
    scrape_content = await scrape_product_url(product_url)
    
    # 2. Vision
    try:
        vision_yaml = await image_vision_analysis(image_url)
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        vision_yaml = """
primary_color: '#000000'
secondary_color: '#ffffff'
typography_style: 'modern'
visual_tone: 'clean'
key_elements: []
product_placement: 'center'
"""
    
    # 3. Intelligence
    intelligence = await marketing_intelligence_synthesis(product_name, scrape_content, vision_yaml, profile)
    
    # 4. Creative Engine
    creative_strategy = run_creative_engine(intelligence, goal)
    
    # 5. Prompt Generation
    final_prompt = await generate_prompt(intelligence, creative_strategy, image_url)
    
    logger.info("Video pipeline completed successfully.")
    
    return {
        "status": "success",
        "intelligence": intelligence,
        "creative_strategy": creative_strategy,
        "veo_prompt": final_prompt,
        "image_url": image_url
    }



