"""
REGROW v1.2 — CONSOLIDATED BACKEND PATCHES
===========================================
Apply these changes to connect the real backend to the frontend.
Each section is labelled with the file to modify.

Order matters — apply in sequence.
"""


# ═══════════════════════════════════════════════════════════════════════════
# 1. NEW FILE: backend/app/models/activity_model.py
#    (copy activity_model.py from the patches/ folder — already provided)
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 2. NEW FILE: backend/app/services/activity_service.py
#    (copy activity_service.py from the patches/ folder — already provided)
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 3. NEW FILE: backend/app/api/feed.py
#    (copy feed.py from the patches/ folder — already provided)
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 4. MODIFY: backend/app/main.py
#    Add feed router + import activity model so table gets created on startup
# ═══════════════════════════════════════════════════════════════════════════

MAIN_PY_ADDITIONS = """
# ── Add these imports near the top, after existing route imports ──
from app.api import feed
from app.models import activity_model   # ensures table is created via Base.metadata

# ── Add this inside the app.include_router() block ──
app.include_router(feed.router)
"""


# ═══════════════════════════════════════════════════════════════════════════
# 5. MODIFY: backend/app/models/schemas.py
#    Add user_phone to PickupListOut
# ═══════════════════════════════════════════════════════════════════════════

# FIND this class:
#   class PickupListOut(BaseModel):
#       id: UUID
#       user_id: UUID
#       ...
# ADD this field:
SCHEMA_PICKUP_ADDITION = """
    user_phone: Optional[str] = None    # joined from User table
"""

# Full updated class for reference:
PICKUP_LIST_OUT_FULL = """
class PickupListOut(BaseModel):
    id:         UUID
    user_id:    UUID
    user_phone: Optional[str] = None   # ← NEW
    location:   str
    waste_type: str
    status:     PickupStatus
    created_at: datetime

    class Config:
        from_attributes = True
"""


# ═══════════════════════════════════════════════════════════════════════════
# 6. MODIFY: backend/app/api/pickups.py
#    a) Join User table to return user_phone
#    b) Emit feed events on create + status update
# ═══════════════════════════════════════════════════════════════════════════

PICKUPS_PY_IMPORTS_ADD = """
from sqlalchemy.orm import joinedload
from app.services.activity_service import log_event
"""

# Replace list_pickups() with this version:
LIST_PICKUPS_REPLACEMENT = """
@router.get("", response_model=PaginatedPickups)
async def list_pickups(
    page:   int                  = Query(1,  ge=1),
    limit:  int                  = Query(20, ge=1, le=100),
    status: Optional[PickupStatus] = None,
    db:     AsyncSession         = Depends(get_db),
    _:      dict                 = Depends(get_current_user),
):
    # Build query with user join for phone number
    q = select(Pickup).options(joinedload(Pickup.user))
    if status:
        q = q.where(Pickup.status == status)
    q = q.order_by(Pickup.created_at.desc())

    # Count
    count_q = select(func.count(Pickup.id))
    if status:
        count_q = count_q.where(Pickup.status == status)
    total = (await db.execute(count_q)).scalar()

    # Page
    q = q.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(q)).unique().scalars().all()

    items = [
        PickupListOut(
            id         = p.id,
            user_id    = p.user_id,
            user_phone = p.user.phone if p.user else None,
            location   = p.location,
            waste_type = p.waste_type,
            status     = p.status,
            created_at = p.created_at,
        )
        for p in rows
    ]
    return PaginatedPickups(items=items, total=total, page=page, limit=limit)
"""

# In create_pickup(), after pickup is flushed and before commit, ADD:
CREATE_PICKUP_EVENT = """
    await log_event(
        db,
        event_type  = "pickup_created",
        title       = f"Pickup baru: {pickup.waste_type}",
        subtitle    = pickup.location[:60] if pickup.location else None,
        entity_type = "pickup",
        entity_id   = str(pickup.id),
        user_id     = user_uuid,
    )
    # The existing db.commit() below will also commit this event
"""

