"""Reconcile every model column against the database

Revision ID: 006_reconcile_columns
Revises: 005_paypal_order_id
Create Date: 2026-07-28

The schema was created by SQLAlchemy create_all() and then drifted: create_all
adds missing *tables* but never adds missing *columns* to a table that already
exists. Columns added to the models over time were therefore never applied to
production, and any query touching one failed outright — e.g.

    UndefinedColumnError: column MarketingState.lastProductIdx does not exist

which took down /marketing/settings, /marketing/posts, /marketing/run-automation
and /social/scheduler-status.

This replays every column in every model with ADD COLUMN IF NOT EXISTS, so any
that is already present is skipped and any that drifted away is restored. All
columns are added nullable with the model default where one is expressible, so
this is safe against tables that already hold rows.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "006_reconcile_columns"
down_revision: Union[str, None] = "005_paypal_order_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Generated from database.py models. ADD COLUMN IF NOT EXISTS requires PG 9.6+.
STATEMENTS = """
        ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "email" VARCHAR;
        ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "password" VARCHAR;
        ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "subscriptionStatus" VARCHAR DEFAULT 'INACTIVE';
        ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "paypalOrderId" VARCHAR;
        ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "isSuperAdmin" BOOLEAN DEFAULT FALSE;
        ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "name" VARCHAR DEFAULT 'My Business';
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "websiteUrl" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "description" TEXT;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "businessModel" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "logoUrl" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "niche" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "productCatalogUrl" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "influencerReferenceUrl" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postIntervalHours" INTEGER DEFAULT 2;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "creativeGenerationIntervalHours" INTEGER DEFAULT 2;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "autoGenerateCreatives" BOOLEAN DEFAULT TRUE;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandColors" JSON;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandFonts" JSON;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "industry" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "targetAudience" TEXT;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "toneOfVoice" VARCHAR;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "contentPillars" JSON;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "suggestedHashtags" JSON;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "brandAnalysisComplete" BOOLEAN DEFAULT FALSE;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "VideoApiConfig" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "VideoApiConfig" ADD COLUMN IF NOT EXISTS "provider" VARCHAR DEFAULT 'json2video';
        ALTER TABLE "VideoApiConfig" ADD COLUMN IF NOT EXISTS "apiKey" VARCHAR;
        ALTER TABLE "VideoApiConfig" ADD COLUMN IF NOT EXISTS "endpoint" VARCHAR;
        ALTER TABLE "VideoApiConfig" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "VideoApiConfig" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "VideoApiConfig" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "title" VARCHAR;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "description" TEXT;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "price" FLOAT;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "url" VARCHAR;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "imageUrl" VARCHAR;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "videoUrl" VARCHAR;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "Product" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "fbAccessToken" TEXT;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "fbPageId" VARCHAR;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "fbPageName" VARCHAR;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "igAccountId" VARCHAR;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "igAccountName" VARCHAR;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "twitterAccessToken" TEXT;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "twitterAccessSecret" TEXT;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "linkedinAccessToken" TEXT;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "email" VARCHAR;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "name" VARCHAR;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "phone" VARCHAR;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "source" VARCHAR DEFAULT 'checkout';
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "unsubscribed" BOOLEAN DEFAULT FALSE;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "lastEngaged" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "tags" JSON;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "Audience" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "lastSocialIdx" INTEGER DEFAULT 0;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "lastEmailIdx" INTEGER DEFAULT 0;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "lastProductIdx" INTEGER DEFAULT 0;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "autoApprove" BOOLEAN DEFAULT FALSE;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "postIntervalHours" INTEGER DEFAULT 2;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "creativeGenerationIntervalHours" INTEGER DEFAULT 2;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "autoGenerateCreatives" BOOLEAN DEFAULT TRUE;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "MarketingState" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "baseCaption" TEXT;
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "mediaUrl" TEXT;
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "mediaType" VARCHAR DEFAULT 'image';
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "isActive" BOOLEAN DEFAULT TRUE;
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialCampaign" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "campaignId" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "platform" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "type" VARCHAR DEFAULT 'AUTO';
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "status" VARCHAR DEFAULT 'DRAFT';
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "caption" TEXT;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "mediaUrls" JSON;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "scheduledAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "postedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "fbPostId" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "igPostId" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "twitterPostId" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "linkedinPostId" VARCHAR;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "errorLog" TEXT;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "SocialPost" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "campaignId" VARCHAR;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "status" VARCHAR DEFAULT 'DRAFT';
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "subject" VARCHAR;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "bodyText" TEXT;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "bodyHtml" TEXT;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "scheduledAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "sentAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "recipientCount" INTEGER DEFAULT 0;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "openRate" FLOAT DEFAULT 0.0;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "clickRate" FLOAT DEFAULT 0.0;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "errorLog" TEXT;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "updatedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "EmailCampaign" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "filename" VARCHAR;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "mimeType" VARCHAR;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "url" TEXT;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "data" BYTEA;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "tags" JSON;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "aiGenerated" BOOLEAN DEFAULT FALSE;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "prompt" TEXT;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "promptType" VARCHAR;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "status" VARCHAR DEFAULT 'SUCCESS';
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "socialSuccess" BOOLEAN DEFAULT FALSE;
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "emailSuccess" BOOLEAN DEFAULT FALSE;
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "emailCount" INTEGER DEFAULT 0;
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "errorLog" TEXT;
        ALTER TABLE "MarketingLog" ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "TeamMember" ADD COLUMN IF NOT EXISTS "businessProfileId" VARCHAR;
        ALTER TABLE "TeamMember" ADD COLUMN IF NOT EXISTS "userId" VARCHAR;
        ALTER TABLE "TeamMember" ADD COLUMN IF NOT EXISTS "email" VARCHAR;
        ALTER TABLE "TeamMember" ADD COLUMN IF NOT EXISTS "role" VARCHAR DEFAULT 'editor';
        ALTER TABLE "TeamMember" ADD COLUMN IF NOT EXISTS "status" VARCHAR DEFAULT 'pending';
        ALTER TABLE "TeamMember" ADD COLUMN IF NOT EXISTS "invitedAt" TIMESTAMP WITH TIME ZONE;
        ALTER TABLE "TeamMember" ADD COLUMN IF NOT EXISTS "acceptedAt" TIMESTAMP WITH TIME ZONE;
"""


def upgrade() -> None:
    for statement in (s.strip() for s in STATEMENTS.split(";")):
        if statement:
            op.execute(statement)


def downgrade() -> None:
    # Intentionally not reversible: these columns are part of the current model
    # set, and dropping them would break the running application.
    pass
