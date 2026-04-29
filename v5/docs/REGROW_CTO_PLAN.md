# REGROW v1.2 → PLATFORM
## CTO Execution Plan — 14 Days to Shipping

---

## SYSTEM AUDIT: What's Real, What's Broken

| Component | Status | Problem | Fix |
|-----------|--------|---------|-----|
| FastAPI backend | ✅ Working | — | — |
| PostgreSQL | ✅ Working | — | — |
| Redis / AI grading | ✅ Working | — | — |
| WhatsApp webhook | ✅ Working | — | — |
| `GET /api/pickups` | ✅ Exists | Missing `user_phone` field | Join User table (Day 2) |
| `GET /api/feed` | ❌ Missing | No endpoint, no table | Add activity_model + feed.py (Day 1) |
| `PATCH /api/channel/posts/{id}` | ❌ Missing | Pin/edit broken in UI | Add endpoint in loopchat.py (Day 1) |
| Dashboard.html | ⚠️ Partial | Still has mock data blocks | Apply dashboard_patch.js (Day 4) |
| Marketplace.html | ⚠️ Partial | Mock data, wrong field names | Apply marketplace_patch.js (Day 4) |
| Channel.html | ⚠️ Partial | `post.body` vs `post.content` | Apply channel patch (Day 5) |
| Broadcast.html | ⚠️ Partial | No real community data | Apply broadcast patch (Day 5) |
| feed.html | ❌ Missing | No entry point page | New file delivered (Day 3) |
| js/api.js | ⚠️ Basic | No retry, no loading helpers | Replaced with v1.2 (Day 3) |
| WhatsApp replies | ⚠️ No links | No app deep links | Patch handlers.py (Day 5) |
| login.html | ✅ Provided | Already in patches | Apply as-is |

---

## STAGE 1 — SYSTEM INTEGRATION (Days 1–5)

### Day 1: Feed Infrastructure

```bash
# Copy new files
cp patches/activity_model.py   backend/app/models/activity_model.py
cp patches/activity_service.py backend/app/services/activity_service.py
cp patches/feed.py             backend/app/api/feed.py

# Register in main.py (see v1_2_consolidated_patches.py section 4)
# Restart backend
docker compose restart backend

# Test
curl http://localhost:8001/api/feed
# Expected: []
```

**Also on Day 1:** Add `PATCH /api/channel/posts/{id}` to `loopchat.py`
(full code in `v1_2_consolidated_patches.py` section 7a)

---

### Day 2: Data Completeness

**Add `user_phone` to pickup list:**
- Modify `PickupListOut` schema (section 5)
- Update `list_pickups()` with `joinedload(Pickup.user)` (section 6a)

**Emit feed events:**
- `pickup_created` → in `create_pickup()` (section 6b)
- `pickup_confirmed/completed/cancelled` → in `update_pickup()` (section 6c)
- `listing_created` → in `create_listing()` (section 7b)
- `listing_matched` → in `update_listing()` (section 7c)
- `broadcast_sent` → in `broadcast_message()` (section 7d)
- `grade_completed` → in `classification_worker.py` (section 8)

---

### Day 3: Frontend Foundation

```bash
mkdir -p js
cp patches/js/api.js js/api.js        # use the v1.2 version (improved retry/events)
cp patches/login.html login.html
cp patches/feed.html feed.html        # new feed-first entry point
```

Create first operator:
```bash
curl -X POST http://localhost:8001/api/auth/register-operator \
  -H "Content-Type: application/json" \
  -d '{"phone":"08001234567","password":"operatorpass123"}'
```

---

### Day 4: Dashboard + Marketplace

**Dashboard.html changes:**
1. Add `<script src="js/api.js"></script>` before Babel script tag
2. Remove all `MOCK_PICKUPS`, `MOCK_GRADES`, time helper functions
3. Replace `function Dashboard()` with `dashboard_patch.js` version
4. Add `FeedItem` and `GradeModal` components from patch

**Marketplace.html changes:**
1. Add `<script src="js/api.js"></script>` before Babel script tag
2. Remove `MOCK_LISTINGS`, `MOCK_BUYERS` constants
3. Replace `function Marketplace()` with `marketplace_patch.js` version
4. Fix field names: `weight_kg` → `weight`, remove `grade`/`origin`/`thumb`

---

### Day 5: Channel + Broadcast + WhatsApp Links

**Channel.html:**
- Add api.js script tag
- Fix field names: `post.body` → `post.content`, `post.published_at` → `post.created_at`, `post.pinned` → `post.is_pinned`
- Remove `post.likes`

**Broadcast.html:**
- Add api.js script tag, load real communities

