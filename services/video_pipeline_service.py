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
import random
import re

import httpx
from typing import Dict, Any, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from services.ai_service import LLM_TIMEOUT, MARKETING_MODEL

# Vision stays a VL model: a text-only model handed an image does not fail,
# it invents, and an invented product description poisons every prompt built
# from it.
VISION_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"
TEXT_MODEL = "z-ai/glm-5.2:free"

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
        brand_context = (
            f"\nBusiness Profile Data:\n"
            f"- Brand name: {profile.name}\n"
            f"- What it does: {profile.description or 'unknown'}\n"
            f"- Industry: {profile.industry}\n"
            f"- Audience: {profile.targetAudience}\n"
            f"- Tone: {profile.toneOfVoice}\n"
            f"- Content Pillars: {profile.contentPillars}\n"
        )
        offer = (getattr(profile, "primaryOffer", None) or "").strip()
        if offer:
            # Context only. This must NOT be written onto the screen: a full
            # offer sentence renders as garbled glyphs, which is exactly how
            # "Start free simulation -> Scan your domain -> Upgrade at 10 runs"
            # ended up burned into a video. The caption carries it verbatim.
            brand_context += (
                f"- What the ad should make a viewer want to do: {offer}\n"
                f"  (Context for the mood only — do NOT put this sentence on screen.)\n"
            )
    
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
        "lifestyle_integration": 50,
        "problem_agitation_solution": 50,
        "challenger_comparison": 50,
    }

    if "physical" in ptype.lower() or "apparel" in ptype.lower():
        weights["cinematic_showcase"] += 30
        weights["lifestyle_integration"] += 30
    else:
        weights["fast_cut_features"] += 30
        weights["ugc_testimonial"] += 20
        weights["problem_agitation_solution"] += 30
        weights["challenger_comparison"] += 25

    if goal == "conversion":
        weights["ugc_testimonial"] += 40
        weights["fast_cut_features"] += 20
        weights["problem_agitation_solution"] += 50
        weights["challenger_comparison"] += 45
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
        # The two highest-converting formats in the reference library, both
        # missing here. Their absence is why every creative was a showcase or a
        # demo and none of them opened on a problem the viewer recognises.
        "problem_agitation_solution": {
            "name": "Problem-Agitation-Solution",
            "description": "Opens on acute pain, holds it, resolves with the product as the hero.",
            "visual_world": "Opens cold, cluttered, overwhelming. Resolves calm, ordered, confident.",
            "camera_direction": "One continuous move — start tight on the problem, ease back as it resolves",
            "pacing": "Tense hold, then release",
            "text_treatment": "The hero string names the problem, not the product",
            "avoid": ["starting with the product", "a happy face before the problem lands", "generic office stock"]
        },
        "challenger_comparison": {
            "name": "Challenger Comparison",
            "description": "Old way versus new way — a category upgrade, without naming competitors.",
            "visual_world": "The old way is manual, slow, paper-heavy. The new way is one clean screen.",
            "camera_direction": "Locked-off static, the change happening within the frame",
            "pacing": "Slow frustration, confident resolution",
            "text_treatment": "One hero string carrying the new state",
            "avoid": ["naming competitors", "split screen", "generic 'vs' graphics"]
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
    
    # "Bloomberg-terminal darkness" used to be the note on dark_institutional.
    # It is also in validator.BANNED_VISUAL_CLICHES, so the modifier injected a
    # banned phrase into every prompt it touched.
    modifiers = [
        {"modifier": "golden_hour", "note": "Warm late afternoon sunlight, long shadows, amber tones", "weight": 1.2},
        {"modifier": "clean_daylight", "note": "Soft natural diffused light, bright airy environment", "weight": 1.0},
        {"modifier": "studio_dramatic", "note": "Controlled studio lighting, dramatic shadows and rim light", "weight": 0.9},
        {"modifier": "dark_institutional", "note": "Cold precision lighting, low ambient, quiet authority", "weight": 0.8},
        {"modifier": "urban_gritty", "note": "Raw city texture, candid feel, authentic locations", "weight": 0.7},
        {"modifier": "luxury_minimal", "note": "Negative space, precise lighting, premium material focus", "weight": 0.8},
        {"modifier": "macro_precision", "note": "Extreme close-up detail, texture and material as hero", "weight": 0.7},
    ]

    # Which lighting suits which vertical. Without this, every software product
    # took the dark branch and produced the same dim room every time.
    INDUSTRY_AFFINITY = {
        "fintech": ["dark_institutional", "clean_daylight", "studio_dramatic"],
        "developer_tools": ["dark_institutional", "clean_daylight"],
        "wellness": ["golden_hour", "clean_daylight", "macro_precision"],
        "fashion": ["golden_hour", "studio_dramatic", "luxury_minimal"],
        "food_beverage": ["macro_precision", "golden_hour", "clean_daylight"],
        "fitness": ["urban_gritty", "golden_hour"],
        "enterprise_saas": ["clean_daylight", "studio_dramatic", "dark_institutional"],
        "quantum_computing": ["studio_dramatic", "clean_daylight", "dark_institutional"],
        "edtech": ["clean_daylight", "golden_hour", "studio_dramatic"],
        "ecommerce": ["studio_dramatic", "clean_daylight", "macro_precision"],
        "luxury": ["luxury_minimal", "studio_dramatic", "golden_hour"],
    }

    def _weighted_pick(items, weight_of):
        total = sum(max(weight_of(i), 0.0) for i in items)
        if total <= 0:
            return random.choice(items)
        r = random.uniform(0, total)
        for item in items:
            r -= max(weight_of(item), 0.0)
            if r <= 0:
                return item
        return items[-1]

    # Weighted random, not argmax. `max()` is deterministic, so one business
    # received the identical format on every single run — which is why
    # consecutive prompts opened on the same camera move in the same room.
    format_keys = list(creative_formats.keys())
    recommended_format = _weighted_pick(format_keys, lambda k: weights[k])

    vertical = (
        intelligence_json.get("industry_visual_language", {}).get("vertical")
        or intelligence_json.get("product_intelligence", {}).get("product_category")
        or ""
    ).lower().replace(" ", "_")
    affinity = next(
        (v for k, v in INDUSTRY_AFFINITY.items() if k in vertical), []
    )
    variation_modifier = _weighted_pick(
        modifiers,
        lambda m: m["weight"] * (2.5 if m["modifier"] in affinity else 1.0),
    )

    return {
        "recommended_format": recommended_format,
        "format_weights": weights,
        "creative_format": creative_formats[recommended_format],
        "variation_modifier": variation_modifier
    }

def _recent_prompts_block(recent_prompts: Optional[list]) -> str:
    """Render already-used prompts as an explicit avoid-list.

    Telling a model to "be creative" does nothing; showing it exactly what it
    already produced and naming the axes it must change does.
    """
    cleaned = [str(p).strip() for p in (recent_prompts or []) if p and str(p).strip()]
    if not cleaned:
        return ""

    lines = [
        "",
        "═══════════════════════════════════════════════════════════",
        "ALREADY USED FOR THIS BRAND — DO NOT REPEAT",
        "═══════════════════════════════════════════════════════════",
        "These prompts were generated for this same business. Yours must be a",
        "visibly different piece of content, not a paraphrase.",
        "",
    ]
    for i, p in enumerate(cleaned[:6], 1):
        lines.append(f"{i}. {p[:400]}")
    lines += [
        "",
        "Your prompt MUST differ from every one above on at least THREE of these axes:",
        "  - the setting (a different room, surface, time of day or location)",
        "  - the camera (a different shot size, lens and movement)",
        "  - the opening beat (a different first frame — do not reuse the same hook)",
        "  - who or what is on screen (person vs product vs screen vs hands)",
        "  - the lighting (different direction, temperature and hardness)",
        "  - the on-screen line (different words and a different claim angle)",
        "If your draft reuses the same opening as any prompt above, discard it and",
        "write a different one.",
    ]
    return "\n".join(lines)


async def generate_prompt(
    intelligence: Dict[str, Any],
    creative_strategy: Dict[str, Any],
    image_url: str,
    recent_prompts: Optional[list] = None,
    duration_seconds: int = 10,
) -> str:
    """Generate the final video-model prompt for a vertical ad of a chosen length.

    `duration_seconds` is 8-30. The generators accept a range now, and a prompt
    written for ten seconds and rendered at thirty is not a longer ad -- it is
    the same ad with twenty seconds of drift after it. The beat sheet in
    services/video_beats.py divides whatever length was chosen and the prompt
    carries that clock explicitly, because these models follow a stated
    timeline far better than they follow a narrative.

    Length discipline is the whole game here. Text-to-video models degrade
    past roughly 120 words — they start dropping the subject, the on-screen
    line, or the camera move. A 150-word two-scene brief does not render as a
    richer video, it renders as a vaguer one, because there is no time for a
    second setup in ten seconds. Ninety to a hundred and twenty words spent on
    ONE decisive moment beats a two-act structure every time.
    """
    cf = creative_strategy.get("creative_format", {})
    vm = creative_strategy.get("variation_modifier", {})
    recent_block = _recent_prompts_block(recent_prompts)

    from services.video_beats import beat_sheet, clamp_duration

    duration_seconds = clamp_duration(duration_seconds)
    timed_structure = beat_sheet(duration_seconds)
    
    # Compute adaptive word budget based on clip length (8s -> 65-95 words, 30s -> 135-195 words)
    min_prompt_words = int(60 + (duration_seconds - 8) * 3.5)
    max_prompt_words = int(95 + (duration_seconds - 8) * 4.5)

    sys_message = f"""You are an elite commercial video director writing prompts for text-to-video diffusion models (Veo, Kling, Sora, Gen-3, Luma Dream Machine).

Generate ONE vertical (9:16) video prompt. It must follow the assigned creative format and the visual world of the product type.

TIMED STRUCTURE IS ABSOLUTE:
Every prompt MUST divide the clip according to the TIMED STRUCTURE block below.
Each range must be described in order, naming the VISUAL, the CAMERA MOVE, and the SPOKEN words.

THE HOOK (0-3s):
Opens ALREADY IN MOTION on frame one. No title cards, no logo animation, no fade-in.
The viewer decides in 3 seconds whether to keep scrolling. Give them a subject already mid-action or mid-reaction.

THE OUTRO (last 2s):
Resolves onto the closing card: brand name and offer, held still.

CAMERA:
ONE continuous camera move for the whole clip. Choose from: slow push-in, slow pull-back, slow pan, locked-off static, gentle handheld sway, slow overhead descent. Never cut, flip, rotate 180, or montage.

THE SURFACE:
Software and apps MUST name one physical surface where text lives (a laptop screen, a phone screen, a tablet, a monitor).
  Saying a screen "displays" something is not enough; the model puts a laptop
  where a laptop naturally goes. State the framing:
    GOOD: "camera over her shoulder, the screen square to frame and filling
           the upper half, showing 'Scan Complete' in large white text"
    BAD:  "turns to their laptop where the screen displays 'Scan Complete'"

THE SPOKEN LINE — ON EVERY CLIP, WITHOUT EXCEPTION.
Every prompt closes with a SPOKEN call to action naming the brand. Spoken, never written — burned on screen it renders as smeared glyphs; as speech it is perfect.
  GOOD: "Run your free scan at QuantCAI."
  GOOD: "Get secure with QuantCAI."
  GOOD: "Book a fitting at Ridgeline this week."
Build it from the business's own offer. Five to nine words.

THE BRAND WATERMARK — ON EVERY CLIP, WITHOUT EXCEPTION.
Close every prompt with the business name as a soft semi-transparent white
wordmark centred along the BOTTOM EDGE, holding for the whole clip. One
word. A render confirmed this comes back clean and legible.

BANNED PHRASES — these mark a prompt as machine filler:
"futuristic holographic", "neon-lit trading floor", "dynamic and vibrant",
"cutting-edge", "seamlessly", "in today's fast-paced world", floating UI
panels, flying data particles, glowing orbs, neon cityscapes, "Bloomberg
terminal", fish-eye, 180-degree rotations.

OUTPUT — valid JSON only. First character {{ and last character }}. No markdown, no array wrapper, no "output" key, no escaped newlines.
{{
  "creative_format_used": "<assigned format name>",
  "variation_modifier_applied": "<assigned modifier name>",
  "product_type": "<product type from marketing intel>",
  "prompt": "<the full timeline, reproduced EXACTLY in the block layout given above: one line per block reading TIME  ROLE, then an indented VISUAL line and an indented SCRIPT line with the spoken words in double quotes. Keep the indentation -- a person has to read this, find a block and edit one line. State subject, wardrobe, room and grade ONCE at the top, then never restate them. Close with one audio clause. No list of negatives.>"
}}

VOCABULARY WARNING — the prompt is read by a RENDERER, not by you. It must
describe only what a camera would see. Never carry a word from these
instructions into the prompt itself. Live output once read:

  BAD:  the laptop where the QuantCAI screen displays the hero string "Scan Complete"
  GOOD: the laptop screen showing "Scan Complete" in large white text

"hero string", "hero text", "voiceover", "brand moment", "on-screen text",
"camera move" and "call to action" are names for parts of a brief. A renderer
will attempt to draw them. Write the thing, never its label.
"""

    prompt = f"""Translate the product intelligence and assigned creative format below into ONE production-ready {duration_seconds}-second vertical video prompt.

═══════════════════════════════════════════════════════════
{timed_structure}
═══════════════════════════════════════════════════════════

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
  FILM THE INTERFACE. For software the screen is the product, and one large
  string on it renders accurately — that is what tells the viewer what this
  thing does. A shot with no readable product is a mood piece that could
  advertise anything.
  Subject: the screen itself, or one developer, analyst or founder with the
  screen clearly in frame.
  The hero string: the problem or the result, 2-6 words, large and central —
  a red alert banner, a chat box mid-typing, a notification card sliding in.
  Everything else on that screen is soft and out of focus.
  The moment: the result landing, and the reaction to it. Shoulders drop. A
  slow nod. A breath let out.
  Props: a mechanical keyboard, a cold coffee, a notebook — at most two.
  Never: small readable menus, tables or log output, holographic panels,
  flying data particles, glowing blue "AI" mist, "Bloomberg terminal".

SOCIAL_PAGE (a themed Instagram or Facebook page — the audience IS the product)
  There is nothing to sell and no founder to film. The page earns attention by
  being the best version of a feeling: aspiration, calm, awe, nostalgia. Every
  clip has to be worth a save or a share on its own.
  Subject: the SUBJECT MATTER itself, shot like the object of desire it is —
  the car, the watch face, the wake behind the yacht, the city at altitude.
  Never a person addressing camera, and never the page's operator.
  Camera: macro detail and slow reveals. Let one object fill the frame and hold.
  Hero string: a short line the viewer would repost, not a sales claim. Two to
  five words. "Six years of saying no." beats "Luxury lifestyle".
  Spoken line: optional, and often better absent — these pages are watched
  muted. If present, keep it a single observation, never a pitch.
  Closing ask: FOLLOW, never buy. There is no purchase to make.
  Never: stock-photo wealth cliches (cash fans, private-jet stairs in a suit),
  and never a claim about what the viewer will earn or achieve.

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

RULE 2 — ONE MOVE PER BEAT. VERTICAL 9:16.
Each beat in the TIMED STRUCTURE is one continuous take with one camera move chosen from: slow push-in, slow
pull-back, slow pan, locked-off static, gentle handheld sway, slow overhead
descent. No cuts. No "then it flips". No rotations. No montages.

RULE 3 — NOTHING LEGIBLE ON ANY SCREEN. The model cannot draw interfaces; it
draws smeared pseudo-text. If a screen appears, it is light and colour only,
out of focus. Never state what it displays.

RULE 4 — ON-SCREEN TEXT: 1-4 WORDS, ONCE, OR NONE.
In double quotes. Usually the brand name alone. Longer text renders as
gibberish, so the offer sentence goes in the caption instead of the video.

RULE 5 — BRAND COLOR ON REAL SURFACES. Use the brand's colour names on things
that would plausibly carry them — a wall, a jacket, a mug, light spilling from
a screen. Never as free-floating glow. Never as a hex code.

RULE 6 — THE VARIATION MODIFIER MUST BE VISIBLE. It has to change the
atmosphere, the lighting, or the camera in a way a viewer would notice. This is
what stops every video for this brand looking identical.

RULE 7 — INVENT NOTHING. No statistics, prices, ratings or claims absent from
the input data.

RULE 8 — {min_prompt_words}-{max_prompt_words} WORDS. Density is the
enemy: three vivid elements beat nine listed ones.

RULE 9 — IT MUST SELL, NOT JUST LOOK GOOD. This is an ad. The strongest moment
in almost every case is a HUMAN REACTION — the second the result lands, the
shoulders dropping, the slow nod, the breath let out. Choose that over any
establishing shot, and over any attempt to show the product's interface.

RULE 10 — ONE SUBJECT, ONE ACTION, ONE PLACE. Name a single subject and give it
a single physical action. At most two atmosphere details. A face AND a screen
AND hands AND steam AND a keyboard is five subjects competing for fidelity, and
all five come out mushy.
{recent_block}
Return the JSON object and nothing else.
"""

    from services.ai_service import _call_openrouter

    combined_prompt = f"{sys_message}\n\nUSER PROMPT:\n{prompt}"

    def _extract(raw: str) -> str:
        """Pull the prompt text out of whatever shape the model returned.

        Free models are inconsistent: some honour response_format, some wrap
        the object in an array, some emit a bare string, some fence it in
        markdown. Every one of those used to be able to yield an empty result,
        which reached the user as an asset with no prompt at all.
        """
        cleaned = (raw or "").strip()
        if not cleaned:
            return ""

        if cleaned.startswith("```"):
            parts = cleaned.split("\n", 1)
            cleaned = parts[1] if len(parts) > 1 else ""
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3]
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except Exception:
            # Not JSON at all — a bare prompt is perfectly usable.
            return cleaned

        # Some models wrap the object in a list, or under an "output" key.
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        if isinstance(parsed, dict) and "prompt" not in parsed:
            for key in ("output", "result", "data", "response"):
                inner = parsed.get(key)
                if isinstance(inner, dict) and "prompt" in inner:
                    parsed = inner
                    break

        if isinstance(parsed, dict):
            value = parsed.get("prompt")
            if isinstance(value, str) and value.strip():
                return value.strip()
            # JSON with no usable prompt field — the raw text beats nothing.
            logger.warning("Video prompt JSON carried no usable 'prompt' field")
            return cleaned
        if isinstance(parsed, str) and parsed.strip():
            return parsed.strip()
        return cleaned

    result = await _call_openrouter(combined_prompt, model=TEXT_MODEL, json_response=True)
    generated = _extract(result)

    if not generated:
        # Asking for JSON is itself a failure mode: several free models reject
        # response_format outright. Retry in plain text before giving up.
        logger.warning("Video prompt came back empty; retrying without JSON mode")
        plain = await _call_openrouter(
            combined_prompt
            + "\n\nIMPORTANT: reply with the prompt text ONLY — no JSON, no keys, "
            "no markdown, no preamble.",
            model=TEXT_MODEL,
        )
        generated = _extract(plain)

    if not generated:
        # Never hand back an empty string: the caller cannot tell an empty
        # prompt from a successful one, and the user gets a blank asset.
        raise RuntimeError(
            "The AI returned an empty prompt after two attempts."
        )

    return _enforce_speech_starts_immediately(_strip_brief_vocabulary(generated))


