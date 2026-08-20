"""Pydantic models for the prompt engine API.

These schemas define request and response payloads for video prompt
generation, caption generation, model prompt payloads, and validation results.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field


class ModelPromptPayload(BaseModel):
    """Structured compiled prompt output tailored to target video generator."""

    model_name: str = Field(..., description="Target video model: runway, kling, veo, sora, pika")
    positive_prompt: str = Field(..., description="The main text prompt payload")
    negative_prompt: Optional[Union[str, List[str]]] = Field(None, description="Negative prompt string or array if supported")
    camera_movement: Optional[str] = Field(None, description="Specific continuous camera vector")
    scene_description: Optional[str] = Field(None, description="Single isolated environment description")
    action_description: Optional[str] = Field(None, description="Single continuous motion description")
    audio_tags: Optional[str] = Field(None, description="Simple ambient audio tags e.g. <<rain on glass>>")
    reference_image_base64: Optional[str] = Field(None, description="Base64 encoded reference asset")
    seed: Optional[int] = Field(None, description="Pinned random noise seed")
    word_count: int = Field(0, description="Token/word count of positive prompt")
    model_specific_payload: Dict[str, Any] = Field(default_factory=dict, description="Raw format sent to model API")


class PromptCreateRequest(BaseModel):
    """Payload for creating a new video prompt."""

    business_profile_id: str = Field(..., description="BusinessProfile identifier (workspace)")
    intent: str = Field(..., description="Short description of creative goal, e.g. 'Show product in use'")
    model_name: Optional[str] = Field("runway", description="Target video model (runway, kling, veo, sora, pika)")
    brand_aesthetic: Optional[str] = Field(None, description="Visual aesthetic anchor")
    customer_motivator: Optional[str] = Field(None, description="Target customer motivator vector")
    camera_vector: Optional[str] = Field(None, description="Explicit continuous camera movement directive")
    product_image_base64: Optional[str] = Field(None, description="Base64 brand asset for subject persistence")
    seed: Optional[int] = Field(None, description="Noise seed for variation without identity drift")
    extra_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional model parameters")


class PromptCreateResponse(BaseModel):
    id: str = Field(..., description="PromptVersion ID")
    version: int = Field(..., description="Version number for this prompt")
    model_name: str = Field(..., description="Target model used")
    prompt_json: Dict[str, Any] = Field(..., description="The model-specific compiled payload")
    positive_prompt: str = Field(..., description="Extracted positive prompt string")
    negative_prompt: Optional[Union[str, List[str]]] = Field(None, description="Extracted negative prompt string/list")
    created_at: datetime = Field(..., alias="createdAt")
    is_valid: bool = Field(..., description="Result of validation step")
    validation_errors: List[str] = Field(default_factory=list, description="Any validation failures")
    errors: List[str] = Field(default_factory=list, description="Validation failure messages")

    model_config = {"populate_by_name": True}


class CaptionCreateRequest(BaseModel):
    business_profile_id: str = Field(..., description="BusinessProfile identifier (workspace)")
    product_feature: str = Field(..., description="Key product feature or benefit to highlight")
    customer_motivator: Optional[str] = Field(None, description="Functional or emotional motivator barrier")
    brand_language_anchor: Optional[str] = Field(None, description="Quote or verbatim feature description from brand")
    website_rag_context: Optional[List[str]] = Field(default_factory=list, description="Client website text snippets for FTC claim substantiation")
    model_name: Optional[str] = Field("llama-3-8b", description="SLM model to use for caption generation")
    extra_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context for RAG")


class CaptionCreateResponse(BaseModel):
    caption: str = Field(..., description="Generated caption text")
    customer_motivator_addressed: Optional[str] = Field(None, description="Motivator used")
    is_valid: bool = Field(..., description="Validation outcome")
    validation_errors: List[str] = Field(default_factory=list)
    detailed_checks: Dict[str, bool] = Field(default_factory=dict, description="Per-gate validation outcomes")


class PromptValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    claim_substantiated: bool = True
    reviewer_voice_free: bool = True
    audience_leakage_free: bool = True
    visual_density_valid: bool = True
    physics_and_cut_valid: bool = True
    exhausted_opener_free: bool = True
    near_duplicate_free: bool = True
    model_negative_syntax_valid: bool = True
    audio_word_budget_valid: bool = True
    background_text_suppression_valid: bool = True
    subject_count_valid: bool = True
    caption_sentence_count_valid: bool = True


class CaptionValidateRequest(BaseModel):
    """Payload for standalone caption validation (no generation)."""

    business_profile_id: str = Field(..., description="BusinessProfile identifier (workspace)")
    caption: str = Field(..., description="Caption text to validate")
    customer_motivator: Optional[str] = Field(None, description="Functional or emotional motivator")
    website_rag_context: Optional[List[str]] = Field(default_factory=list, description="Client website text snippets for FTC claim check")


class GoldenDatasetEvalRequest(BaseModel):
    dataset_name: Optional[str] = Field("default_golden_dataset", description="Name of golden dataset")


class GoldenDatasetEvalResponse(BaseModel):
    total_samples: int
    safety_pass_rate: float
    heuristic_pass_rate: float
    passed_ci_gate: bool
    details: List[Dict[str, Any]] = Field(default_factory=list)

