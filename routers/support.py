"""Support tickets and customer reviews.

Two things a product needs before it can charge people and mean it: a place to
say something is broken, and a way for what other customers said to be visible
to the next one.

They live together because they are the same loop. Someone reports a problem,
it gets fixed, they are told it was fixed — and that is the moment they are
willing to say something good. A review request sent before that point is
asking for a favour; sent after it, it is asking for a fact.

MODERATION
Review.isApproved defaults to False and nothing a customer can call sets it.
The public endpoint filters on it. An in-product text field that reaches a
marketing page unread is an open text field on a marketing page.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, Review, SupportTicket, User
from routers.auth import verify_user

router = APIRouter(prefix="/api/v1/support", tags=["Support"])
public_router = APIRouter(prefix="/api/public", tags=["Public"])

CATEGORIES = {"question", "bug", "billing", "feature"}
STATUSES = {"open", "in_progress", "resolved"}


# =============================================================================
# Schemas
# =============================================================================
class TicketIn(BaseModel):
    subject: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=10, max_length=4000)
    category: str = "question"


class TicketReplyIn(BaseModel):
    reply: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[str] = None


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: Optional[str] = Field(default=None, max_length=1200)


def _ticket_json(t: SupportTicket) -> dict:
    return {
        "id": t.id,
        "subject": t.subject,
        "body": t.body,
        "category": t.category,
        "status": t.status,
        "reply": t.reply,
        "repliedAt": t.repliedAt.isoformat() if t.repliedAt else None,
        "createdAt": t.createdAt.isoformat() if t.createdAt else None,
    }


async def _require_admin(user_id: str) -> User:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
    if not user or not getattr(user, "isSuperAdmin", False):
        # 404 rather than 403: an endpoint that answers "forbidden" has
        # confirmed it exists, which is the first half of finding it.
        raise HTTPException(status_code=404, detail="Not found")
    return user


# =============================================================================
# Tickets — the customer's side
# =============================================================================
@router.post("/tickets")
async def create_ticket(
    data: TicketIn, request: Request, user_id: str = Depends(verify_user)
) -> dict:
    if data.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")

    workspace_id = request.headers.get("x-workspace-id") or None
    async with AsyncSessionLocal() as session:
        if workspace_id:
            # A workspace id from a header is a claim, not a fact.
            owned = await session.get(BusinessProfile, workspace_id)
            if not owned or owned.userId != user_id:
                workspace_id = None

        ticket = SupportTicket(
            userId=user_id,
            businessProfileId=workspace_id,
            subject=data.subject.strip(),
            body=data.body.strip(),
            category=data.category,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

    logger.info(f"Support ticket {ticket.id} opened by {user_id} ({data.category})")
    return {"success": True, "ticket": _ticket_json(ticket)}


@router.get("/tickets")
async def my_tickets(user_id: str = Depends(verify_user)) -> dict:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(SupportTicket)
            .where(SupportTicket.userId == user_id)
            .order_by(SupportTicket.createdAt.desc())
            .limit(50)
        )).scalars().all()
    return {"success": True, "tickets": [_ticket_json(t) for t in rows]}


# =============================================================================
# Tickets — the operator's side
# =============================================================================
@router.get("/admin/tickets")
async def all_tickets(status: Optional[str] = None, user_id: str = Depends(verify_user)) -> dict:
    await _require_admin(user_id)
    async with AsyncSessionLocal() as session:
        stmt = select(SupportTicket).order_by(SupportTicket.createdAt.desc()).limit(200)
        if status in STATUSES:
            stmt = stmt.where(SupportTicket.status == status)
        rows = (await session.execute(stmt)).scalars().all()

        emails = {}
        if rows:
            users = (await session.execute(
                select(User).where(User.id.in_({t.userId for t in rows}))
            )).scalars().all()
            emails = {u.id: u.email for u in users}

    return {
        "success": True,
        "tickets": [{**_ticket_json(t), "userEmail": emails.get(t.userId)} for t in rows],
    }


@router.patch("/admin/tickets/{ticket_id}")
async def reply_to_ticket(
    ticket_id: str, data: TicketReplyIn, user_id: str = Depends(verify_user)
) -> dict:
    await _require_admin(user_id)
    if data.status is not None and data.status not in STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status")

    async with AsyncSessionLocal() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if data.reply is not None:
            ticket.reply = data.reply.strip() or None
            ticket.repliedAt = datetime.now(timezone.utc) if ticket.reply else None
            # Answering a ticket that is still "open" and leaving it open is
            # how a queue stops meaning anything.
            if ticket.reply and ticket.status == "open" and data.status is None:
                ticket.status = "in_progress"

        if data.status is not None:
            ticket.status = data.status

        await session.commit()
        await session.refresh(ticket)

    return {"success": True, "ticket": _ticket_json(ticket)}


# =============================================================================
# Reviews
# =============================================================================
@router.post("/reviews")
async def submit_review(data: ReviewIn, user_id: str = Depends(verify_user)) -> dict:
    """One review per account, editable until it is approved.

    Editable-after-approval would let an approved five-star quote be rewritten
    into anything at all while still displayed as vetted.
    """
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.userId == user_id).limit(1)
        )).scalars().first()

        existing = (await session.execute(
            select(Review).where(Review.userId == user_id)
        )).scalars().first()

        if existing and existing.isApproved:
            raise HTTPException(
                status_code=409,
                detail="Your review is already published. Contact support to change it.",
            )

        review = existing or Review(userId=user_id)
        review.rating = data.rating
        review.body = (data.body or "").strip() or None
        review.authorName = (getattr(user, "name", None) or "").strip() or None
        review.authorBusiness = (getattr(profile, "name", None) or "").strip() or None
        review.isApproved = False

        if existing is None:
            session.add(review)
        await session.commit()

    return {"success": True, "message": "Thank you — we read every one of these."}


@router.get("/reviews/mine")
async def my_review(user_id: str = Depends(verify_user)) -> dict:
    async with AsyncSessionLocal() as session:
        r = (await session.execute(
            select(Review).where(Review.userId == user_id)
        )).scalars().first()
    if not r:
        return {"success": True, "review": None}
    return {
        "success": True,
        "review": {
            "rating": r.rating,
            "body": r.body,
            "isApproved": r.isApproved,
            "createdAt": r.createdAt.isoformat() if r.createdAt else None,
        },
    }


@router.get("/admin/reviews")
async def all_reviews(user_id: str = Depends(verify_user)) -> dict:
    await _require_admin(user_id)
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Review).order_by(Review.createdAt.desc()).limit(200)
        )).scalars().all()
    return {
        "success": True,
        "reviews": [{
            "id": r.id, "rating": r.rating, "body": r.body,
            "authorName": r.authorName, "authorBusiness": r.authorBusiness,
            "isApproved": r.isApproved,
            "createdAt": r.createdAt.isoformat() if r.createdAt else None,
        } for r in rows],
    }


@router.patch("/admin/reviews/{review_id}")
async def approve_review(review_id: str, approve: bool = True, user_id: str = Depends(verify_user)) -> dict:
    await _require_admin(user_id)
    async with AsyncSessionLocal() as session:
        r = await session.get(Review, review_id)
        if not r:
            raise HTTPException(status_code=404, detail="Review not found")
        r.isApproved = bool(approve)
        await session.commit()
    return {"success": True, "isApproved": bool(approve)}


# =============================================================================
# Public — what the landing page shows
# =============================================================================
@public_router.get("/reviews")
async def public_reviews() -> dict:
    """Approved reviews only. This is the one endpoint with no auth, so the
    isApproved filter is the whole of the moderation guarantee."""
    try:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                select(Review)
                .where(Review.isApproved.is_(True))
                .order_by(Review.createdAt.desc())
                .limit(12)
            )).scalars().all()
    except Exception as e:
        # The landing page renders without this rather than not at all.
        logger.warning(f"Public reviews unavailable: {e}")
        return {"reviews": [], "count": 0, "average": None}

    return {
        "reviews": [{
            "rating": r.rating,
            "body": r.body,
            "author": r.authorName,
            "business": r.authorBusiness,
        } for r in rows],
        "count": len(rows),
        "average": round(sum(r.rating for r in rows) / len(rows), 1) if rows else None,
    }
