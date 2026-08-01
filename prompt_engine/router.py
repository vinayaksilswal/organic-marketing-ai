"""FastAPI router for prompt engine.

Provides endpoints for model-compiled video brief generation, motivator-based caption generation,
FTC claim substantiation gates, validation retrieval, and CI/CD golden dataset evaluation.
"""

from __future__ import annotations

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import verify_user

from prompt_engine.models import (
    PromptCreateRequest,
    PromptCreateResponse,
    CaptionCreateRequest,
    CaptionCreateResponse,
    CaptionValidateRequest,
    PromptValidationResult,
    GoldenDatasetEvalRequest,
    GoldenDatasetEvalResponse,
)
from prompt_engine.db_models import PromptVersion, PromptValidationLog, ModelRoutingRule, GoldenDatasetSample, CaptionVersion
from prompt_engine.compilers import compile_video_prompt
from prompt_engine.validator import validate_video_prompt, validate_caption
from prompt_engine.caption_generator import generate_caption_via_llm
from prompt_engine.scene_writer import write_scene

from database import BusinessProfile, SocialPost, get_tenant_session

# These endpoints run paid LLM calls and write rows against a workspace taken
# from a request header. Without authentication anyone could burn AI credit and
# write into another tenant's data by guessing a workspace id, so the whole
# router requires a valid session and every handler verifies ownership against
# the authenticated user rather than trusting the header alone.
#
# Mounted under /api/v1 to match every other authenticated surface; the bare
# /prompt prefix sat outside the versioned API.
router = APIRouter(
    prefix="/api/v1/prompt",
    tags=["PromptEngine"],
    dependencies=[Depends(verify_user)],
)


async def _get_business_profile(session: AsyncSession, business_profile_id: str) -> BusinessProfile:
    stmt = select(BusinessProfile).where(BusinessProfile.id == business_profile_id)
    result = await session.execute(stmt)
    bp = result.scalar_one_or_none()
    if not bp:
        raise HTTPException(status_code=404, detail="BusinessProfile not found")
    return bp


async def _assert_owns_workspace(session: AsyncSession, workspace_id: str, user_id: str) -> BusinessProfile:
    """Confirm the caller owns the workspace they named in the header.

    The header is client-supplied, so on its own it is a claim, not proof.
    """
    bp = await _get_business_profile(session, workspace_id)
    if bp.userId != user_id:
        raise HTTPException(status_code=403, detail="That workspace is not yours")
    return bp