**handlers.py — add deep links:**
- Set `APP_URL` from env
- Add URL to every WhatsApp reply (section 9 in patches)

**End of Week 1 milestone:** Every page shows real data, every action writes to DB, feed shows all events.

---

## STAGE 2 — EXPERIENCE (Days 6–9)

### Feed-First Design
`feed.html` is the new default landing page.
**Change default redirect:** `login.html` redirects to `feed.html` on success (not `Dashboard.html`).

```javascript
// In login.html, change:
window.location.href = 'Dashboard.html';
// To:
window.location.href = 'feed.html';
```

### Actionable Feed Cards
Every feed event includes contextual action buttons:

| Event Type | Primary Action | Secondary |
|-----------|----------------|-----------|
| `pickup_created` | Konfirmasi Pickup | — |
| `pickup_confirmed` | Lihat Detail | Upload Foto |
| `grade_completed` | Lihat Hasil Grade | Buat Listing |
| `listing_created` | Pasangkan Buyer | — |
| `listing_matched` | Lihat Listing | Selesaikan |
| `broadcast_sent` | — | — |

### Loading / Empty / Error States
Every page must handle all three states:
```javascript
// Pattern to add to each page:
if (loading)      return <SkeletonCards />;
if (error)        return <ErrorState message={error} onRetry={reload} />;
if (!data.length) return <EmptyState message="Belum ada data" />;
```

### Optimistic Updates
Use `window.API.optimistic.apply()` for instant UI feedback:
```javascript
// Before awaiting the API call:
const rollback = window.API.optimistic.apply(setPickups, id, { status: 'confirmed' });
try {
  await window.API.pickups.confirm(id);
} catch (e) {
  rollback();
  showToast('Gagal: ' + e.message);
}
```

### Live Feed Polling
`feed.html` polls every 15 seconds automatically. For Dashboard, add:
```javascript
useEffect(() => {
  const stop = window.API.feed.poll(events => setFeed(events), 15_000);
  return stop;
}, []);
```

---

## STAGE 3 — PLATFORM PREPARATION (Days 10–14)

### A. Event Thinking

`activity_events` is your system's heartbeat. Every state change becomes an event. This is the foundation for:
- **Audit trail** — replay everything that happened
- **Notifications** — send WhatsApp when a specific event fires
- **Analytics** — count events by type, date, user

**Current event types:**
```
pickup_created     → user booked via WhatsApp
pickup_confirmed   → operator confirmed
pickup_completed   → pickup done
grade_completed    → AI grading finished (with grade + confidence)
listing_created    → new marketplace listing
listing_matched    → buyer matched
listing_completed  → transaction done
broadcast_sent     → community message sent
```

**Future event types to add:**
```
user_joined_community
payment_received
dispute_raised
operator_assigned
```

---

### B. Logical Service Boundaries

DO NOT split into microservices yet. DO define clear module boundaries:

```
backend/app/
├── api/
│   ├── pickups.py          → Pickup System
│   ├── feed.py             → Feed System  
│   ├── loopchat.py         → Channel + Community + Marketplace
│   └── webhook.py          → WhatsApp integration
│
├── services/
│   ├── activity_service.py → Feed System (event logging)
│   ├── grading_service.py  → Grading System (future: extract from worker)
│   └── notification.py     → Notification System (future: WA + email)
│
├── workers/
│   └── classification_worker.py → Grading System (AI)
│
└── models/
    ├── activity_model.py   → Feed System schema
    └── loopchat_models.py  → All other schemas
```