# In update_pickup() (PATCH endpoint), after status is set, ADD:
UPDATE_PICKUP_EVENT = """
    # After setting new status — emit feed event
    event_map = {
        PickupStatus.confirmed:  ("pickup_confirmed",  "Pickup dikonfirmasi"),
        PickupStatus.completed:  ("pickup_completed",  "Pickup selesai"),
        PickupStatus.cancelled:  ("pickup_cancelled",  "Pickup dibatalkan"),
    }
    if body.status and body.status in event_map:
        etype, etitle = event_map[body.status]
        await log_event(
            db,
            event_type  = etype,
            title       = etitle,
            subtitle    = f"{pickup.waste_type} — {pickup.location[:40]}",
            entity_type = "pickup",
            entity_id   = str(pickup.id),
        )
"""


# ═══════════════════════════════════════════════════════════════════════════
# 7. MODIFY: backend/app/api/loopchat.py
#    a) Add PATCH /api/channel/posts/{post_id}
#    b) Emit feed events on listing create + broadcast
# ═══════════════════════════════════════════════════════════════════════════

CHANNEL_PATCH_ENDPOINT = """
# ── ADD after the existing @router.post(\"/api/channel/posts\") handler ──

from typing import Optional as Opt

class ChannelPostUpdate(BaseModel):
    title:     Opt[str]  = None
    content:   Opt[str]  = None
    category:  Opt[str]  = None
    is_pinned: Opt[bool] = None

@router.patch("/api/channel/posts/{post_id}", response_model=ChannelPostOut)
async def update_channel_post(
    post_id: str,
    body:    ChannelPostUpdate,
    db:      AsyncSession = Depends(get_db),
    _:       dict         = Depends(get_current_user),
):
    import uuid as _uuid
    result = await db.execute(
        select(ChannelPost).where(ChannelPost.id == _uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")

    if body.title     is not None: post.title     = body.title
    if body.content   is not None: post.content   = body.content
    if body.category  is not None: post.category  = body.category
    if body.is_pinned is not None: post.is_pinned = body.is_pinned

    await db.flush()
    await db.refresh(post)
    return post
"""

# In create_listing(), after listing is flushed, ADD:
LISTING_EVENT = """
    from app.services.activity_service import log_event
    await log_event(
        db,
        event_type  = "listing_created",
        title       = f"Listing baru: {body.waste_type}",
        subtitle    = f"{body.weight or '?'} kg",
        entity_type = "listing",
        entity_id   = str(listing.id),
    )
"""

# In update_listing() (match buyer), ADD:
LISTING_MATCH_EVENT = """
    from app.services.activity_service import log_event
    if body.status == "matched":
        await log_event(
            db,
            event_type  = "listing_matched",
            title       = f"Buyer dipasangkan ke listing {listing.waste_type}",
            subtitle    = f"{listing.weight} kg",
            entity_type = "listing",
            entity_id   = str(listing.id),
        )
    elif body.status == "completed":
        await log_event(
            db,
            event_type  = "listing_completed",
            title       = f"Transaksi selesai: {listing.waste_type}",
            subtitle    = f"{listing.weight} kg",
            entity_type = "listing",
            entity_id   = str(listing.id),
        )
"""

# In broadcast_message(), after sending, ADD:
BROADCAST_EVENT = """
    from app.services.activity_service import log_event
    await log_event(
        db,
        event_type  = "broadcast_sent",
        title       = f"Broadcast ke komunitas ({sent_count} anggota)",
        subtitle    = body.message[:80],
        entity_type = "community",
        entity_id   = str(community_id),
    )
"""


# ═══════════════════════════════════════════════════════════════════════════
# 8. MODIFY: backend/app/workers/classification_worker.py
#    Emit grade_completed event after grading finishes
# ═══════════════════════════════════════════════════════════════════════════

