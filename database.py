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
    text,
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
    # Stops the automation for this workspace without deleting anything.
    #
    # A customer needs a way to hold posting during a rebrand, an incident, or
    # a holiday, and the alternatives are all destructive: disconnecting the
    # social account loses the token, deleting the workspace loses the
    # catalog, and setting a 24-hour interval still posts. Non-null with a
    # default so an existing workspace is never accidentally paused by a
    # migration.
    automationPaused = Column(Boolean, default=False, nullable=False)
    # ~100 hashtags in size tiers, built once when the brand profile is built.
    # suggestedHashtags already existed and holds about ten, which is enough
    # for one caption and not enough to rotate -- the same ten on every post is
    # the clearest automation signal an account can send.
    hashtagSets = Column(JSON, nullable=True)
    # Products and angles this business has already sold with, taken from its ad
    # results. Two of these businesses have real revenue from paid and almost
    # none from organic, and the reason is visible in the data: paid knows which
    # product converts and which problem the buyer feels, and the organic
    # captions were written from a brand description that knows neither.
    # A list of {product, problem, audience, proof, offer, best_format}.
    provenOffers = Column(JSON, nullable=True)
    # WHEN a workspace may post, as opposed to how often. The interval alone
    # drifts through the whole clock -- a 4-hour cadence starting at 20:58
    # posts at 02:58 and 08:58 -- so a shop whose customers are asleep gets a
    # third of its output at three in the morning.
    #
    # All null means no restriction, which is what every existing workspace
    # has and must keep having. See services/posting_window.py.
    postingDays = Column(JSON, nullable=True)          # [0..6], Monday = 0
    postingStartHour = Column(Integer, nullable=True)  # 0-23, local
    postingEndHour = Column(Integer, nullable=True)    # 0-23, local
    postingTimezone = Column(String, nullable=True)    # IANA, e.g. Asia/Kolkata
    # Publishing Visibility & Draft Review Mode (PUBLIC | PRIVATE | DRAFT_REVIEW)
    publishingMode = Column(String, default="PUBLIC", nullable=True)
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
    # The deep marketing profile — pain point, transformation, objection,
    # decision driver, competitor visual world. Built once from the website and
    # the brand's own fields, then reused. It used to be re-synthesised on
    # every generation (a scrape, a vision call and an LLM call per prompt),
    # which was slow and non-deterministic: two runs for the same business
    # could disagree about what that business even sells.
    brandIntelligence = Column(JSON, nullable=True)
    brandIntelligenceAt = Column(DateTime(timezone=True), nullable=True)
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
    # NOTE: prompt_versions is NOT declared here. It is contributed by
    # prompt_engine/db_models.py via backref, so this module needs no knowledge
    # of a class it does not own. Declaring it here made database.py depend on
    # prompt_engine, which dragged the whole FastAPI router stack into the
    # Alembic migration process and broke the deploy.

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
    # The app-scoped Facebook user id of the person who connected. Meta's Data
    # Deletion Callback identifies the user by this and nothing else, so
    # without it a deletion request cannot be mapped back to an account.
    fbUserId = Column(String, nullable=True, index=True)
    igAccountId = Column(String, nullable=True)
    igAccountName = Column(String, nullable=True)
    twitterAccessToken = Column(Text, nullable=True)
    twitterAccessSecret = Column(Text, nullable=True)
    linkedinAccessToken = Column(Text, nullable=True)
    # Who the post is authored by: "urn:li:person:xxxx" for a personal
    # profile, "urn:li:organization:123" for a Company Page.
    #
    # Both exist because they cost different things to obtain. Posting to a
    # Company Page needs LinkedIn's Community Management API and app review;
    # posting to a personal profile needs w_member_social and nothing else. A
    # customer who wants to publish today gets the second, and the first when
    # the review clears.
    linkedinActorUrn = Column(String, nullable=True)
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


