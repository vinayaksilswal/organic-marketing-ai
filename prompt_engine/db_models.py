"""SQLAlchemy models for prompt engineering.

These models extend the existing Base defined in `database.py` and provide:
- versioned prompts (`PromptVersion`)
- validation logs (`PromptValidationLog`)
- model‑specific routing rules (`ModelRoutingRule`)
- golden dataset samples for CI/CD offline evaluation (`GoldenDatasetSample`)
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, ForeignKey, UniqueConstraint, Text, Float
from sqlalchemy.orm import backref, relationship
from datetime import datetime
from database import Base, generate_uuid, utc_now


class PromptVersion(Base):
    __tablename__ = "PromptVersion"

    id = Column(String, primary_key=True, default=generate_uuid)
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    target_model = Column(String, nullable=False, default="runway")
    prompt_json = Column(JSON, nullable=False)  # Stores the full compiled prompt payload
    positive_prompt = Column(Text, nullable=True)
    negative_prompt = Column(JSON, nullable=True)  # Stores negative prompt string or array
    motivator = Column(String, nullable=True)
    seed = Column(Integer, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # backref, not back_populates: this side owns the relationship so that
    # database.py needs no reference to PromptVersion. A forward reference from
    # there forced database.py to import this package, which pulled the router
    # and its FastAPI/httpx dependencies into every process that touches the
    # database — including Alembic, where it broke migrations outright.
    business_profile = relationship(
        'BusinessProfile',
        backref=backref('prompt_versions', cascade='all, delete-orphan'),
    )
    validations = relationship('PromptValidationLog', back_populates='prompt_version', cascade='all, delete-orphan')

    __table_args__ = (UniqueConstraint('businessProfileId', 'version', name='uniq_prompt_version_per_workspace'),)


class PromptValidationLog(Base):
    __tablename__ = "PromptValidationLog"

    id = Column(String, primary_key=True, default=generate_uuid)
    promptVersionId = Column(String, ForeignKey('PromptVersion.id', ondelete='CASCADE'), nullable=False)
    is_valid = Column(Boolean, default=False, nullable=False)
    errors = Column(JSON, default=list, nullable=False)  # List of validation error strings
    detailed_checks = Column(JSON, default=dict, nullable=False)  # Detailed per-check breakdown
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    prompt_version = relationship('PromptVersion', back_populates='validations')

    __table_args__ = (UniqueConstraint('promptVersionId', name='uniq_validation_per_prompt'),)


class ModelRoutingRule(Base):
    __tablename__ = "ModelRoutingRule"

    id = Column(String, primary_key=True, default=generate_uuid)
    model_name = Column(String, nullable=False, unique=True)  # e.g. "runway", "veo", "kling", "sora", "pika"
    prompt_template = Column(JSON, nullable=False)
    supports_negative_prompt = Column(Boolean, default=True, nullable=False)
    max_word_budget = Column(Integer, default=85, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint('model_name', name='uniq_model_name'),)


class GoldenDatasetSample(Base):
    __tablename__ = "GoldenDatasetSample"

    id = Column(String, primary_key=True, default=generate_uuid)
    dataset_name = Column(String, nullable=False, default="default_golden_dataset")
    intent = Column(String, nullable=False)
    target_model = Column(String, nullable=False)
    customer_motivator = Column(String, nullable=True)
    expected_safety_pass = Column(Boolean, default=True, nullable=False)
    expected_heuristic_pass = Column(Boolean, default=True, nullable=False)
    payload_sample = Column(JSON, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class CaptionVersion(Base):
    """Stores generated captions with their motivator, brand anchor, and validation result.

    Analogous to PromptVersion for video prompts. Each row is an immutable snapshot
    of one LLM-generated (or template-fallback) caption tied to a BusinessProfile.
    """
    __tablename__ = "CaptionVersion"

    id = Column(String, primary_key=True, default=generate_uuid)
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    caption_text = Column(Text, nullable=False)
    customer_motivator = Column(String, nullable=True)
    brand_language_anchor = Column(Text, nullable=True)
    product_feature = Column(String, nullable=True)
    is_valid = Column(Boolean, default=False, nullable=False)
    validation_errors = Column(JSON, default=list, nullable=False)
    detailed_checks = Column(JSON, default=dict, nullable=False)
    generation_method = Column(String, default="template", nullable=False)  # "llm" or "template"
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    business_profile = relationship('BusinessProfile', backref='caption_versions')

    __table_args__ = (UniqueConstraint('businessProfileId', 'version', name='uniq_caption_version_per_workspace'),)