**Rule:** Each system owns its events and its DB tables. Cross-system communication is read-only (a pickup route reads the User table, but doesn't write to it).

---

### C. API Layer Cleanup

Group endpoints by domain prefix (already done in the backend — verify nginx routes):

```
/api/pickups/*          → Pickup System
/api/marketplace/*      → Marketplace System
/api/channel/*          → Content System
/api/communities/*      → Community System
/api/feed               → Feed System
/api/auth/*             → Auth System
/api/files/*            → File System
/api/webhook/*          → WhatsApp integration
```

Add response envelope standard across all endpoints:
```json
{
  "data": {...},
  "meta": { "page": 1, "total": 47, "limit": 20 },
  "error": null
}
```
*(Not required now — do this in a dedicated cleanup sprint)*

---

### D. Deep Link Strategy

Every WhatsApp message includes a link. URL structure:

```
https://yourapp.com/feed.html              → Main feed (default)
https://yourapp.com/Dashboard.html?pickup={id}  → Specific pickup
https://yourapp.com/Marketplace.html?listing={id} → Specific listing
https://yourapp.com/Channel.html?community={id}   → Community view
```

**Implementation:** Add query param parsing to each page:
```javascript
// In Dashboard.html, inside useEffect:
const params = new URLSearchParams(window.location.search);
const autoOpen = params.get('pickup');
if (autoOpen) {
  // Automatically open the grade modal for this pickup
  setViewingGrade(autoOpen);
}
```

---

## FUTURE-READY ARCHITECTURE NOTES

### How to evolve to AI Service Layer
Today: AI grading runs in-process via Redis worker.
Future path:
1. Extract `classification_worker.py` into its own FastAPI service
2. Expose `POST /grade` endpoint
3. Main backend calls it via HTTP (not Redis)
4. This service can be scaled independently, swapped to different AI providers

**No code change needed now** — the boundary is already clean.

---

### How to evolve to Event-Driven System
Today: `log_event()` is a direct DB write inside the same transaction.
Future path:
1. Replace `log_event()` with `emit_event()` that publishes to Redis Pub/Sub
2. `feed.py` reads from the stream instead of the DB
3. Other consumers (notifications, analytics) subscribe to the same stream
4. The DB insert becomes async via a dedicated consumer

**No code change needed now** — the `activity_service.py` interface is already the right abstraction. Just swap the internals.

---

### How to evolve to Multi-Tenant SaaS (Upshalter direction)
Today: Single operator, single WhatsApp number.
Future path:
1. Add `tenant_id` column to all tables
2. JWT carries `tenant_id` claim
3. All queries filter by `tenant_id`
4. Each tenant gets their own WhatsApp number (Loopchat multi-account)
5. Billing per tenant in a new `subscriptions` table

**Prerequisite:** Auth system must issue tenant-scoped tokens. This is the hardest migration — do it before you have real tenants, not after.

---

## 14-DAY EXECUTION ROADMAP

| Day | Focus | Deliverable | Done? |
|-----|-------|-------------|-------|
| 1 | Backend — Feed infrastructure | `activity_events` table + `GET /api/feed` | ☐ |
| 1 | Backend — Channel PATCH | `PATCH /api/channel/posts/{id}` | ☐ |
| 2 | Backend — Data completeness | `user_phone` in pickups, all feed events emitted | ☐ |
| 3 | Frontend — Foundation | `api.js` v1.2, `login.html`, `feed.html` deployed | ☐ |
| 4 | Frontend — Dashboard + Marketplace | Both pages on real API, no mock data | ☐ |
| 5 | Frontend — Channel + Broadcast + WA links | All pages live, deep links working | ☐ |
| **6** | **Review** | **Full manual test of all flows** | ☐ |
| 7 | UX — Loading/empty/error states | All states implemented on all pages | ☐ |
| 8 | UX — Optimistic updates | Confirm/match updates instant | ☐ |
| 9 | UX — Live feed polling | Feed auto-refreshes every 15s | ☐ |
| **10** | **Review** | **Product walkthrough — feels like a real product** | ☐ |
| 11 | Platform — Event audit | All event types documented, gaps filled | ☐ |
| 12 | Platform — API cleanup | Endpoint grouping, response standard | ☐ |
| 13 | Platform — Deep links | All WA messages have links, links open correct view | ☐ |
| 14 | Deploy | Production deploy, smoke test, DONE | ☐ |

---

## TESTING CHECKLIST (End-to-End)

```bash
# Run from scripts/verify.sh (full script in v1_2_consolidated_patches.py)

1. curl /health                    → {"status":"ok"}
2. curl /api/feed                  → []
3. POST /api/auth/login            → JWT token
4. GET  /api/pickups               → {items:[{user_phone:...}]}
5. POST WhatsApp webhook (jemput)  → pickup created in DB
6. GET  /api/feed                  → [{event_type:"pickup_created"}]
7. PATCH /api/pickups/{id}         → status=confirmed
8. GET  /api/feed                  → [confirmed, created]
9. POST /api/marketplace/listings  → listing created
10. GET /api/feed                   → [listing_created, confirmed, created]
11. PATCH /api/channel/posts/{id}   → is_pinned=true (new endpoint)
12. Open feed.html in browser       → shows real events, actions work
```

---

## KNOWN RISKS

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CORS error when opening HTML from disk | High | High | Add `file://` + `http://127.0.0.1` to CORS_ORIGINS |
| activity_events table not created | Medium | High | Restart backend after adding import |
| JWT missing from localStorage | Medium | High | Test login flow first, check browser storage |
| `joinedload` causes N+1 on large datasets | Low | Medium | Add pagination (already there) + DB index on `user_id` |
| Feed polling hammers DB | Low | Medium | 15s interval is fine; add Redis cache if >1000 events/day |