# Names for the PARTS of a brief. The renderer has no idea these are labels and
# will attempt to draw them. Live output reached the dashboard reading "the
# QuantCAI screen displays the hero string "Scan Complete"" — the words "hero
# string" would have been rendered onto the laptop.
#
# The instruction not to do this lives in the brief, but an instruction is a
# request and this is a correctness property, so it is also enforced here.
_BRIEF_VOCABULARY = [
    (r"\bdisplays the hero[ _-]?(?:string|text)\b", "displays"),
    (r"\bshows the hero[ _-]?(?:string|text)\b", "shows"),
    (r"\breads the hero[ _-]?(?:string|text)\b", "reads"),
    (r"\bthe hero[ _-]?(?:string|text)\b", "the text"),
    (r"\bhero[ _-]?(?:string|text)\b", "text"),
    (r"\bon[ _-]?screen[ _-]?text:\s*", ""),
    (r"\bvoice[ _-]?over:\s*", ""),
    (r"\bvoiceover\b", "spoken line"),
    (r"\bbrand[ _-]?moment\b", "brand mark"),
    (r"\bcall[ _-]to[ _-]action\b", "closing line"),
    (r"\bcamera[ _-]?vector\b", "camera move"),
    (r"\bhero[ _-]?surface\b", "surface"),
]