class MediaFolder(Base):
    """A folder of assets that publishes as ONE carousel post.

    The catalog was flat, so every asset was its own post and there was no way
    to say "these six images belong together". A folder is that statement: the
    files inside it go out as a single carousel, in order, under one caption.

    It is a real table rather than a name written on each asset so an empty
    folder can exist. The user makes the folder first and moves files into it
    afterwards, which is impossible if the folder is only implied by its
    members.

    Deleting a folder never deletes the assets inside it -- they simply become
    loose files again, each its own post. Losing a business's media to a
    mis-clicked folder delete would be unrecoverable.
    """

    __tablename__ = "MediaFolder"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    # A caption written for the carousel as a whole. Optional: left empty, the
    # normal caption writer runs against the folder's first asset.
    caption = Column(Text, nullable=True)
    # Excluded from automatic posting while false, without unpacking it.
    isActive = Column(Boolean, default=True, nullable=False)
    businessProfileId = Column(
        String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True
    )
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    medias = relationship('Media', back_populates='folder')


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
    # Whether the file carries a sound track. NULL means nobody has looked yet.
    #
    # This exists because Instagram's music picker is app-only: the Content
    # Publishing API has no field for attaching a licensed track, so a silent
    # clip published through the API goes out silent forever. Knowing which
    # clips those are lets the scheduler post the ones that already have sound
    # and leave the rest for the operator to post by hand, picking a track in
    # the app.
    hasAudio = Column(Boolean, nullable=True)
    # Generation state for assets produced asynchronously.
    # NULL = nothing to generate (a plain upload). PENDING/READY/FAILED track a
    # background AI job, so the request can return immediately instead of
    # holding an HTTP connection open for minutes and being killed by the
    # server's timeout — which reaches the browser as a bogus CORS error.
    # The two stills the clip is generated between. Written as prompts, not
    # images: the frames are produced by an image model outside this system,
    # and holding the prompts means a frame can be regenerated or re-styled
    # without re-running the whole pipeline.
    #
    # {firstFramePrompt, lastFramePrompt, brand, cta, destination,
    #  spokenClosingLine, timing} -- see services/keyframes.py.
    keyframes = Column(JSON, nullable=True)
    # The beat plan the prompt was written to, so the length a prompt was
    # built for travels with it. A 30s prompt rendered at 10s is not a shorter
    # ad, it is a truncated one.
    plan = Column(JSON, nullable=True)
    generationStatus = Column(String, nullable=True)
    generationError = Column(Text, nullable=True)
    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    businessProfileId = Column(String, ForeignKey('BusinessProfile.id', ondelete='CASCADE'), nullable=True)
    businessProfile = relationship('BusinessProfile', back_populates='medias')
    # NULL means a loose file, which posts on its own. Set means this asset is
    # one slide of its folder's carousel. SET NULL on delete so removing a
    # folder frees its files rather than destroying them.
    folderId = Column(
        String, ForeignKey('MediaFolder.id', ondelete='SET NULL'), nullable=True
    )
    # Slide order within the folder. A carousel whose slides arrive in creation
    # order is not the same post as one the user arranged deliberately.
    folderPosition = Column(Integer, default=0, nullable=False)
    folder = relationship('MediaFolder', back_populates='medias')


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


class SupportTicket(Base):
    """A problem a customer reported, and what was done about it.

    The reply lives on the ticket rather than in an inbox. Support answered by
    email is invisible to everyone except the two people in the thread: the
    customer cannot find it again, and nobody else can see whether an issue
    was ever resolved. Here the answer sits next to the question, and the
    person who raised it sees the status change without being told.
    """

    __tablename__ = "SupportTicket"

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False, index=True)
    businessProfileId = Column(String, ForeignKey("BusinessProfile.id", ondelete="SET NULL"), nullable=True)

    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    # question | bug | billing | feature
    category = Column(String, default="question", nullable=False)
    # open | in_progress | resolved
    status = Column(String, default="open", nullable=False, index=True)

    reply = Column(Text, nullable=True)
    repliedAt = Column(DateTime(timezone=True), nullable=True)

    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User")


