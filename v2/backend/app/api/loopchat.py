"""
LOOPCHAT REST API ROUTES
Provides CRUD endpoints for dashboard + admin use.

Routes:
  GET/POST  /api/marketplace/listings
  GET       /api/marketplace/listings/{id}
  PATCH     /api/marketplace/listings/{id}

  GET/POST  /api/communities
  POST      /api/communities/{id}/broadcast
  POST      /api/communities/{id}/members

  GET/POST  /api/channel/posts
  DELETE    /api/channel/posts/{id}
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.loopchat_models import (
    MarketplaceListing, ListingStatus,
    Community, UserCommunity, ChannelPost,
)
from app.loopchat.handlers import broadcast_to_community

router = APIRouter(tags=["loopchat"])


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKETPLACE
# ═══════════════════════════════════════════════════════════════════════════════

class ListingOut(BaseModel):
    id: UUID
    user_id: UUID
    waste_type: str
    weight: Optional[float]
    price_estimate: Optional[float]
    status: ListingStatus
    created_at: datetime
    class Config: from_attributes = True

class ListingCreate(BaseModel):
    user_id: str
    waste_type: str
    weight: Optional[float] = None
    price_estimate: Optional[float] = None


@router.get("/api/marketplace/listings", response_model=List[ListingOut])
async def list_marketplace(
    status: Optional[ListingStatus] = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    q = select(MarketplaceListing).order_by(MarketplaceListing.created_at.desc()).limit(limit)
    if status:
        q = q.where(MarketplaceListing.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/api/marketplace/listings", response_model=ListingOut, status_code=201)
async def create_listing(
    body: ListingCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    import uuid
    listing = MarketplaceListing(
        user_id=uuid.UUID(body.user_id),
        waste_type=body.waste_type,
        weight=body.weight,
        price_estimate=body.price_estimate,
        status=ListingStatus.open,
    )
    db.add(listing)
    await db.flush()
    await db.refresh(listing)
    return listing


@router.patch("/api/marketplace/listings/{listing_id}", response_model=ListingOut)
async def update_listing_status(
    listing_id: str,
    status: ListingStatus,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    import uuid
    result = await db.execute(
        select(MarketplaceListing).where(MarketplaceListing.id == uuid.UUID(listing_id))
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(404, "Listing not found")
    listing.status = status
    await db.flush()
    return listing


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMUNITY
# ═══════════════════════════════════════════════════════════════════════════════

class CommunityOut(BaseModel):
    id: UUID
    name: str
    area: Optional[str]
    is_active: bool
    created_at: datetime
    class Config: from_attributes = True

class CommunityCreate(BaseModel):
    name: str
    area: Optional[str] = None
    description: Optional[str] = None

class BroadcastBody(BaseModel):
    message: str

class AddMemberBody(BaseModel):
    user_id: str
    is_admin: bool = False


@router.get("/api/communities", response_model=List[CommunityOut])
async def list_communities(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Community).where(Community.is_active.is_(True))
    )
    return result.scalars().all()


@router.post("/api/communities", response_model=CommunityOut, status_code=201)
async def create_community(
    body: CommunityCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    community = Community(
        name=body.name,
        area=body.area,
        description=body.description,
    )
    db.add(community)
    await db.flush()
    await db.refresh(community)
    return community


@router.post("/api/communities/{community_id}/broadcast")
async def broadcast_message(
    community_id: str,
    body: BroadcastBody,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    count = await broadcast_to_community(community_id, body.message, db)
    return {"sent_to": count, "message": body.message}


@router.post("/api/communities/{community_id}/members", status_code=201)
async def add_member(
    community_id: str,
    body: AddMemberBody,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    import uuid
    membership = UserCommunity(
        user_id=uuid.UUID(body.user_id),
        community_id=uuid.UUID(community_id),
        is_admin=body.is_admin,
    )
    db.add(membership)
    await db.flush()
    return {"status": "added", "user_id": body.user_id, "community_id": community_id}


@router.get("/api/communities/{community_id}/members")
async def list_members(
    community_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    import uuid
    from app.models.models import User
    result = await db.execute(
        select(UserCommunity, User)
        .join(User, UserCommunity.user_id == User.id)
        .where(UserCommunity.community_id == uuid.UUID(community_id))
    )
    rows = result.all()
    return [
        {
            "user_id": str(uc.user_id),
            "phone": u.phone,
            "name": u.name,
            "is_admin": uc.is_admin,
            "joined_at": uc.joined_at,
        }
        for uc, u in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  CHANNEL POSTS
# ═══════════════════════════════════════════════════════════════════════════════

class ChannelPostOut(BaseModel):
    id: UUID
    title: str
    content: str
    category: str
    is_pinned: bool
    views: int
    created_at: datetime
    class Config: from_attributes = True

class ChannelPostCreate(BaseModel):
    title: str
    content: str
    category: str = "info"
    is_pinned: bool = False
    author_id: Optional[str] = None


@router.get("/api/channel/posts", response_model=List[ChannelPostOut])
async def list_posts(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(ChannelPost)
        .order_by(ChannelPost.is_pinned.desc(), ChannelPost.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/api/channel/posts", response_model=ChannelPostOut, status_code=201)
async def create_post(
    body: ChannelPostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import uuid
    post = ChannelPost(
        title=body.title,
        content=body.content,
        category=body.category,
        is_pinned=body.is_pinned,
        author_id=uuid.UUID(body.author_id) if body.author_id else None,
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    return post


@router.delete("/api/channel/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    import uuid
    result = await db.execute(
        select(ChannelPost).where(ChannelPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    await db.delete(post)
