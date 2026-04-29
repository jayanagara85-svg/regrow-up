"""
BACKEND PATCHES — All new/modified endpoints for Regrow v1.1 → v1.2

Files to modify:
  1. backend/app/models/activity_model.py    → NEW (copy from patches)
  2. backend/app/services/activity_service.py → NEW (copy from patches)
  3. backend/app/api/feed.py                 → NEW (this file)
  4. backend/app/models/loopchat_models.py   → ADD buyer_name field
  5. backend/app/api/loopchat.py             → ADD PATCH channel post endpoint
  6. backend/app/api/pickups.py              → ADD user_phone to response
  7. backend/app/api/webhook.py              → ADD links in WA responses
  8. backend/app/workers/classification_worker.py → EMIT feed event on grade done
  9. backend/app/main.py                     → REGISTER feed router + activity model
"""

# ═══════════════════════════════════════════════════════════════════════════
# FILE: backend/app/api/feed.py   (NEW FILE)
# ═══════════════════════════════════════════════════════════════════════════

FEED_PY = '''
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.core.database import get_db
from app.models.activity_model import ActivityEvent

router = APIRouter(prefix="/api/feed", tags=["feed"])


class ActivityEventOut(BaseModel):
    id: UUID
    event_type: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    title: str
    subtitle: Optional[str]
    created_at: datetime
    class Config: from_attributes = True


@router.get("", response_model=List[ActivityEventOut])
async def get_feed(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/feed
    Returns latest activity events for the Dashboard feed.
    No auth required — internal dashboard tool.
    """
    result = await db.execute(
        select(ActivityEvent)
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
'''

print("=== feed.py ===")
print(FEED_PY)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH: backend/app/api/loopchat.py
# ADD channel post PATCH endpoint (missing — needed for pin/unpin + edit)
# ═══════════════════════════════════════════════════════════════════════════

CHANNEL_PATCH_ENDPOINT = '''
# ADD after the existing @router.post("/api/channel/posts") endpoint:

class ChannelPostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    is_pinned: Optional[bool] = None


@router.patch("/api/channel/posts/{post_id}", response_model=ChannelPostOut)
async def update_post(
    post_id: str,
    body: ChannelPostUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """PATCH /api/channel/posts/{id} — edit or pin/unpin a post"""
    import uuid as uuid_module
    result = await db.execute(
        select(ChannelPost).where(ChannelPost.id == uuid_module.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    
    if body.title is not None:    post.title    = body.title
    if body.content is not None:  post.content  = body.content
    if body.category is not None: post.category = body.category
    if body.is_pinned is not None: post.is_pinned = body.is_pinned
    
    await db.flush()
    await db.refresh(post)
    return post
'''

print("=== channel PATCH endpoint ===")
print(CHANNEL_PATCH_ENDPOINT)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH: backend/app/api/pickups.py
# ADD user_phone to PickupListOut so dashboard can show user identity
# ═══════════════════════════════════════════════════════════════════════════

PICKUP_LIST_PATCH = '''
# In schemas.py: update PickupListOut to include user_phone
class PickupListOut(BaseModel):
    id: UUID
    user_id: UUID
    user_phone: Optional[str] = None   # ← ADD THIS
    location: str
    waste_type: str
    status: PickupStatus
    created_at: datetime
    class Config: from_attributes = True


# In pickups.py: update list_pickups to join User and attach phone
# REPLACE:
#   rows = (await db.execute(q)).scalars().all()
#
# WITH:
from sqlalchemy.orm import joinedload

@router.get("", response_model=PaginatedPickups)
async def list_pickups(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[PickupStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    q = select(Pickup).options(joinedload(Pickup.user))
    if status:
        q = q.where(Pickup.status == status)
    q = q.order_by(Pickup.created_at.desc())

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar()

    q = q.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(q)).unique().scalars().all()

    # Attach user_phone to each row (not a DB column, set manually)
    items = []
    for p in rows:
        item = PickupListOut.model_validate(p)
        item.user_phone = p.user.phone if p.user else None
        items.append(item)

    return PaginatedPickups(items=items, total=total, page=page, limit=limit)
'''

print("=== pickup list patch ===")
print(PICKUP_LIST_PATCH)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH: backend/app/api/pickups.py + loopchat.py
# EMIT feed events on key state changes
# ═══════════════════════════════════════════════════════════════════════════

