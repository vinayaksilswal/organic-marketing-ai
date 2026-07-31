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
    # The PayPal order that paid for this subscription. Unique so a single
    # completed order can never activate more than one account.
    paypalOrderId = Column(String, unique=True, nullable=True)
    isSuperAdmin = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    businessProfiles = relationship("BusinessProfile", back_populates="user", cascade="all, delete-orphan")
    videoApiConfigs = relationship("VideoApiConfig", back_populates="user", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    socialConnections = relationship("SocialConnection", back_populates="user", cascade="all, delete-orphan")
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
    logoUrl = Column(String, nullable=True)
    niche = Column(String, nullable=True)
    productCatalogUrl = Column(String, nullable=True)
    influencerReferenceUrl = Column(String, nullable=True)
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
    # The single action every creative should drive toward, in the words the
    # business would use — "Start free — no credit card", "Book a demo",
    # "Shop the drop". Without it the AI invented a CTA per post, so offers
    # drifted and nothing was consistent enough to convert against.
    primaryOffer = Column(Text, nullable=True)
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
    prompt_versions = relationship('PromptVersion', back_populates='business_profile', cascade='all, delete-orphan')

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


class Subscription(Base):
    """A user's recurring PayPal subscription.

    Separate from User.subscriptionStatus, which only ever recorded a boolean
    "did someone pay once". Recurring billing needs the plan, the PayPal
    subscription id, and the period end — without the period end an expired
    or failed subscription looks identical to a healthy one.
    """

    __tablename__ = "Subscription"
    __table_args__ = (
        UniqueConstraint("paypalSubscriptionId", name="uniq_paypal_subscription_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False, index=True)
    planCode = Column(String, nullable=False, default="starter")
    paypalSubscriptionId = Column(String, nullable=True)
    paypalPlanId = Column(String, nullable=True)
    # APPROVAL_PENDING | ACTIVE | SUSPENDED | CANCELLED | EXPIRED
    status = Column(String, nullable=False, default="APPROVAL_PENDING")
    currentPeriodEnd = Column(DateTime(timezone=True), nullable=True)
    cancelAtPeriodEnd = Column(Boolean, default=False, nullable=False)
    lastPaymentAt = Column(DateTime(timezone=True), nullable=True)
    lastError = Column(Text, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class UsageCounter(Base):
    """Metered usage for one user, one metric, one billing month.

    Counting rows in the domain tables would be wrong: deleting a post must
    not refund the AI call that produced it, and a plan change must not
    retroactively rewrite history.
    """

    __tablename__ = "UsageCounter"
    __table_args__ = (
        UniqueConstraint("userId", "metric", "periodStart", name="uniq_usage_user_metric_period"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False, index=True)
    metric = Column(String, nullable=False)      # posts | prompts | emails | media
    periodStart = Column(String, nullable=False)  # "YYYY-MM", the billing month
    count = Column(Integer, default=0, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ProcessedWebhookEvent(Base):
    """Every PayPal event id we have already applied.

    PayPal retries deliveries, so without this a repeated
    PAYMENT.SALE.COMPLETED would extend a subscription twice.
    """

    __tablename__ = "ProcessedWebhookEvent"

    id = Column(String, primary_key=True)     # PayPal's own event id
    eventType = Column(String, nullable=True)
    processedAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class EmailConfig(Base):
    """Per-workspace email sending credentials.

    Sending was previously possible only through one global RESEND_API_KEY, so
    every customer's mail would leave from the platform's own domain — bad for
    deliverability and impossible for a business that wants its own sender.
    """

    __tablename__ = "EmailConfig"
    __table_args__ = (
        UniqueConstraint("businessProfileId", name="uniq_email_config_workspace"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String, default="resend", nullable=False)
    apiKey = Column(Text, nullable=False)          # Fernet-encrypted at rest
    fromEmail = Column(String, nullable=False)
    fromName = Column(String, nullable=True)
    replyTo = Column(String, nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    lastError = Column(Text, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    businessProfileId = Column(
        String, ForeignKey("BusinessProfile.id", ondelete="CASCADE"), nullable=True
    )


class Product(Base):
    __tablename__ = "Product"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    url = Column(String, nullable=True)
    imageUrl = Column(String, nullable=True)
    videoUrl = Column(String, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="products")
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='products')


class SocialConnection(Base):
    __tablename__ = "SocialConnection"
    __table_args__ = (UniqueConstraint("userId", "businessProfileId", name="uniq_user_workspace_social"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False)
    fbAccessToken = Column(Text, nullable=True)
    fbPageId = Column(String, nullable=True)
    fbPageName = Column(String, nullable=True)
    # The Page's own category from Meta ("Software Company", "Clothing Store",
    # "Restaurant"). Captured at connect time and fed to the writers, so an
    # account's niche comes from the platform itself rather than being guessed.
    # This is what keeps two businesses on one login from sounding alike.
    fbPageCategory = Column(String, nullable=True)
    igAccountId = Column(String, nullable=True)
    igAccountName = Column(String, nullable=True)
    twitterAccessToken = Column(Text, nullable=True)
    twitterAccessSecret = Column(Text, nullable=True)
    linkedinAccessToken = Column(Text, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="socialConnections")
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
    lastProductIdx = Column(Integer, default=0, nullable=False)
    autoApprove = Column(Boolean, default=False, nullable=False)
    postIntervalHours = Column(Integer, default=2, nullable=False)
    creativeGenerationIntervalHours = Column(Integer, default=2, nullable=False)
    autoGenerateCreatives = Column(Boolean, default=True, nullable=False)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="marketingStates")
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='marketingstates')

    # Exactly one automation state per workspace. Without this, duplicate rows
    # accumulated and every reader used .first() with no ordering — so the
    # auto-approve toggle could update one row while the publisher read
    # another, and posts went out with the dashboard showing "off".
    __table_args__ = (
        UniqueConstraint("businessProfileId", name="uniq_marketing_state_workspace"),
    )


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
    # Nullable: a post triggered directly by the scheduler or the manual
    # "Run Automation" button has no parent campaign. Requiring one made every
    # such run fail with NotNullViolationError on campaignId.
    campaignId = Column(String, ForeignKey("SocialCampaign.id", ondelete="CASCADE"), nullable=True)
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
    # Nullable for the same reason as SocialPost.campaignId: an email drafted
    # by the automation run has no parent social campaign, and requiring one
    # made every run fail on NotNullViolationError.
    campaignId = Column(String, ForeignKey("SocialCampaign.id", ondelete="CASCADE"), nullable=True)
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
    prompt = Column(Text, nullable=True)  # The AI prompt that produced this asset
    promptType = Column(String, nullable=True)  # 'image' | 'video'
    # What this asset actually shows, in words. This is the single strongest
    # signal the caption writer has — a filename tells it nothing. For AI
    # assets it is seeded from the generation prompt; for uploads the user
    # types it. Editable either way.
    caption = Column(Text, nullable=True)
    # Deactivated assets stay in the catalog but are never chosen for posting.
    isActive = Column(Boolean, default=True, nullable=False)
    # Generation state for assets produced asynchronously.
    # NULL = nothing to generate (a plain upload). PENDING/READY/FAILED track a
    # background AI job, so the request can return immediately instead of
    # holding an HTTP connection open for minutes and being killed by the
    # server's timeout — which reaches the browser as a bogus CORS error.
    generationStatus = Column(String, nullable=True)
    generationError = Column(Text, nullable=True)
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


class TeamMember(Base):
    __tablename__ = "TeamMember"
    __table_args__ = (UniqueConstraint("businessProfileId", "email", name="uniq_workspace_team_email"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    businessProfileId = Column(String, ForeignKey("BusinessProfile.id", ondelete="CASCADE"), nullable=False)
    userId = Column(String, ForeignKey("User.id", ondelete="SET NULL"), nullable=True)
    email = Column(String, nullable=False)
    role = Column(String, default="editor", nullable=False)
    status = Column(String, default="pending", nullable=False)
    invitedAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    acceptedAt = Column(DateTime(timezone=True), nullable=True)

    businessProfile = relationship("BusinessProfile")
    user = relationship("User")


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

def _is_postgres(session) -> bool:
    """True when the session talks to PostgreSQL.

    Defensive: set_config() is Postgres-only, and this must never be the thing
    that raises — a failure here would take down every tenant-scoped endpoint.
    """
    try:
        bind = session.get_bind() if hasattr(session, "get_bind") else session.bind
        return bool(bind) and bind.dialect.name == "postgresql"
    except Exception:
        return False


@asynccontextmanager
async def get_tenant_session(workspace_id: str) -> AsyncSession:
    """Provide an async database session context configured with RLS for the given workspace."""
    if not _sessionmaker:
        await init_db()
    async with AsyncSessionLocal() as session:
        if workspace_id and _is_postgres(session):
            # Set the workspace for the RLS policies in enable_rls.py to read.
            #
            # This MUST use set_config() rather than "SET LOCAL ... = :ws".
            # SET is a utility statement and cannot take bind parameters, so the
            # parameterised form compiled to "SET LOCAL ... = $1" and raised a
            # syntax error on every request through this helper — which is every
            # marketing endpoint. set_config(name, value, is_local=true) is an
            # ordinary function call, is parameterisable, and is scoped to the
            # transaction exactly like SET LOCAL.
            await session.execute(
                text("SELECT set_config('app.current_workspace', :ws, true)"),
                {"ws": workspace_id},
            )
        yield session
