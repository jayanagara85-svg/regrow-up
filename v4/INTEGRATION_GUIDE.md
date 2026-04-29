# REGROW v1.1 → v1.2: COMPLETE INTEGRATION GUIDE
## Turn the fake UI into a real working system
## Estimated time: 1–2 days for a senior engineer, 3–4 days for a mid-level

---

## SYSTEM FIX OVERVIEW

### What changes in v1.2
```
v1.1 (before):                      v1.2 (after):
─────────────────────────────────   ─────────────────────────────────
Dashboard.html = MOCK data     →    Dashboard.html = real /api/pickups
Marketplace.html = MOCK data   →    Marketplace.html = real /api/marketplace
Channel.html = MOCK data       →    Channel.html = real /api/channel/posts
Broadcast.html = MOCK data     →    Broadcast.html = real /api/communities/broadcast

No auth in HTML pages          →    JWT auth via localStorage (shared api.js)
No activity feed               →    GET /api/feed with activity_events table
No PATCH channel posts         →    PATCH /api/channel/posts/{id} (pin/edit)
No user_phone in pickups       →    user_phone joined from User table
No web links in WhatsApp msgs  →    Every WA response includes dashboard URL
```

---

## DATA FLOW (after fix)

```
WhatsApp user:
  User → "jemput"
  Loopchat router → creates Pickup in DB
  → log_event("pickup_created") in activity_events table
  → sends WA reply with link: "https://yourapp.com/Dashboard.html"

Operator (web):
  Opens Dashboard.html
  → api.js checks localStorage for JWT
  → if no token → redirect to login.html
  → login.html → POST /api/auth/login → get JWT → store in localStorage
  → Dashboard: GET /api/pickups → shows real pickup data
  → Dashboard: GET /api/feed → shows activity events
  → Operator clicks "Konfirmasi" → PATCH /api/pickups/{id} → status=confirmed
  → → log_event("pickup_confirmed")
  → Operator opens Marketplace.html → GET /api/marketplace/listings
  → Operator clicks "Pasangkan Pembeli" → PATCH /api/marketplace/listings/{id}
  → → log_event("listing_matched")
  → Operator opens Broadcast.html → GET /api/communities
  → Operator sends broadcast → POST /api/communities/{id}/broadcast
  → → Sends real WhatsApp to all members
  → → log_event("broadcast_sent")

AI Worker:
  Pickup confirmed → file uploaded → RQ worker runs
  → Calls Gemini Vision → grade result
  → Saves to DB
  → log_event("grade_completed")
  → Sends WhatsApp notification with link
```

---

## STEP-BY-STEP IMPLEMENTATION

### WEEK 1: Backend + Auth (Days 1–3)

#### Day 1: Add activity_events table + feed endpoint

**Step 1.1: Copy new model file**
```bash
cp patches/activity_model.py backend/app/models/activity_model.py
cp patches/activity_service.py backend/app/services/activity_service.py
cp patches/feed.py backend/app/api/feed.py
```

**Step 1.2: Register in main.py**
```python
# In backend/app/main.py, add:
from app.api import feed
from app.models import activity_model  # ensures table is created

# In app.include_router() section:
app.include_router(feed.router)
```

**Step 1.3: Test**
```bash
docker compose restart backend
curl http://localhost:8001/api/feed
# → []  (empty array, no events yet — that's correct)
```

---

#### Day 1: Add PATCH endpoint for channel posts

**Step 1.4: In backend/app/api/loopchat.py, add after the existing POST /api/channel/posts:**

```python
from typing import Optional as Opt

class ChannelPostUpdate(BaseModel):
    title: Opt[str] = None
    content: Opt[str] = None
    category: Opt[str] = None
    is_pinned: Opt[bool] = None

@router.patch("/api/channel/posts/{post_id}", response_model=ChannelPostOut)
async def update_channel_post(
    post_id: str,
    body: ChannelPostUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    import uuid as _uuid
    result = await db.execute(
        select(ChannelPost).where(ChannelPost.id == _uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    if body.title is not None:     post.title     = body.title
    if body.content is not None:   post.content   = body.content
    if body.category is not None:  post.category  = body.category
    if body.is_pinned is not None: post.is_pinned = body.is_pinned
    await db.flush()
    await db.refresh(post)
    return post
```