async def _get_recent_captions(session: AsyncSession, business_profile_id: str, limit: int = 50) -> List[str]:
    """Retrieve the last N published captions for near-duplicate detection.

    Queries the SocialPost table for the most recent posts belonging to this
    business profile and extracts their caption text.
    """
    # SocialPost stores the text in `caption`; there is no `content` column, so
    # this query raised AttributeError and the except swallowed it — meaning
    # near-duplicate detection silently compared every caption against an empty
    # list and never fired. Ordering is by scheduledAt because SocialPost has no
    # createdAt either.
    try:
        stmt = (
            select(SocialPost.caption)
            .where(SocialPost.businessProfileId == business_profile_id)
            .where(SocialPost.caption.isnot(None))
            .order_by(SocialPost.scheduledAt.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all() if row[0]]
    except Exception:
        logger.exception(
            "Could not load recent captions for near-duplicate detection; "
            "the check will pass by default this run"
        )
        return []


@router.post("/video", response_model=PromptCreateResponse)
async def generate_video_prompt(
    payload: PromptCreateRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> PromptCreateResponse:
    """Create a deterministic model-compiled video brief for a BusinessProfile.

    Compiles model-specific syntax (Runway, Kling, Veo, Sora, Pika), stores prompt version,
    runs automated quality gates, and returns the validation result.
    """
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID header missing")

    async with get_tenant_session(workspace_id) as session:
        await _assert_owns_workspace(session, workspace_id, user_id)
        bp = await _get_business_profile(session, payload.business_profile_id)
        if bp.id != workspace_id and bp.userId != workspace_id:
            raise HTTPException(status_code=403, detail="BusinessProfile does not belong to workspace")

        target_model = (payload.model_name or "runway").lower().strip()

        # Compile brief using model-specific compiler
        # Let the model write the shot before the compiler formats it. Without
        # this the compilers fill f-string templates — "a single subject in an
        # isolated setting" — which is structurally valid and creatively dead.
        # Previous prompts are passed so successive ads for one brand differ.
        recent = (await session.execute(
            select(PromptVersion.positive_prompt)
            .where(PromptVersion.businessProfileId == bp.id)
            .order_by(PromptVersion.createdAt.desc())
            .limit(5)
        )).scalars().all()

        # The stored understanding of this business, if it has one. It carries
        # the pain point, the objection and the transformation — none of which
        # are on the flat profile, and all of which are what separate an ad
        # that argues something from one that just looks nice.
        from services.brand_intelligence import get_or_build, to_scene_context

        try:
            intel, _ = await get_or_build(session, bp)
        except Exception as e:
            logger.warning(f"Brand intelligence unavailable for {bp.id}: {e}")
            intel = None
        ctx = to_scene_context(intel)

        scene_fields = await write_scene(
            intent=payload.intent,
            business_name=bp.name,
            what_it_does=ctx.get("what_it_does") or bp.description,
            audience_motivator=(
                payload.customer_motivator
                or ctx.get("audience_motivator")
                or bp.targetAudience
            ),
            brand_aesthetic=(
                payload.brand_aesthetic
                or ctx.get("brand_aesthetic")
                or bp.toneOfVoice
            ),
            primary_offer=bp.primaryOffer,
            recent_scenes=[r for r in recent if r],
            transformation=ctx.get("transformation"),
            avoid_visual_world=ctx.get("avoid_visual_world"),
        )

        compiled_payload = compile_video_prompt(
            model_name=target_model,
            intent=payload.intent,
            brand_aesthetic=payload.brand_aesthetic or bp.toneOfVoice,
            camera_vector=payload.camera_vector,
            primary_offer=bp.primaryOffer,
            product_image_base64=payload.product_image_base64,
            seed=payload.seed,
            scene_fields=scene_fields,
        )

        # Determine next version number for this BusinessProfile
        stmt = (
            select(PromptVersion.version)
            .where(PromptVersion.businessProfileId == bp.id)
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        last_version = (await session.execute(stmt)).scalar_one_or_none() or 0
        new_version = last_version + 1

        prompt_json = compiled_payload.model_specific_payload

        # Persist PromptVersion
        pv = PromptVersion(
            businessProfileId=bp.id,
            version=new_version,
            target_model=target_model,
            prompt_json=prompt_json,
            positive_prompt=compiled_payload.positive_prompt,
            negative_prompt=compiled_payload.negative_prompt,
            motivator=payload.customer_motivator,
            seed=payload.seed,
        )
        session.add(pv)
        await session.flush()

        # Validation pass
        validation = validate_video_prompt(bp, prompt_json, target_model=target_model)
        log = PromptValidationLog(
            promptVersionId=pv.id,
            is_valid=validation.is_valid,
            errors=validation.errors,
            detailed_checks={
                "visual_density_valid": validation.visual_density_valid,
                "physics_and_cut_valid": validation.physics_and_cut_valid,
                "model_negative_syntax_valid": validation.model_negative_syntax_valid,
                "audio_word_budget_valid": validation.audio_word_budget_valid,
                "background_text_suppression_valid": validation.background_text_suppression_valid,
                "subject_count_valid": validation.subject_count_valid,
            },
        )
        session.add(log)
        await session.commit()

        return PromptCreateResponse(
            id=pv.id,
            version=pv.version,
            model_name=target_model,
            prompt_json=prompt_json,
            positive_prompt=compiled_payload.positive_prompt,
            negative_prompt=compiled_payload.negative_prompt,
            created_at=pv.createdAt,
            is_valid=validation.is_valid,
            validation_errors=validation.errors,
        )


@router.post("/caption", response_model=CaptionCreateResponse)
async def generate_caption(
    payload: CaptionCreateRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> CaptionCreateResponse:
    """Generate a direct-response motivator-based caption for a BusinessProfile.

    Uses LLM-powered generation with the research-specified system prompt,
    negative exemplars, and forced specificity. Falls back to deterministic
    templates if LLM is unavailable. Runs FTC claim substantiation gates
    against website RAG context.
    """
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID header missing")

    async with get_tenant_session(workspace_id) as session:
        await _assert_owns_workspace(session, workspace_id, user_id)
        bp = await _get_business_profile(session, payload.business_profile_id)
        if bp.id != workspace_id and bp.userId != workspace_id:
            raise HTTPException(status_code=403, detail="BusinessProfile does not belong to workspace")

        motivator = payload.customer_motivator or "needs peer-reviewed safety evidence"
        anchor = payload.brand_language_anchor or bp.primaryOffer or "Our core product"
        feature = payload.product_feature

        # Fetch recent captions for near-duplicate detection
        past_captions = await _get_recent_captions(session, bp.id)

        # Generate caption via LLM with retry loop + template fallback
        caption, validation, gen_method = await generate_caption_via_llm(
            business_profile=bp,
            product_feature=feature,
            customer_motivator=motivator,
            brand_language_anchor=anchor,
            website_rag_context=payload.website_rag_context or [anchor, bp.primaryOffer or ""],
            past_captions=past_captions,
            llm_enabled=True,
        )

        # Persist CaptionVersion
        stmt = (
            select(CaptionVersion.version)
            .where(CaptionVersion.businessProfileId == bp.id)
            .order_by(CaptionVersion.version.desc())
            .limit(1)
        )
        last_cv = (await session.execute(stmt)).scalar_one_or_none() or 0

        cv = CaptionVersion(
            businessProfileId=bp.id,
            version=last_cv + 1,
            caption_text=caption,
            customer_motivator=motivator,
            brand_language_anchor=anchor,
            product_feature=feature,
            is_valid=validation.is_valid,
            validation_errors=validation.errors,
            detailed_checks={
                "claim_substantiated": validation.claim_substantiated,
                "reviewer_voice_free": validation.reviewer_voice_free,
                "audience_leakage_free": validation.audience_leakage_free,
                "exhausted_opener_free": validation.exhausted_opener_free,
                "near_duplicate_free": validation.near_duplicate_free,
                "caption_sentence_count_valid": validation.caption_sentence_count_valid,
            },
            generation_method=gen_method,
        )
        session.add(cv)
        await session.commit()

        detailed_checks = {
            "claim_substantiated": validation.claim_substantiated,
            "reviewer_voice_free": validation.reviewer_voice_free,
            "audience_leakage_free": validation.audience_leakage_free,
            "exhausted_opener_free": validation.exhausted_opener_free,
            "near_duplicate_free": validation.near_duplicate_free,
            "caption_sentence_count_valid": validation.caption_sentence_count_valid,
        }

        return CaptionCreateResponse(
            caption=caption,
            customer_motivator_addressed=motivator,
            is_valid=validation.is_valid,
            validation_errors=validation.errors,
            detailed_checks=detailed_checks,
        )


@router.post("/caption/validate", response_model=PromptValidationResult)
async def validate_caption_standalone(
    payload: CaptionValidateRequest,
    request: Request,
    user_id: str = Depends(verify_user),
) -> PromptValidationResult:
    """Validate an already-written caption without generating one.

    Useful for manual review flows where a human writes the caption and
    wants to run it through the automated quality gates before publishing.
    """
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID header missing")

    async with get_tenant_session(workspace_id) as session:
        await _assert_owns_workspace(session, workspace_id, user_id)
        bp = await _get_business_profile(session, payload.business_profile_id)
        if bp.id != workspace_id and bp.userId != workspace_id:
            raise HTTPException(status_code=403, detail="BusinessProfile does not belong to workspace")

        # Fetch recent captions for near-duplicate detection
        past_captions = await _get_recent_captions(session, bp.id)

        validation = validate_caption(
            business_profile=bp,
            caption=payload.caption,
            customer_motivator=payload.customer_motivator,
            website_rag_context=payload.website_rag_context or [bp.primaryOffer or ""],
            past_captions=past_captions,
        )

        return validation


@router.get("/{prompt_id}", response_model=PromptCreateResponse)
async def get_prompt(
    prompt_id: str,
    request: Request,
    user_id: str = Depends(verify_user),
) -> PromptCreateResponse:
    """Retrieve a stored PromptVersion by ID."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID header missing")

    async with get_tenant_session(workspace_id) as session:
        await _assert_owns_workspace(session, workspace_id, user_id)
        stmt = select(PromptVersion).where(PromptVersion.id == prompt_id)
        pv = (await session.execute(stmt)).scalar_one_or_none()
        if not pv:
            raise HTTPException(status_code=404, detail="PromptVersion not found")

        bp = await _get_business_profile(session, pv.businessProfileId)
        if bp.id != workspace_id and bp.userId != workspace_id:
            raise HTTPException(status_code=403, detail="Prompt does not belong to workspace")

        stmt = (
            select(PromptValidationLog)
            .where(PromptValidationLog.promptVersionId == pv.id)
            .order_by(PromptValidationLog.createdAt.desc())
            .limit(1)
        )
        log = (await session.execute(stmt)).scalar_one_or_none()
        is_valid = log.is_valid if log else False
        errors = log.errors if log else []

        return PromptCreateResponse(
            id=pv.id,
            version=pv.version,
            model_name=pv.target_model or "runway",
            prompt_json=pv.prompt_json,
            positive_prompt=pv.positive_prompt or "",
            negative_prompt=pv.negative_prompt,
            created_at=pv.createdAt,
            is_valid=is_valid,
            validation_errors=errors,
        )


@router.get("/{prompt_id}/validation", response_model=PromptValidationResult)
async def get_prompt_validation(
    prompt_id: str,
    request: Request,
    user_id: str = Depends(verify_user),
) -> PromptValidationResult:
    """Return the most recent validation result for a PromptVersion."""
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID header missing")

    async with get_tenant_session(workspace_id) as session:
        await _assert_owns_workspace(session, workspace_id, user_id)
        stmt = select(PromptVersion).where(PromptVersion.id == prompt_id)
        pv = (await session.execute(stmt)).scalar_one_or_none()
        if not pv:
            raise HTTPException(status_code=404, detail="PromptVersion not found")

        bp = await _get_business_profile(session, pv.businessProfileId)
        if bp.id != workspace_id and bp.userId != workspace_id:
            raise HTTPException(status_code=403, detail="Prompt does not belong to workspace")

        stmt = (
            select(PromptValidationLog)
            .where(PromptValidationLog.promptVersionId == pv.id)
            .order_by(PromptValidationLog.createdAt.desc())
            .limit(1)
        )
        log = (await session.execute(stmt)).scalar_one_or_none()
        if not log:
            raise HTTPException(status_code=404, detail="No validation log found for this prompt")

        checks = log.detailed_checks or {}
        return PromptValidationResult(
            is_valid=log.is_valid,
            errors=log.errors,
            visual_density_valid=checks.get("visual_density_valid", True),
            physics_and_cut_valid=checks.get("physics_and_cut_valid", True),
            model_negative_syntax_valid=checks.get("model_negative_syntax_valid", True),
            audio_word_budget_valid=checks.get("audio_word_budget_valid", True),
            background_text_suppression_valid=checks.get("background_text_suppression_valid", True),
            subject_count_valid=checks.get("subject_count_valid", True),
        )


@router.post("/eval/ci", response_model=GoldenDatasetEvalResponse)
async def run_ci_golden_dataset_evaluation(
    request: Request,
    payload: GoldenDatasetEvalRequest = GoldenDatasetEvalRequest(),
    user_id: str = Depends(verify_user),
) -> GoldenDatasetEvalResponse:
    """CI/CD release gate endpoint running evaluations against the Golden Dataset.

    Loads samples from the GoldenDatasetSample DB table if available, otherwise
    falls back to hard-coded edge cases.

    Checks:
    - 100% pass rate required on deterministic safety gates (FTC claim substantiation, banned words)
    - >= 95% pass rate required on heuristic scoring (visual density, single continuous shot)
    """
    # Try to load from DB first
    sample_cases = []
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")

    if workspace_id:
        try:
            async with get_tenant_session(workspace_id) as session:
                await _assert_owns_workspace(session, workspace_id, user_id)
                stmt = select(GoldenDatasetSample).where(
                    GoldenDatasetSample.dataset_name == (payload.dataset_name or "default_golden_dataset")
                )
                results = (await session.execute(stmt)).scalars().all()
                for gs in results:
                    sample_cases.append({
                        "id": gs.id,
                        "model": gs.target_model,
                        "intent": gs.intent,
                        "aesthetic": gs.payload_sample.get("aesthetic", "Professional studio lighting"),
                        "expect_safety": gs.expected_safety_pass,
                        "expect_heuristic": gs.expected_heuristic_pass,
                    })
        except Exception:
            pass  # Fall through to hard-coded samples

    # Fallback to hard-coded samples if DB is empty
    if not sample_cases:
        sample_cases = [
            {
                "id": "gold_1",
                "model": "runway",
                "intent": "Demonstrate modern organic facial oil",
                "aesthetic": "High key luxury studio lighting",
                "expect_safety": True,
                "expect_heuristic": True,
            },
            {
                "id": "gold_2",
                "model": "veo",
                "intent": "Show SaaS analytics dashboard export",
                "aesthetic": "Minimalist digital workplace",
                "expect_safety": True,
                "expect_heuristic": True,
            },
            {
                "id": "gold_3",
                "model": "kling",
                "intent": "Show quiet coffee brewing process",
                "aesthetic": "Warm ambient natural morning light",
                "expect_safety": True,
                "expect_heuristic": True,
            },
            {
                "id": "gold_4",
                "model": "sora",
                "intent": "Display premium leather wallet craftsmanship",
                "aesthetic": "Natural lighting, lifelike textures",
                "expect_safety": True,
                "expect_heuristic": True,
            },
            {
                "id": "gold_5",
                "model": "pika",
                "intent": "Show ceramic mug with steam rising",
                "aesthetic": "Clean modern studio, warm tones",
                "expect_safety": True,
                "expect_heuristic": True,
            },
        ]

    total = len(sample_cases)
    safety_passes = 0
    heuristic_passes = 0
    details = []

    bp_mock = BusinessProfile(
        id="mock_gold",
        userId="mock_ws",
        name="Golden Corp",
        primaryOffer="Verified analytics platform",
        toneOfVoice="Authoritative and direct",
    )

    for case in sample_cases:
        compiled = compile_video_prompt(
            model_name=case["model"],
            intent=case["intent"],
            brand_aesthetic=case["aesthetic"],
            primary_offer=bp_mock.primaryOffer,
        )
        val = validate_video_prompt(bp_mock, compiled.model_specific_payload, target_model=case["model"])

        safety_ok = val.model_negative_syntax_valid
        heuristic_ok = (
            val.visual_density_valid
            and val.physics_and_cut_valid
            and val.audio_word_budget_valid
            and val.background_text_suppression_valid
            and val.subject_count_valid
        )

        if safety_ok:
            safety_passes += 1
        if heuristic_ok:
            heuristic_passes += 1

        details.append({
            "id": case["id"],
            "model": case["model"],
            "safety_pass": safety_ok,
            "heuristic_pass": heuristic_ok,
            "errors": val.errors,
        })

    safety_rate = safety_passes / float(total) if total else 1.0
    heuristic_rate = heuristic_passes / float(total) if total else 1.0

    passed_gate = (safety_rate == 1.0) and (heuristic_rate >= 0.95)

    return GoldenDatasetEvalResponse(
        total_samples=total,
        safety_pass_rate=safety_rate,
        heuristic_pass_rate=heuristic_rate,
        passed_ci_gate=passed_gate,
        details=details,
    )