EMIT_EVENTS_PATCH = '''
# In pickups.py — add to create_pickup():
from app.services.activity_service import log_event

@router.post("", response_model=PickupOut, status_code=201)
async def create_pickup(body: PickupCreate, db: AsyncSession = Depends(get_db)):
    ...
    # After: db.add(pickup); await db.flush()
    await log_event(
        db,
        event_type="pickup_created",
        title=f"Pickup baru: {body.waste_type}",
        subtitle=f"{body.location[:60]}",
        entity_type="pickup",
        entity_id=str(pickup.id),
        user_id=user_uuid,
    )
    ...


# In pickups.py — add to update_pickup():
@router.patch("/{pickup_id}", response_model=PickupOut)
async def update_pickup(...):
    ...
    if body.status == PickupStatus.confirmed:
        await log_event(
            db,
            event_type="pickup_confirmed",
            title=f"Pickup dikonfirmasi",
            subtitle=f"{pickup.waste_type} · {pickup.location[:40]}",
            entity_type="pickup",
            entity_id=str(pickup.id),
        )
    ...


# In loopchat.py — add to create_listing():
@router.post("/api/marketplace/listings", ...)
async def create_listing(body: ListingCreate, ...):
    ...
    # After listing created
    await log_event(
        db,
        event_type="listing_created",
        title=f"Listing baru: {body.waste_type}",
        subtitle=f"{body.weight or '?'} kg · {window.formatIDR(body.price_estimate)}",
        entity_type="listing",
        entity_id=str(listing.id),
    )
    ...


# In loopchat.py — add to update_listing_status():
@router.patch("/api/marketplace/listings/{listing_id}", ...)
async def update_listing_status(listing_id, status, ...):
    ...
    if status == ListingStatus.matched:
        await log_event(
            db,
            event_type="listing_matched",
            title=f"Listing dipasangkan: {listing.waste_type}",
            subtitle=f"Pembeli ditugaskan",
            entity_type="listing",
            entity_id=str(listing.id),
        )
    ...


# In loopchat.py — add to broadcast_message():
@router.post("/api/communities/{community_id}/broadcast")
async def broadcast_message(community_id, body, ...):
    count = await broadcast_to_community(community_id, body.message, db)
    await log_event(
        db,
        event_type="broadcast_sent",
        title=f"Broadcast ke komunitas ({count} anggota)",
        subtitle=body.message[:80],
        entity_type="community",
        entity_id=community_id,
    )
    return {"sent_to": count, "message": body.message}
'''

print("=== emit events patch ===")
print(EMIT_EVENTS_PATCH)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH: backend/app/workers/classification_worker.py
# EMIT grade_completed event after grading finishes
# ═══════════════════════════════════════════════════════════════════════════

WORKER_PATCH = '''
# In _grade_file_async(), after: await session.commit()

from app.services.activity_service import log_event

# After grading result saved:
await log_event(
    session,
    event_type="grade_completed",
    title=f"Grading selesai: Grade {grade_data['grade']} ({int(grade_data['confidence']*100)}%)",
    subtitle=f"{grade_data.get('estimated_kg', '?')} kg · {grade_data.get('reasoning', '')[:60]}",
    entity_type="pickup",
    entity_id=str(file_obj.pickup_id),
    user_id=file_obj.pickup.user_id if hasattr(file_obj, 'pickup') else None,
)
await session.commit()
'''

print("=== worker patch ===")
print(WORKER_PATCH)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH: backend/app/main.py
# Register feed router + import activity model
# ═══════════════════════════════════════════════════════════════════════════

MAIN_PY_PATCH = '''
# In main.py, add these imports:
from app.api import feed                          # ← ADD
from app.models import activity_model             # ← ADD (so table is created)

# In the router section, add:
app.include_router(feed.router)                   # ← ADD

# In lifespan, the create_tables() call will auto-create activity_events table
# because activity_model.py imports Base and SQLAlchemy sees the class.
'''

print("=== main.py patch ===")
print(MAIN_PY_PATCH)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH: WhatsApp messages include web links
# In loopchat/handlers.py — update responses to include app URL
# ═══════════════════════════════════════════════════════════════════════════

WHATSAPP_LINKS_PATCH = '''
# Add at top of handlers.py:
APP_URL = "http://localhost:3000"  # Change to production URL


# In handle_pickup_step() — after creating pickup:
return (
    f"🎉 *Booking berhasil!*\\n\\n"
    f"📋 ID: *{pid}*\\n"
    f"♻️ Jenis: *{waste_type}*\\n"
    f"📍 Lokasi: *{location}*\\n\\n"
    f"🔗 Pantau status: {APP_URL}/Dashboard.html\\n"    # ← ADD LINK
    f"Tim kami akan segera konfirmasi."
)


# In _notify_user_graded() — include link to dashboard:
message = (
    f"🎯 *Hasil Penilaian Sampah Anda*\\n\\n"
    f"{emoji} Grade: *{grade}* ({confidence}% keyakinan)\\n"
    f"⚖️ Estimasi berat: *{est_kg} kg*\\n"
    f"📝 {reasoning}\\n\\n"
    f"🔗 Lihat detail: {APP_URL}/Dashboard.html"    # ← ADD LINK
)
'''

print("=== WhatsApp links patch ===")
print(WHATSAPP_LINKS_PATCH)