**Test:**
```bash
# Get a post ID first
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/channel/posts

# Pin a post
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_pinned": true}' \
  http://localhost:8001/api/channel/posts/{post_id}
```

---

#### Day 2: Add user_phone to pickup list response

**Step 2.1: Update backend/app/models/schemas.py**

```python
# Modify PickupListOut:
class PickupListOut(BaseModel):
    id: UUID
    user_id: UUID
    user_phone: Optional[str] = None    # ← ADD
    location: str
    waste_type: str
    status: PickupStatus
    created_at: datetime
    class Config: from_attributes = True
```

**Step 2.2: Update backend/app/api/pickups.py — list_pickups()**

```python
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

    count_q = select(func.count()).select_from(
        select(Pickup).where(Pickup.status == status).subquery() if status
        else select(Pickup).subquery()
    )
    total = (await db.execute(count_q)).scalar()

    q = q.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(q)).unique().scalars().all()

    items = []
    for p in rows:
        # Pydantic validation from ORM object
        d = {
            "id": p.id, "user_id": p.user_id,
            "user_phone": p.user.phone if p.user else None,
            "location": p.location, "waste_type": p.waste_type,
            "status": p.status, "created_at": p.created_at,
        }
        items.append(PickupListOut(**d))

    return PaginatedPickups(items=items, total=total, page=page, limit=limit)
```

---

#### Day 2: Emit feed events from routes

**In backend/app/api/pickups.py — create_pickup():**

```python
from app.services.activity_service import log_event

# After pickup is created and flushed:
await log_event(
    db,
    event_type="pickup_created",
    title=f"Pickup baru: {pickup.waste_type}",
    subtitle=pickup.location[:60] if pickup.location else None,
    entity_type="pickup",
    entity_id=str(pickup.id),
    user_id=user_uuid,
)
```

**In backend/app/api/pickups.py — update_pickup():**

```python
if body.status == PickupStatus.confirmed:
    await log_event(
        db,
        event_type="pickup_confirmed",
        title=f"Pickup dikonfirmasi",
        subtitle=f"{pickup.waste_type}",
        entity_type="pickup",
        entity_id=str(pickup.id),
    )
```

**In backend/app/api/loopchat.py — create_listing():**

```python
from app.services.activity_service import log_event

await log_event(
    db,
    event_type="listing_created",
    title=f"Listing baru: {body.waste_type}",
    subtitle=f"{body.weight or '?'} kg",
    entity_type="listing",
    entity_id=str(listing.id),
)
```

**In backend/app/api/loopchat.py — broadcast_message():**

```python
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
```

---

#### Day 3: Worker emits feed event on grade completion

**In backend/app/workers/classification_worker.py:**

Find the section after `await session.commit()` (the successful path) and add:

```python
# After grade saved and pickup status updated:
from app.services.activity_service import log_event

await log_event(
    session,
    event_type="grade_completed",
    title=f"Grading selesai: Grade {grade_data['grade']} ({int(grade_data['confidence']*100)}%)",
    subtitle=f"Est. {grade_data.get('estimated_kg', '?')} kg",
    entity_type="pickup",
    entity_id=str(file_obj.pickup_id),
)
await session.commit()  # commit the feed event too
```

---

### WEEK 1: Frontend Connection (Days 3–5)

#### Day 3: Add api.js + login.html

**Step 3.1: Create js/ directory in project root (alongside HTML files)**
```bash
mkdir -p js
cp patches/js/api.js js/api.js
cp patches/login.html login.html
```

**Step 3.2: Change BASE_URL in api.js if needed**
```javascript
// In js/api.js, line ~10:
const BASE_URL = window.REGROW_API_URL || 'http://localhost:8001';
// For production: set window.REGROW_API_URL = 'https://api.yourapp.com' in a <script> before api.js
```

**Step 3.3: Create first operator account**
```bash
curl -X POST http://localhost:8001/api/auth/register-operator \
  -H "Content-Type: application/json" \
  -d '{"phone": "08001234567", "password": "operatorpass123"}'
```

**Step 3.4: Test login**
Open `login.html` in browser → enter phone/password → should redirect to Dashboard.html

---

#### Day 4: Connect Dashboard.html