class Review(Base):
    """What a customer says about the product, and whether it may be shown.

    isApproved defaults to False and there is no path that sets it from a
    customer request. A review collected in-product and published to the
    landing page without a human reading it first is an open text field on a
    marketing site, which is a decision nobody makes twice.
    """

    __tablename__ = "Review"
    __table_args__ = (UniqueConstraint("userId", name="uniq_review_per_user"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    userId = Column(String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False, index=True)

    rating = Column(Integer, nullable=False)          # 1-5
    body = Column(Text, nullable=True)
    # Shown alongside the quote. Captured at submission so a later rename of
    # the workspace does not silently rewrite an attributed public quote.
    authorName = Column(String, nullable=True)
    authorBusiness = Column(String, nullable=True)

    isApproved = Column(Boolean, default=False, nullable=False, index=True)

    createdAt = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updatedAt = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

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

                # Defensive column migrations for existing databases
                columns_to_add = [
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "publishingMode" VARCHAR DEFAULT \'PUBLIC\'',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingDays" JSON',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingStartHour" INTEGER',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingEndHour" INTEGER',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingTimezone" VARCHAR',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "automationPaused" BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "hashtagSets" JSON',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "provenOffers" JSON',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandColors" JSON DEFAULT \'[]\'',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandFonts" JSON DEFAULT \'[]\'',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "industry" VARCHAR',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "targetAudience" TEXT',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "toneOfVoice" VARCHAR',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "contentPillars" JSON DEFAULT \'[]\'',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "suggestedHashtags" JSON DEFAULT \'[]\'',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "primaryOffer" TEXT',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandIntelligence" JSON',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandIntelligenceAt" TIMESTAMP WITH TIME ZONE',
                    'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandAnalysisComplete" BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "paypalOrderId" VARCHAR',
                    'ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "isSuperAdmin" BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "fbPageCategory" VARCHAR',
                    'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "fbUserId" VARCHAR',
                    'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "twitterAccessToken" TEXT',
                    'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "twitterAccessSecret" TEXT',
                    'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "linkedinAccessToken" TEXT',
                    # Who LinkedIn posts are authored as. The model declares
                    # this column, so if the bootstrap runs without Alembic
                    # every SELECT on the table fails, not just LinkedIn.
                    'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "linkedinActorUrn" VARCHAR',
                    'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR',
                    'ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "errorLog" TEXT',
                    'ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "twitterPostId" VARCHAR',
                    'ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "linkedinPostId" VARCHAR',
                    'ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "mediaUrls" JSON DEFAULT \'[]\'',
                    'ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "postedAt" TIMESTAMP WITH TIME ZONE',
                    'ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "keyframes" JSON',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "plan" JSON',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "generationStatus" VARCHAR',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "generationError" TEXT',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "caption" TEXT',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "isActive" BOOLEAN DEFAULT TRUE',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "hasAudio" BOOLEAN',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "folderId" VARCHAR',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "folderOrder" INTEGER',
                    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR',
                ]
                for stmt in columns_to_add:
                    try:
                        await conn.execute(text(stmt))
                    except Exception as col_err:
                        logger.debug(f"Column migration notice ({stmt}): {col_err}")

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


# =============================================================================
# A note on prompt_engine
# =============================================================================
# This module deliberately does NOT import prompt_engine.
#
# It previously did, because BusinessProfile declared
# relationship('PromptVersion', ...) and SQLAlchemy resolves that name at
# mapper-configuration time. That forward reference made the core data layer
# depend on an application package, and importing any prompt_engine submodule
# executed its __init__, which imported the FastAPI router and with it
# routers.*, services.*, fastapi and httpx.
#
# The consequence was a failed deploy: Alembic's env.py imports `database`, so
# `alembic upgrade head` dragged the entire web stack into the migration
# runner and died with SQLAlchemy MissingGreenlet — sync migration code
# attempting async IO. Render kept serving the previous build.
#
# PromptVersion now contributes the relationship from its own side via
# backref, so this module needs no knowledge of it and migrations import
# nothing but the ORM.
