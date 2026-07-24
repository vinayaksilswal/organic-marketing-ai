"""
=============================================================================
Organic Marketing AI — Centralized Configuration (Pydantic Settings)
=============================================================================
All environment variables are loaded here via pydantic-settings and exposed
as a singleton `settings` instance. Every service imports from this module
instead of calling os.getenv() directly.

Environment variables are loaded from the .env file in the python_admin/
directory (or the root .env via env_file config).
=============================================================================
"""

from __future__ import annotations

import sys
import warnings
from pydantic import model_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All fields use snake_case; pydantic-settings auto-maps to UPPER_CASE env vars.
    """

    # =========================================================================
    # Core Application
    # =========================================================================
    environment: str = "development"
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://organic-marketing-ai.vercel.app",
        "https://organicai.pro",
        "https://www.organicai.pro"
    ]

    # =========================================================================
    # Database (PostgreSQL) & Redis (ARQ)
    # =========================================================================
    database_url: str = "postgresql://postgres:password@localhost:5432/quantcai"
    redis_url: str = "redis://localhost:6379/0"

    # =========================================================================
    # Security (Encryption & Authentication)
    # =========================================================================
    encryption_key: str | None = None  # Base64 encoded 32-byte key for AES-256
    admin_username: str = "admin"
    admin_password: str = "admin"
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"


    # =========================================================================
    # OpenRouter API (LLM — AI copy generation & chatbot)
    # =========================================================================
    openrouter_api_key: str | None = None

    # =========================================================================
    # Meta Graph API (Facebook + Instagram publishing)
    # =========================================================================
    fb_app_id: str | None = None
    fb_app_secret: str | None = None
    fb_page_access_token: str | None = None
    fb_page_id: str | None = None
    ig_business_account_id: str | None = None

    # =========================================================================
    # TikTok Content Posting API
    # =========================================================================
    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None

    # =========================================================================
    # Cloud Storage (Cloudinary)
    # =========================================================================
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None

    # =========================================================================
    # Json2Video API (Video Rendering)
    # =========================================================================
    json2video_api_key: str | None = None

    # =========================================================================
    # Resend API (Transactional & Marketing Email)
    # =========================================================================
    resend_api_key: str | None = None
    resend_from_email: str = "Organic Marketing AI <support@organicmarketing.ai>"

    # =========================================================================
    # Stripe (Monetization & Webhooks)
    # =========================================================================
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    # =========================================================================
    # YouTube API (Optional — for auto-posting Shorts)
    # =========================================================================
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None

    # =========================================================================
    # Admin Seeding
    # =========================================================================
    admin_email: str = "vinayaksilswal@gmail.com"

    # =========================================================================
    # Pydantic Settings Configuration
    # =========================================================================
    model_config = SettingsConfigDict(
        # Look for .env in the parent directory (project root) first,
        # then fall back to the python_admin/.env
        env_file=("../.env", ".env"),
        extra="ignore",  # Ignore unknown env vars (e.g., VITE_*)
    )

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if self.environment == "production":
            if not self.jwt_secret or self.jwt_secret == "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7":
                raise ValueError("CRITICAL: JWT_SECRET must be securely set in production environment variables.")
            if not self.encryption_key:
                raise ValueError("CRITICAL: ENCRYPTION_KEY must be securely set in production environment variables.")
            if self.database_url == "postgresql://postgres:password@localhost:5432/quantcai":
                raise ValueError("CRITICAL: DATABASE_URL must be set to a real production database URL.")
            if self.admin_username == "admin" or self.admin_password == "admin":
                raise ValueError("CRITICAL: ADMIN_USERNAME and ADMIN_PASSWORD must be changed in production.")
        elif not self.jwt_secret:
            self.jwt_secret = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
            warnings.warn("Using default JWT_SECRET for development. Do NOT use in production.")
        
        if not self.encryption_key:
            self.encryption_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            warnings.warn("Using default ENCRYPTION_KEY for development. Do NOT use in production.")
            
        return self


# =============================================================================
# Global Singleton Instance
# =============================================================================
try:
    settings = Settings()
except ValidationError as e:
    print("=" * 70, file=sys.stderr)
    print("CRITICAL CONFIGURATION ERROR: APPLICATION FAILED TO START", file=sys.stderr)
    print("The application cannot start because of the following validation errors:", file=sys.stderr)
    for err in e.errors():
        field_path = ".".join(str(loc) for loc in err.get("loc", []))
        message = err.get("msg", "")
        print(f" ❌ {field_path.upper()}: {message}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    sys.exit(1)