WORKER_GRADE_EVENT = """
# ── FIND: the block after grading result is saved to DB ──
# ── ADD before session.commit(): ──

from app.services.activity_service import log_event

await log_event(
    session,
    event_type  = "grade_completed",
    title       = f"Grading selesai: Grade {grade_data['grade']} ({int(grade_data.get('confidence', 0) * 100)}%)",
    subtitle    = f"Est. {grade_data.get('estimated_kg', '?')} kg — {grade_data.get('reasoning', '')[:60]}",
    entity_type = "pickup",
    entity_id   = str(file_obj.pickup_id),
)
# The existing session.commit() below will commit both the grade and the event
"""


# ═══════════════════════════════════════════════════════════════════════════
# 9. MODIFY: backend/app/loopchat/handlers.py (or webhook.py)
#    Add deep links in WhatsApp reply messages
# ═══════════════════════════════════════════════════════════════════════════

WA_LINKS_PATCH = """
import os
APP_URL = os.getenv("APP_URL", "http://localhost:3000")

# ── In handle_pickup_step(), replace the return/send message with: ──
pickup_msg = (
    f"🎉 *Booking berhasil!*\\n\\n"
    f"📋 ID: *{pickup_id_short}*\\n"
    f"♻️ Jenis: *{waste_type}*\\n"
    f"📍 Lokasi: *{location}*\\n\\n"
    f"🔗 Pantau status: {APP_URL}/Dashboard.html\\n"
    f"Tim kami akan segera konfirmasi penjemputan Anda."
)

# ── In _notify_user_graded() or wherever you send grading result: ──
grade_msg = (
    f"🎯 *Hasil Penilaian Sampah Anda*\\n\\n"
    f"{emoji} Grade: *{grade}* ({confidence}% keyakinan)\\n"
    f"⚖️ Estimasi berat: *{est_kg} kg*\\n"
    f"📝 {reasoning}\\n\\n"
    f"🔗 Detail lengkap: {APP_URL}/Dashboard.html\\n"
    f"Hubungi kami jika ada pertanyaan."
)

# ── In marketplace match notification: ──
match_msg = (
    f"✅ *Listing Anda telah terpasangkan!*\\n\\n"
    f"♻️ Jenis: *{waste_type}*\\n"
    f"🔗 Detail: {APP_URL}/Marketplace.html\\n"
    f"Silakan koordinasikan pengiriman dengan tim kami."
)
"""

# ── .env additions ─────────────────────────────────────────────────────────
ENV_ADDITIONS = """
# Add to .env:
APP_URL=https://yourapp.com
"""


# ═══════════════════════════════════════════════════════════════════════════
# QUICK VERIFICATION SCRIPT
# Run after applying all patches:
# ═══════════════════════════════════════════════════════════════════════════

VERIFY_SCRIPT = """
#!/bin/bash
set -e
BASE=http://localhost:8001

echo "1. Health check..."
curl -sf $BASE/health | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK:', d.get('status'))"

echo "2. Feed endpoint..."
curl -sf $BASE/api/feed | python3 -c "import json,sys; d=json.load(sys.stdin); print('Feed OK, events:', len(d))"

echo "3. Login..."
TOKEN=$(curl -sf -X POST $BASE/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"phone":"08001234567","password":"operatorpass123"}' \\
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:20}..."

echo "4. Pickups list (with user_phone)..."
curl -sf -H "Authorization: Bearer $TOKEN" $BASE/api/pickups \\
  | python3 -c "import json,sys; d=json.load(sys.stdin); p=d['items'][0] if d['items'] else {}; print('user_phone present:', 'user_phone' in p)"

echo "5. Simulate WhatsApp pickup..."
curl -sf -X POST $BASE/api/webhook/whatsapp \\
  -H "Content-Type: application/json" \\
  -d '{"entry":[{"changes":[{"value":{"messages":[{"from":"628111222333","type":"text","text":{"body":"jemput"}}]}}]}]}'

echo "6. Check feed has pickup_created..."
sleep 1
curl -sf $BASE/api/feed | python3 -c "import json,sys; d=json.load(sys.stdin); types=[e['event_type'] for e in d]; print('pickup_created in feed:', 'pickup_created' in types)"

echo "\\nAll checks passed. Open feed.html in browser."
"""
