"""
=============================================================================
Organic Marketing AI — SQLAlchemy 2.0 Async Database Layer
=============================================================================
Pure Python PostgreSQL database layer replacing Prisma.
Uses SQLAlchemy 2.0 + asyncpg. Zero external Rust/Node binary dependencies.
=============================================================================
"""

from __future__ import annotations

import asyncio
import ssl
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

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
    isSuperAdmin = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    businessProfiles = relationship("BusinessProfile", back_populates="user", cascade="all, delete-orphan")
    videoApiConfigs = relationship("VideoApiConfig", back_populates="user", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    socialConnection = relationship("SocialConnection", back_populates="user", uselist=False, cascade="all, delete-orphan")
    audiences = relationship("Audience", back_populates="user", cascade="all, delete-orphan")
    campaigns = relationship("SocialCampaign", back_populates="user", cascade="all, delete-orphan")
    marketingStates = relationship("MarketingState", back_populates="user", cascade="all, delete-orphan")


class BusinessProfile(Base):
    __tablename__ = "BusinessProfile"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, default="My Business", nullable=False)
    websiteUrl = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    businessModel = Column(String, nullable=True)
    niche = Column(String, nullable=True)  # Predefined niche from NICHE_OPTIONS
    postIntervalHours = Column(Integer, default=2, nullable=False)
    creativeGenerationIntervalHours = Column(Integer, default=2, nullable=False)
    autoGenerateCreatives = Column(Boolean, default=True, nullable=False)
    # AI Brand Context Fields
    brandColors = Column(JSON, default=list, nullable=False)
    brandFonts = Column(JSON, default=list, nullable=False)
    industry = Column(String, nullable=True)
    targetAudience = Column(Text, nullable=True)
    toneOfVoice = Column(String, nullable=True)
    contentPillars = Column(JSON, default=list, nullable=False)
    suggestedHashtags = Column(JSON, default=list, nullable=False)
    brandAnalysisComplete = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="businessProfiles")
    products = relationship('Product', back_populates='businessProfile', cascade='all, delete-orphan')
    videoapiconfigs = relationship('VideoApiConfig', back_populates='businessProfile', cascade='all, delete-orphan')
    audiences = relationship('Audience', back_populates='businessProfile', cascade='all, delete-orphan')
    marketingstates = relationship('MarketingState', back_populates='businessProfile', cascade='all, delete-orphan')
    socialcampaigns = relationship('SocialCampaign', back_populates='businessProfile', cascade='all, delete-orphan')
    socialposts = relationship('SocialPost', back_populates='businessProfile', cascade='all, delete-orphan')
    emailcampaigns = relationship('EmailCampaign', back_populates='businessProfile', cascade='all, delete-orphan')
    medias = relationship('Media', back_populates='businessProfile', cascade='all, delete-orphan')
    marketinglogs = relationship('MarketingLog', back_populates='businessProfile', cascade='all, delete-orphan')
    socialconnections = relationship('SocialConnection', back_populates='businessProfile', cascade='all, delete-orphan')

class VideoApiConfig(Base):
    __tablename__ = "VideoApiConfig"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String, default="json2video", nullable=False)
    apiKey = Column(String, nullable=False)
    endpoint = Column(String, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="videoApiConfigs")
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='videoapiconfigs')


class Product(Base):
    __tablename__ = "Product"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    url = Column(String, nullable=True)
    imageUrl = Column(String, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="products")
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='products')


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
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='socialconnections')


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
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='audiences')


class MarketingState(Base):
    __tablename__ = "MarketingState"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    lastSocialIdx = Column(Integer, default=0, nullable=False)
    lastEmailIdx = Column(Integer, default=0, nullable=False)
    autoApprove = Column(Boolean, default=False, nullable=False)
    postIntervalHours = Column(Integer, default=2, nullable=False)
    creativeGenerationIntervalHours = Column(Integer, default=2, nullable=False)
    autoGenerateCreatives = Column(Boolean, default=True, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="marketingStates")
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='marketingstates')


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
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='socialcampaigns')


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
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='socialposts')


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
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='emailcampaigns')


class Media(Base):
    __tablename__ = "Media"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    mimeType = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    data = Column(LargeBinary, nullable=True)
    tags = Column(JSON, default=list, nullable=False)
    aiGenerated = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='medias')


class MarketingLog(Base):
    __tablename__ = "MarketingLog"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, nullable=True)
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    status = Column(String, default="SUCCESS", nullable=False)
    socialSuccess = Column(Boolean, default=False, nullable=False)
    emailSuccess = Column(Boolean, default=False, nullable=False)
    emailCount = Column(Integer, default=0, nullable=False)
    errorLog = Column(Text, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    businessProfile = relationship('BusinessProfile', back_populates='marketinglogs')


# =============================================================================
# Database Connection Manager
# =============================================================================
def get_async_database_url(url: str) -> tuple[str, dict]:
    """Format connection string for SQLAlchemy asyncpg driver."""
    clean_url = url
    if clean_url.startswith("postgresql://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql+asyncpg://", 1)

    connect_args = {"timeout": 10.0}

    # Handle SSL mode if requested in URL
    if "sslmode=require" in clean_url or "ssl=true" in clean_url.lower():
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx
        
    # asyncpg does not accept most psycopg2 query params (like sslmode, channel_binding)
    # so we strip the entire query string after parsing what we need.
    clean_url = clean_url.split("?")[0]

    return clean_url, connect_args


engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


def AsyncSessionLocal() -> AsyncSession:
    if not _sessionmaker:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _sessionmaker()


async def init_db() -> AsyncEngine:
    """Initialize SQLAlchemy async engine and create tables."""
    global engine, _sessionmaker

    db_url, connect_args = get_async_database_url(settings.database_url)
    logger.info("Initializing SQLAlchemy AsyncEngine with PostgreSQL...")

    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args=connect_args,
    )

    _sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Auto-create tables with 30-second timeout safeguard (Neon cold start can be slow)
    try:
        async with asyncio.timeout(30.0):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLAlchemy ORM tables initialized successfully")
    except Exception as e:
        logger.error(f"Table initialization failed or timed out: {e}")

    return engine


async def close_db():
    """Close SQLAlchemy async engine connection pool."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("SQLAlchemy engine disposed")


async def get_db_session() -> AsyncSession:
    """Provide an async database session context."""
    if not _sessionmaker:
        await init_db()
    async with AsyncSessionLocal() as session:
        yield session


from contextlib import asynccontextmanager
from sqlalchemy import text

@asynccontextmanager
async def get_tenant_session(workspace_id: str) -> AsyncSession:
    """Provide an async database session context configured with RLS for the given workspace."""
    if not _sessionmaker:
        await init_db()
    async with AsyncSessionLocal() as session:
        if workspace_id:
            # Set the local variable for PostgreSQL RLS policies to use
            await session.execute(text("SET LOCAL app.current_workspace = :ws"), {"ws": workspace_id})
        yield session