def _strip_brief_vocabulary(text: str) -> str:
    """Remove schema words a video model would try to render."""
    import re as _re

    cleaned = text
    for pattern, replacement in _BRIEF_VOCABULARY:
        cleaned, n = _re.subn(pattern, replacement, cleaned, flags=_re.IGNORECASE)
        if n:
            logger.info(f"Stripped brief vocabulary from prompt: {pattern}")
    # Collapse the double spaces a removal can leave behind.
    cleaned = _re.sub(r"\s{2,}", " ", cleaned)
    return _re.sub(r"\s+([,.])", r"\1", cleaned).strip()


def _beats_summary(duration_seconds: int) -> Dict[str, Any]:
    from services.video_beats import summary

    return summary(duration_seconds)


async def execute_video_pipeline(
    product_name: str,
    product_url: Optional[str] = None,
    image_url: str = "",
    goal: str = "conversion",
    profile: Optional[Any] = None,
    recent_prompts: Optional[list] = None,
    duration_seconds: int = 10,
) -> Dict[str, Any]:
    """Execute the full end-to-end creative video pipeline.

    `recent_prompts` is what this business has already generated. Without it
    every run started from the same brand profile and creative format and
    produced near-identical scenes, so a feed of these videos looked like one
    video posted repeatedly.
    """
    logger.info(f"Starting video pipeline for {product_name}")

    # 1-3. Understand the business. Reuse the stored understanding when the
    # workspace already has one — this used to scrape, run vision, and
    # synthesise on every single prompt, discarding the result each time, so
    # the same business could be described differently from one run to the
    # next. See services/brand_intelligence.py.
    intelligence = None
    if profile is not None:
        try:
            from database import AsyncSessionLocal
            from services.brand_intelligence import get_or_build

            async with AsyncSessionLocal() as session:
                fresh = await session.get(type(profile), profile.id)
                intelligence, built = await get_or_build(
                    session, fresh or profile, image_url=image_url
                )
                if built:
                    logger.info("Brand intelligence built and stored for reuse")
        except Exception as e:
            logger.warning(f"Stored brand intelligence unavailable, deriving inline: {e}")

    if not intelligence:
        scrape_content = await scrape_product_url(product_url)
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
        intelligence = await marketing_intelligence_synthesis(
            product_name, scrape_content, vision_yaml, profile
        )

    # 4. Creative Engine
    creative_strategy = run_creative_engine(intelligence, goal)
    
    # 5. Prompt Generation
    final_prompt = await generate_prompt(
        intelligence, creative_strategy, image_url,
        recent_prompts=recent_prompts, duration_seconds=duration_seconds,
    )
    
    # 6. Keyframes. The clip is generated BETWEEN two stills: the first locks
    #    the look, the last carries the brand name and the offer as real text
    #    an image model can actually spell. See services/keyframes.py.
    keyframes = {}
    if profile is not None:
        try:
            from services.keyframes import build_keyframes

            keyframes = await build_keyframes(
                profile, intelligence, recent_prompts=recent_prompts
            )
        except Exception as e:
            # A missing pair of stills is a weaker creative, not a failed one.
            logger.warning(f"Keyframe prompts unavailable: {e}")

    logger.info("Video pipeline completed successfully.")

    return {
        "status": "success",
        "intelligence": intelligence,
        "creative_strategy": creative_strategy,
        "veo_prompt": final_prompt,
        "image_url": image_url,
        "keyframes": keyframes,
        "plan": _beats_summary(duration_seconds),
    }