**In Dashboard.html:**

1. Add before the Babel script tag:
   ```html
   <script src="js/api.js"></script>
   ```

2. Remove: `const MOCK_PICKUPS = [...]` and `const MOCK_GRADES = {...}` and `NOW/minutesAgo/hoursAgo/daysAgo` helpers

3. Replace the entire `function Dashboard()` with the code from `patches/js/dashboard_patch.js`

4. Add `FeedItem` and `GradeModal` components from `patches/js/dashboard_patch.js`

**Test:**
- Open login.html → login → redirect to Dashboard.html
- Should show real pickup data from PostgreSQL
- Clicking "Konfirmasi" should actually update the DB

---

#### Day 4: Connect Marketplace.html

**In Marketplace.html:**

1. Add `<script src="js/api.js"></script>` before Babel

2. Remove `MOCK_LISTINGS` and `MOCK_BUYERS` constants

3. Replace `function Marketplace()` with code from `patches/js/marketplace_patch.js`

4. Replace `ListingCard` component with the version from the patch (adapts to real schema)

5. Replace `MatchModal` with version from patch (text input instead of hardcoded buyers)

6. Add `CreateListingModal` component from patch

---

#### Day 5: Connect Channel.html + Broadcast.html

**In Channel.html:**

1. Add api.js script tag

2. Remove `MOCK_POSTS` and `CATEGORIES` constants

3. Replace `function ChannelPage()` with code from `patches/js/channel_broadcast_patch.js`

4. Replace `PostCard` component — note the field name changes:
   - Mock: `post.body` → Real: `post.content`
   - Mock: `post.published_at` → Real: `post.created_at`
   - Mock: `post.pinned` → Real: `post.is_pinned`
   - Mock: `post.likes` → Real: (not in schema, remove)

**In Broadcast.html:**

1. Add api.js script tag

2. Remove `MOCK_COMMUNITIES` and `MOCK_HISTORY` constants

3. Replace `function BroadcastPage()` with code from `patches/js/channel_broadcast_patch.js`

4. Note: broadcast history is in-memory only (refreshes on page load) — backend doesn't store it

---

#### Day 5: Add WhatsApp links in WA responses

**In backend/app/loopchat/handlers.py:**

```python
APP_URL = "http://localhost:3000"  # TODO: set to real domain

# In handle_pickup_step, after booking created:
return (
    f"🎉 *Booking berhasil!*\n\n"
    f"📋 ID: *{pid}*\n"
    f"♻️ Jenis: *{waste_type}*\n"
    f"📍 Lokasi: *{location}*\n\n"
    f"🔗 Pantau status: {APP_URL}/Dashboard.html\n"
    f"Tim kami akan segera konfirmasi."
)

# In _notify_user_graded():
message = (
    f"🎯 *Hasil Penilaian Sampah Anda*\n\n"
    f"{emoji} Grade: *{grade}* ({confidence}% keyakinan)\n"
    f"⚖️ Estimasi berat: *{est_kg} kg*\n"
    f"📝 {reasoning}\n\n"
    f"🔗 Detail: {APP_URL}/Dashboard.html"
)
```

---

## FRONTEND → BACKEND API MAPPING

| Page | Real API calls | Method | Auth needed? |
|------|---------------|--------|-------------|
| **Dashboard** | GET /api/pickups | GET paginated list | ✅ JWT |
| | GET /api/feed | GET activity events | ❌ no auth |
| | GET /api/pickups/{id} | GET detail for grade modal | ✅ JWT |
| | PATCH /api/pickups/{id} | Confirm/complete | ✅ JWT |
| **Marketplace** | GET /api/marketplace/listings | List all | ✅ JWT |
| | POST /api/marketplace/listings | Create new | ✅ JWT |
| | PATCH /api/marketplace/listings/{id} | Match buyer / complete | ✅ JWT |
| **Channel** | GET /api/channel/posts | List posts | ✅ JWT |
| | POST /api/channel/posts | Create post | ✅ JWT |
| | PATCH /api/channel/posts/{id} | Edit / pin | ✅ JWT |
| | DELETE /api/channel/posts/{id} | Delete post | ✅ JWT |
| **Community** | GET /api/communities | List communities | ✅ JWT |
| | GET /api/communities/{id}/members | Member list | ✅ JWT |
| **Broadcast** | GET /api/communities | Load community list | ✅ JWT |
| | POST /api/communities/{id}/broadcast | Send to WhatsApp | ✅ JWT |

