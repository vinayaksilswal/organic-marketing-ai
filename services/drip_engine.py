"""
=============================================================================
Organic Marketing AI — Behavioral Drip Engine
=============================================================================
Parses email_flows.json configurations and executes behavioral email drips
using SQLAlchemy 2.0 Async Session.
=============================================================================
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from loguru import logger
from sqlalchemy import select

from database import AsyncSessionLocal, User
from .email_service import send_email_blast

FLOWS_FILE = Path(__file__).parent.parent / "email_flows.json"

class DripEngine:
    def __init__(self):
        self.flows = self._load_flows()

    def _load_flows(self) -> dict:
        try:
            if not FLOWS_FILE.exists():
                logger.warning(f"[DRIP ENGINE] Flows file not found at {FLOWS_FILE}")
                return {}
            with open(FLOWS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("sequences", {})
        except Exception as e:
            logger.error(f"[DRIP ENGINE] Failed to load email flows: {e}")
            return {}

    def _build_html_template(self, subject: str, headline: str, body_html: str, cta_text: str, cta_link: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 0; background-color: #f4f7f6; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="padding: 40px 0;">
                <tr>
                    <td align="center">
                        <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                            <tr>
                                <td style="padding: 40px; text-align: center; background-color: #0f172a;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Organic<span style="color: #6366f1;">AI</span></h1>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px; color: #334155;">
                                    <h2 style="margin-top: 0; color: #0f172a; font-size: 22px;">{headline}</h2>
                                    <div style="font-size: 16px; line-height: 1.6; color: #475569;">
                                        {body_html}
                                    </div>
                                    {f'''
                                    <div style="margin-top: 30px; text-align: center;">
                                        <a href="{cta_link}" style="background-color: #6366f1; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                                            {cta_text}
                                        </a>
                                    </div>
                                    ''' if cta_text and cta_link else ''}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    async def run_sequence(self, sequence_id: str):
        sequence = self.flows.get(sequence_id)
        if not sequence:
            logger.warning(f"[DRIP ENGINE] Sequence '{sequence_id}' not found.")
            return

        trigger = sequence.get("trigger")
        logger.info(f"[DRIP ENGINE] Evaluating sequence: {sequence_id} (Trigger: {trigger})")

        target_users = []
        async with AsyncSessionLocal() as session:
            stmt = select(User)
            if trigger == "user_registered":
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                stmt = stmt.where(User.createdAt >= cutoff)
            res = await session.execute(stmt)
            target_users = res.scalars().all()

            for step in sequence.get("steps", []):
                delay_hours = step.get("delay_hours", 0)
                subject = step.get("subject", "")
                headline = step.get("headline", "")
                body_html = step.get("body", "")
                cta_text = step.get("cta_text", "")
                cta_link = step.get("cta_link", "")

                full_html = self._build_html_template(subject, headline, body_html, cta_text, cta_link)

                for u in target_users:
                    try:
                        await send_email_blast(subject, full_html, user_id=u.id)
                    except Exception as e:
                        logger.error(f"[DRIP ENGINE] Failed drip to user {u.email}: {e}")