# The spoken line has to begin at frame one. A rendered test of a prompt from
# this path came back near-silent until 3.5 seconds — room tone over a man
# closing a notebook — which threw away the verbal third of Meta's tripartite
# hook and, in a feed, the whole ad.
#
# The brief asks for it, but a brief is a request. Enforced here because the
# failure is silent: the prompt reads perfectly and only the render shows it.
_DIALOGUE_START = re.compile(
    r'(?<![\w"])"([^"]{25,})"',   # a quoted string long enough to be a sentence
)

# Wording that already pins the start. Matching any of these means leave it be.
_ALREADY_TIMED = re.compile(
    r"\b(from the (?:very )?first frame|speaking immediately|starts? speaking "
    r"at once|already (?:speaking|mid-sentence)|first word lands)\b",
    re.IGNORECASE,
)


def _enforce_speech_starts_immediately(text: str) -> str:
    """Pin the spoken line to frame one if the prompt left it floating."""
    if _ALREADY_TIMED.search(text):
        return text

    match = _DIALOGUE_START.search(text)
    if not match:
        return text

    line = match.group(1)
    # A CTA is short and trails the clip; the opening line is the one that has
    # to land at zero, so prefer the first long quote.
    if len(line.split()) < 6:
        return text

    # Phrased positively: "no pause before the first word" reads naturally but
    # the leading "no " trips check_model_negative_syntax, which rejects
    # negative wording in a Runway positive prompt.
    prefixed = (
        text[: match.start()]
        + f'already speaking as the first frame begins: "{line}"'
        + text[match.end():]
    )
    logger.info("Pinned the spoken line to the first frame")
    return prefixed
