"""
=============================================================================
Organic Marketing AI — Resend Email Client
=============================================================================
Handles transactional and marketing email delivery via the Resend SDK
using SQLAlchemy 2.0 Async Session.
=============================================================================
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from database import AsyncSessionLocal, Audience

try:
    import resend
except ImportError:
    resend = None
    logger.warning("Resend SDK not installed. Install with: pip install resend")

EMAIL_BATCH_SIZE = 50
BATCH_DELAY_SECONDS = 2


def _init_resend() -> bool:
    """Initialize the Resend API key."""
    if not resend:
        return False
    if not settings.resend_api_key:
        return False
    resend.api_key = settings.resend_api_key
    return True


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _send_single_resend_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str = "",
) -> dict[str, Any]:
    """Send a single email via Resend with exponential backoff retries."""
    if not _init_resend():
        return {"success": False, "error": "Resend API key not configured"}

    params = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": subject,
        "html": body_html,
    }
    if body_text:
        params["text"] = body_text

    response = resend.Emails.send(params)
    logger.info(f"Resend email sent to {to_email}: ID {response.get('id')}")
    return {"success": True, "id": response.get("id")}


async def send_single_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str = "",
) -> dict[str, Any]:
    """Async wrapper for sending a single email."""
    try:
        return await asyncio.to_thread(
            _send_single_resend_email, to_email, subject, body_html, body_text
        )
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return {"success": False, "error": str(e)}


async def send_email_blast(
    subject: str,
    body_html: str,
    body_text: str = "",
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Send a promotional email blast to all audience members using SQLAlchemy session."""
    if not _init_resend():
        logger.warning(f"Resend not configured. Simulating email blast: {subject}")
        return {"success": True, "sent_count": 0, "simulated": True}

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Audience).where(Audience.unsubscribed == False)
            if user_id:
                stmt = stmt.where(Audience.userId == user_id)

            res = await session.execute(stmt)
            audiences = res.scalars().all()

            email_set: set[str] = set()
            for a in audiences:
                if a.email:
                    email_set.add(a.email.lower().strip())

            emails = list(email_set)

        if not emails:
            logger.info("No active audience members found for email blast")
            return {"success": True, "sent_count": 0}

        logger.info(f"Starting email blast to {len(emails)} recipients...")
        sent_count = 0

        for i in range(0, len(emails), EMAIL_BATCH_SIZE):
            batch = emails[i : i + EMAIL_BATCH_SIZE]
            for recipient in batch:
                try:
                    res = await send_single_email(recipient, subject, body_html, body_text)
                    if res.get("success"):
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Failed email blast to {recipient}: {e}")

            if i + EMAIL_BATCH_SIZE < len(emails):
                await asyncio.sleep(BATCH_DELAY_SECONDS)

        return {"success": True, "sent_count": sent_count}
    except Exception as e:
        logger.error(f"Email blast exception: {e}")
        return {"success": False, "error": str(e), "sent_count": 0}
