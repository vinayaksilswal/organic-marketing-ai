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
    sender: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Send a single email via Resend with exponential backoff retries.

    `sender` carries a workspace's own credentials when it has connected them,
    so a customer's mail leaves from their domain rather than the platform's —
    which is what makes it land in inboxes rather than spam.
    """
    if sender and sender.get("apiKey"):
        if not resend:
            return {"success": False, "error": "Resend library not installed"}
        resend.api_key = sender["apiKey"]
    elif not _init_resend():
        return {"success": False, "error": "Resend API key not configured"}

    from_address = settings.resend_from_email
    if sender and sender.get("fromEmail"):
        name = sender.get("fromName")
        from_address = f"{name} <{sender['fromEmail']}>" if name else sender["fromEmail"]

    params = {
        "from": from_address,
        "to": [to_email],
        "subject": subject,
        "html": body_html,
    }
    if body_text:
        params["text"] = body_text
    if sender and sender.get("replyTo"):
        params["reply_to"] = sender["replyTo"]

    response = resend.Emails.send(params)
    logger.info(f"Resend email sent to {to_email}: ID {response.get('id')}")
    return {"success": True, "id": response.get("id")}


async def send_single_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str = "",
    sender: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Async wrapper for sending a single email."""
    try:
        return await asyncio.to_thread(
            _send_single_resend_email, to_email, subject, body_html, body_text, sender
        )
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return {"success": False, "error": str(e)}


async def _workspace_sender(workspace_id: Optional[str]) -> Optional[dict[str, Any]]:
    """This workspace's own sending credentials, decrypted, if it has any."""
    if not workspace_id:
        return None
    try:
        from database import EmailConfig
        from services.crypto_service import decrypt_token

        async with AsyncSessionLocal() as session:
            cfg = (await session.execute(
                select(EmailConfig).where(EmailConfig.businessProfileId == workspace_id)
            )).scalars().first()
        if not cfg or not cfg.apiKey:
            return None
        return {
            "apiKey": decrypt_token(cfg.apiKey),
            "fromEmail": cfg.fromEmail,
            "fromName": cfg.fromName,
            "replyTo": cfg.replyTo,
        }
    except Exception as e:
        logger.warning(f"Could not load email credentials for workspace {workspace_id}: {e}")
        return None


async def send_email_blast(
    subject: str,
    body_html: str,
    body_text: str = "",
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Send a promotional email blast to a workspace's audience.

    workspace_id scopes the recipient list. Without it this selected EVERY
    Audience row in the database, so one tenant's campaign could reach another
    tenant's subscribers.
    """
    # A workspace's own credentials take precedence over the platform default.
    sender = await _workspace_sender(workspace_id)

    if not sender and not _init_resend():
        # Reporting success here marked campaigns SENT when nothing was sent,
        # and the recipient saw nothing. An unconfigured sender is a failure.
        logger.error("Email sending is not configured (no Resend API key)")
        return {
            "success": False,
            "sent_count": 0,
            "error": (
                "Email sending is not configured. Add a sending key in "
                "Email Suite → Connect email."
            ),
        }

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Audience).where(Audience.unsubscribed == False)
            if workspace_id:
                stmt = stmt.where(Audience.businessProfileId == workspace_id)
            elif user_id:
                stmt = stmt.where(Audience.userId == user_id)
            else:
                logger.error("Refusing to send a blast with no workspace or user scope")
                return {
                    "success": False,
                    "sent_count": 0,
                    "error": "Internal error: the recipient list was not scoped to a business.",
                }

            res = await session.execute(stmt)
            audiences = res.scalars().all()

            email_set: set[str] = set()
            for a in audiences:
                if a.email:
                    email_set.add(a.email.lower().strip())

            emails = list(email_set)

        if not emails:
            logger.info("No active audience members found for email blast")
            return {
                "success": False,
                "sent_count": 0,
                "error": "This business has no subscribers yet, so there was nobody to send to.",
            }

        logger.info(f"Starting email blast to {len(emails)} recipients...")
        sent_count = 0

        for i in range(0, len(emails), EMAIL_BATCH_SIZE):
            batch = emails[i : i + EMAIL_BATCH_SIZE]
            for recipient in batch:
                try:
                    res = await send_single_email(
                        recipient, subject, body_html, body_text, sender=sender
                    )
                    if res.get("success"):
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Failed email blast to {recipient}: {e}")

            if i + EMAIL_BATCH_SIZE < len(emails):
                await asyncio.sleep(BATCH_DELAY_SECONDS)

        if sent_count == 0:
            return {
                "success": False,
                "sent_count": 0,
                "error": f"All {len(emails)} sends were rejected by the email provider.",
            }
        return {
            "success": True,
            "sent_count": sent_count,
            "error": (
                None if sent_count == len(emails)
                else f"Delivered to {sent_count} of {len(emails)} recipients."
            ),
        }
    except Exception as e:
        logger.exception("Email blast failed")
        return {"success": False, "error": str(e), "sent_count": 0}
