"""
=============================================================================
Organic Marketing AI — SQLAlchemy 2.0 Async Database Layer
=============================================================================
Pure Python PostgreSQL database layer replacing Prisma.
Uses SQLAlchemy 2.0 + asyncpg. Zero external Rust/Node binary dependencies.
=============================================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    JSON,
    UniqueConstraint,
    select,
    func,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from config import settings
from loguru import logger


# =============================================================================
# Declarative Base
# =============================================================================
class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# SQLAlchemy ORM Models (Exact mapping matching original PostgreSQL schema)
# =============================================================================
class User(Base):
    __tablename__ = "User"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    subscriptionStatus = Column(String, default="INACTIVE", nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    businessProfile = relationship("BusinessProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    socialConnection = relationship("SocialConnection", back_populates="user", uselist=False, cascade="all, delete-orphan")
    audiences = relationship("Audience", back_populates="user", cascade="all, delete-orphan")
    campaigns = relationship("SocialCampaign", back_populates="user", cascade="all, delete-orphan")
    marketingStates = relationship("MarketingState", back_populates="user", cascade="all, delete-orphan")


class BusinessProfile(Base):
    __tablename__ = "BusinessProfile"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), unique=True, nullable=False)
    websiteUrl = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    businessModel = Column(String, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="businessProfile")


class SocialConnection(Base):
    __tablename__ = "SocialConnection"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), unique=True, nullable=False)
    fbAccessToken = Column(Text, nullable=True)
    fbPageId = Column(String, nullable=True)
    fbPageName = Column(String, nullable=True)
    igAccountId = Column(String, nullable=True)
    igAccountName = Column(String, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="socialConnection")


class Audience(Base):
    __tablename__ = "Audience"
    __table_args__ = (UniqueConstraint("userId", "email", name="uniq_user_audience_email"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    source = Column(String, default="checkout", nullable=False)
    unsubscribed = Column(Boolean, default=False, nullable=False)
    lastEngaged = Column(DateTime(timezone=True), nullable=True)
    tags = Column(JSON, default=list, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="audiences")


class MarketingState(Base):
    __tablename__ = "MarketingState"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    lastSocialIdx = Column(Integer, default=0, nullable=False)
    lastEmailIdx = Column(Integer, default=0, nullable=False)
    autoApprove = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="marketingStates")


class SocialCampaign(Base):
    __tablename__ = "SocialCampaign"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    baseCaption = Column(Text, nullable=False)
    mediaUrl = Column(Text, nullable=False)
    mediaType = Column(String, default="image", nullable=False)
    isActive = Column(Boolean, default=True, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="campaigns")
    posts = relationship("SocialPost", back_populates="campaign", cascade="all, delete-orphan")
    emails = relationship("EmailCampaign", back_populates="campaign", cascade="all, delete-orphan")


class SocialPost(Base):
    __tablename__ = "SocialPost"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, nullable=True)
    campaignId = Column(String, ForeignKey("SocialCampaign.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String, nullable=False)
    type = Column(String, default="AUTO", nullable=False)
    status = Column(String, default="DRAFT", nullable=False)
    caption = Column(Text, nullable=True)
    mediaUrls = Column(JSON, default=list, nullable=False)
    scheduledAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    postedAt = Column(DateTime(timezone=True), nullable=True)
    fbPostId = Column(String, nullable=True)
    igPostId = Column(String, nullable=True)
    twitterPostId = Column(String, nullable=True)
    linkedinPostId = Column(String, nullable=True)
    errorLog = Column(Text, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    campaign = relationship("SocialCampaign", back_populates="posts")


class EmailCampaign(Base):
    __tablename__ = "EmailCampaign"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, nullable=True)
    campaignId = Column(String, ForeignKey("SocialCampaign.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="DRAFT", nullable=False)
    subject = Column(String, nullable=True)
    bodyText = Column(Text, nullable=True)
    bodyHtml = Column(Text, nullable=True)
    scheduledAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    sentAt = Column(DateTime(timezone=True), nullable=True)
    recipientCount = Column(Integer, default=0, nullable=False)
    openRate = Column(Float, default=0.0, nullable=False)
    clickRate = Column(Float, default=0.0, nullable=False)
    errorLog = Column(Text, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    campaign = relationship("SocialCampaign", back_populates="emails")


class Media(Base):
    __tablename__ = "Media"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    mimeType = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    data = Column(LargeBinary, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# =============================================================================
# Database Connection Manager
# =============================================================================
def get_async_database_url(url: str) -> str:
    """Format connection string for SQLAlchemy asyncpg driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db() -> AsyncEngine:
    """Initialize SQLAlchemy async engine and create tables."""
    global engine, AsyncSessionLocal

    db_url = get_async_database_url(settings.database_url)
    logger.info(f"Initializing SQLAlchemy AsyncEngine with PostgreSQL...")

    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Auto-create all tables in PostgreSQL
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("SQLAlchemy ORM tables initialized successfully")
    return engine


async def close_db():
    """Close SQLAlchemy async engine connection pool."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("SQLAlchemy engine disposed")


async def get_db_session() -> AsyncSession:
    """Provide an async database session context."""
    if not AsyncSessionLocal:
        await init_db()
    async with AsyncSessionLocal() as session:
        yield session