---

## SCHEMA FIELD DIFFERENCES (mock → real)

| Page | Mock field | Real API field | Note |
|------|-----------|---------------|------|
| Dashboard | `pickup.user` (name string) | `pickup.user_phone` | Add join to User in backend |
| Channel | `post.body` | `post.content` | Rename in UI |
| Channel | `post.published_at` | `post.created_at` | Rename in UI |
| Channel | `post.pinned` | `post.is_pinned` | Rename in UI |
| Channel | `post.likes` | (not in schema) | Remove from UI |
| Marketplace | `listing.weight_kg` | `listing.weight` | Rename in UI |
| Marketplace | `listing.grade` | (not in schema) | Remove, grades are on files |
| Marketplace | `listing.origin` | (not in schema) | Remove |
| Marketplace | `listing.thumb` | (not in schema) | Generate color from waste_type |
| Marketplace | `listing.buyer` (string) | (not in schema yet) | Use `description` field to store buyer name |

---

## TESTING CHECKLIST

After completing all changes, run this test sequence:

```bash
# 1. Backend health
curl http://localhost:8001/health
# → {"status":"ok","version":"2.0.0"}

# 2. Feed (empty initially)
curl http://localhost:8001/api/feed
# → []

# 3. Login
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"08001234567","password":"operatorpass123"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
echo "Token: $TOKEN"

# 4. Simulate WhatsApp booking
curl -X POST http://localhost:8001/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"changes":[{"value":{"messages":[{"from":"628111222333","type":"text","text":{"body":"jemput"}}]}}]}]}'

# 5. Check pickup was created
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/pickups
# → {"items":[{...pickup...}],"total":1,...}

# 6. Check feed has pickup_created event
curl http://localhost:8001/api/feed
# → [{"event_type":"pickup_created","title":"Pickup baru: ..."}]

# 7. Confirm pickup
PICKUP_ID=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/pickups | python3 -c "import json,sys; print(json.load(sys.stdin)['items'][0]['id'])")
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"confirmed"}' \
  http://localhost:8001/api/pickups/$PICKUP_ID

# 8. Check feed has pickup_confirmed event
curl http://localhost:8001/api/feed
# → [{pickup_confirmed},{pickup_created}]

# 9. Create marketplace listing
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"waste_type":"Pakaian Bekas","weight":10.5,"price_estimate":105000}' \
  http://localhost:8001/api/marketplace/listings

# 10. Create channel post
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Post","content":"Ini konten test","category":"info"}' \
  http://localhost:8001/api/channel/posts

# 11. Pin channel post
POST_ID=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/channel/posts | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_pinned":true}' \
  http://localhost:8001/api/channel/posts/$POST_ID

echo "All tests complete. Open Dashboard.html in browser to verify UI."
```

---

## COMMON ISSUES + FIXES

| Issue | Cause | Fix |
|-------|-------|-----|
| CORS error in browser | Backend CORS not set for HTML file origin | Add `file://` or `http://127.0.0.1` to CORS_ORIGINS in .env |
| 401 on all requests | Token not being sent | Check localStorage has `regrow_token` key |
| Community page shows no members | Members join via WhatsApp flow | Add test members via POST /api/communities/{id}/members |
| Feed stays empty | activity_events table not created | Restart backend (create_tables() runs on startup) |
| Channel edit not working | PATCH endpoint didn't exist | Verify new endpoint is registered |

---

## PRODUCTION DEPLOYMENT

When deploying to VPS:

```bash
# 1. Update BASE_URL in api.js
const BASE_URL = 'https://api.yourapp.com';

# 2. Update APP_URL in handlers.py  
APP_URL = "https://yourapp.com"

# 3. Add CORS origins for your domain
CORS_ORIGINS=https://yourapp.com,https://www.yourapp.com

# 4. Serve HTML files as static files from nginx
# nginx.conf:
# location /app/ {
#   root /var/www/regrow;
#   try_files $uri $uri/ /app/login.html;
# }

# 5. Restart all services
docker compose down && docker compose up -d
```
