"""
=============================================================================
Organic Marketing AI — Seed Service
=============================================================================
Handles idempotent seeding of the database on application startup:
  1. System user + workspace for self-promotion
  2. Superadmin account (vinayaksilswal@gmail.com)
  3. Predefined niche/industry options

Called once during application lifespan startup.
=============================================================================
"""

from __future__ import annotations

import asyncio
import bcrypt
from loguru import logger
from sqlalchemy import select

from database import AsyncSessionLocal, User, BusinessProfile, MarketingState
from config import settings


# =============================================================================
# Predefined Niche / Industry Options
# =============================================================================
NICHE_OPTIONS = [
    {"value": "saas", "label": "SaaS / Software", "icon": "💻"},
    {"value": "ecommerce", "label": "E-Commerce / Retail", "icon": "🛍️"},
    {"value": "local_services", "label": "Local Services", "icon": "🏠"},
    {"value": "healthcare", "label": "Healthcare / Wellness", "icon": "🏥"},
    {"value": "real_estate", "label": "Real Estate", "icon": "🏘️"},
    {"value": "restaurant", "label": "Restaurant / Food & Beverage", "icon": "🍽️"},
    {"value": "fitness", "label": "Fitness / Gym", "icon": "💪"},
    {"value": "education", "label": "Education / Coaching", "icon": "📚"},
    {"value": "agency", "label": "Marketing Agency", "icon": "📢"},
    {"value": "finance", "label": "Finance / Fintech", "icon": "💰"},
    {"value": "beauty", "label": "Beauty / Salon / Spa", "icon": "💅"},
    {"value": "legal", "label": "Legal / Law Firm", "icon": "⚖️"},
    {"value": "travel", "label": "Travel / Hospitality", "icon": "✈️"},
    {"value": "automotive", "label": "Automotive", "icon": "🚗"},
    {"value": "construction", "label": "Construction / Home Improvement", "icon": "🔨"},
    {"value": "consulting", "label": "Consulting / Professional Services", "icon": "📊"},
    {"value": "nonprofit", "label": "Nonprofit / NGO", "icon": "🤝"},
    {"value": "entertainment", "label": "Entertainment / Media", "icon": "🎬"},
    {"value": "other", "label": "Other", "icon": "🏢"},
]


async def seed_system_workspace() -> None:
    """
    Create or verify the SYSTEM user and workspace for platform self-promotion.
    This workspace markets the Organic Marketing AI platform itself.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Find or create SYSTEM user
            system_user = (
                await session.execute(
                    select(User).where(User.email == "system@organicai.pro")
                )
            ).scalar()

            if not system_user:
                system_user = User(
                    email="system@organicai.pro",
                    password="NOPASSWORD",
                    subscriptionStatus="ACTIVE",
                )
                session.add(system_user)
                await session.commit()
                await session.refresh(system_user)
                logger.info("✓ Created SYSTEM user for self-promotion")

            # Find or create SYSTEM workspace
            system_workspace = (
                await session.execute(
                    select(BusinessProfile).where(
                        BusinessProfile.userId == system_user.id
                    )
                )
            ).scalar()

            if not system_workspace:
                system_workspace = BusinessProfile(
                    userId=system_user.id,
                    name="Organic Marketing AI",
                    websiteUrl="https://organicai.pro",
                    description=(
                        "An enterprise-grade SaaS platform that uses AI to automate organic marketing. "
                        "It auto-generates brand-matched social media posts with AI images and publishes them "
                        "to Facebook, Instagram, X, and LinkedIn on a schedule. It helps businesses save time "
                        "and grow their audience without needing marketing skills."
                    ),
                    businessModel="SaaS",
                    niche="saas",
                    postIntervalHours=2,
                    brandAnalysisComplete=True,
                    toneOfVoice="Professional, authoritative, yet approachable and exciting.",
                    contentPillars=[
                        "AI Marketing Tips",
                        "SaaS Growth",
                        "Social Media Automation",
                        "ROI & Cost Savings",
                        "Platform Features",
                    ],
                    suggestedHashtags=[
                        "#AIMarketing",
                        "#SaaS",
                        "#SocialMediaAutomation",
                        "#GrowthHacking",
                        "#OrganicAI",
                    ],
                )
                session.add(system_workspace)
                await session.commit()
                logger.info("✓ Created SYSTEM workspace for self-promotion")

                # Trigger initial creative generation
                try:
                    from services.creative_service import auto_populate_workspace

                    asyncio.create_task(
                        auto_populate_workspace(system_user.id, system_workspace.id)
                    )
                    logger.info("✓ Triggered initial AI creative generation for self-promotion")
                except Exception as e:
                    logger.error(f"Failed to trigger self-promotion creatives: {e}")

    except Exception as e:
        logger.error(f"Failed to seed system workspace: {e}")


async def seed_superadmin() -> None:
    """
    Create or verify the superadmin account.
    The superadmin has access to all workspaces and the admin dashboard.
    """
    admin_email = settings.admin_email
    if not admin_email:
        logger.warning("No ADMIN_EMAIL configured — skipping superadmin seed")
        return

    try:
        async with AsyncSessionLocal() as session:
            existing = (
                await session.execute(
                    select(User).where(User.email == admin_email)
                )
            ).scalar()

            if existing:
                # Ensure superadmin status
                if existing.subscriptionStatus != "ACTIVE":
                    existing.subscriptionStatus = "ACTIVE"
                    await session.commit()
                    logger.info(f"✓ Upgraded {admin_email} to ACTIVE subscription")
                if not existing.isSuperAdmin:
                    existing.isSuperAdmin = True
                    await session.commit()
                    logger.info(f"✓ Granted superadmin role to {admin_email}")
                return

            # Create the superadmin account with a default password
            # User should change this on first login
            default_password = "OrganicAI@2024!"
            hashed = bcrypt.hashpw(
                default_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            admin_user = User(
                email=admin_email,
                password=hashed,
                subscriptionStatus="ACTIVE",
                isSuperAdmin=True,
            )
            session.add(admin_user)
            await session.commit()
            await session.refresh(admin_user)

            logger.info(f"✓ Created superadmin account: {admin_email}")
            logger.info(f"  Default password: {default_password}")
            logger.info(f"  ⚠️  CHANGE THIS PASSWORD IMMEDIATELY IN PRODUCTION")

    except Exception as e:
        logger.error(f"Failed to seed superadmin: {e}")


async def run_all_seeds() -> None:
    """Run all seed operations. Called during application startup."""
    logger.info("Running database seeds...")
    await seed_system_workspace()
    await seed_superadmin()
    logger.info("Database seeding complete")
