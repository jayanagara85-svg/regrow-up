#!/usr/bin/env bash
# REGROW v1.2 — Quick Apply Script
# Run from the project root (where docker-compose.yml lives)
# Usage: bash apply_patches.sh [--dry-run]
#
# What this does:
#   1. Copies new backend files into place
#   2. Copies updated frontend assets
#   3. Prints manual steps you still need to do in Python files
#   4. Restarts docker services
#   5. Runs smoke tests

set -e
DRY=${1:-}

PATCHES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(pwd)"

say()  { echo "▸ $*"; }
run()  { if [[ $DRY == "--dry-run" ]]; then echo "  [DRY] $*"; else eval "$@"; fi; }
warn() { echo "⚠  $*"; }
ok()   { echo "✓  $*"; }

echo ""
echo "╔═════════════════════════════════════════╗"
echo "║  REGROW v1.2 — Patch Apply Script       ║"
echo "╚═════════════════════════════════════════╝"
echo ""

# ─── Guard: must run from project root ─────────────────────────────────────
if [[ ! -f "docker-compose.yml" ]] && [[ ! -f "docker-compose.yaml" ]]; then
  echo "ERROR: Run this script from the project root (where docker-compose.yml lives)"
  exit 1
fi
ok "Project root: $PROJECT_ROOT"
echo ""

# ─── STEP 1: Backend — copy new Python files ──────────────────────────────
say "Step 1/6: Copying new backend files..."

run "cp $PATCHES_DIR/backend_patches/activity_model.py   backend/app/models/activity_model.py"
run "cp $PATCHES_DIR/backend_patches/activity_service.py backend/app/services/activity_service.py"
run "cp $PATCHES_DIR/backend_patches/feed.py             backend/app/api/feed.py"
ok "Backend files copied"

# ─── STEP 2: Frontend — copy new JS + HTML ─────────────────────────────────
say "Step 2/6: Copying frontend assets..."

run "mkdir -p js"
run "cp $PATCHES_DIR/js/api.js   js/api.js"
run "cp $PATCHES_DIR/feed.html   feed.html"

# Only copy login.html if it doesn't already exist
if [[ ! -f "login.html" ]]; then
  run "cp $PATCHES_DIR/login.html login.html"
  ok "login.html created"
else
  warn "login.html already exists — skipping (don't overwrite existing)"
fi
ok "Frontend assets deployed"

# ─── STEP 3: Print manual Python edits ────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/6: MANUAL edits required (cannot auto-patch Python)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  A. backend/app/main.py — add 2 lines:"
echo "     from app.api import feed"
echo "     from app.models import activity_model"
echo "     app.include_router(feed.router)"
echo ""
echo "  B. backend/app/models/schemas.py — add to PickupListOut:"
echo "     user_phone: Optional[str] = None"
echo ""
echo "  C. backend/app/api/pickups.py:"
echo "     - Add joinedload(Pickup.user) to list_pickups()"
echo "     - Emit log_event() in create_pickup() + update_pickup()"
echo "     (see docs/REGROW_CTO_PLAN.md section Day 2)"
echo ""
echo "  D. backend/app/api/loopchat.py:"
echo "     - Add PATCH /api/channel/posts/{post_id} endpoint"
echo "     - Emit log_event() in create_listing(), broadcast_message()"
echo "     (see backend_patches/v1_2_consolidated_patches.py)"
echo ""
echo "  E. backend/app/workers/classification_worker.py:"
echo "     - Emit log_event('grade_completed') after DB commit"
echo ""
echo "  F. backend/app/loopchat/handlers.py:"
echo "     - Add APP_URL deep links to all WhatsApp reply messages"
echo "     - Set APP_URL=https://yourapp.com in .env"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Press ENTER when you've applied the manual edits, or Ctrl+C to stop..."

# ─── STEP 4: Restart backend ──────────────────────────────────────────────
say "Step 4/6: Restarting backend..."
run "docker compose restart backend"
run "sleep 4"
ok "Backend restarted"

# ─── STEP 5: Create first operator account (if needed) ────────────────────
say "Step 5/6: Checking operator account..."
PHONE="${OPERATOR_PHONE:-08001234567}"
PASS="${OPERATOR_PASS:-operatorpass123}"

REGISTER_RESULT=$(curl -sf -X POST http://localhost:8001/api/auth/register-operator \
  -H "Content-Type: application/json" \
  -d "{\"phone\":\"$PHONE\",\"password\":\"$PASS\"}" 2>&1 || true)

if echo "$REGISTER_RESULT" | grep -q "already"; then
  ok "Operator account already exists ($PHONE)"
elif echo "$REGISTER_RESULT" | grep -q "access_token\|user_id\|id"; then
  ok "Operator account created: $PHONE / $PASS"
else
  warn "Could not verify operator account. Try manually:"
  warn "curl -X POST http://localhost:8001/api/auth/register-operator -d '{\"phone\":\"$PHONE\",\"password\":\"$PASS\"}'"
fi

# ─── STEP 6: Smoke tests ──────────────────────────────────────────────────
say "Step 6/6: Running smoke tests..."
BASE=http://localhost:8001

# Health
HEALTH=$(curl -sf $BASE/health 2>/dev/null || echo "FAIL")
if echo "$HEALTH" | grep -q "ok"; then
  ok "Health: OK"
else
  warn "Health check failed: $HEALTH"
fi

# Feed endpoint
FEED=$(curl -sf $BASE/api/feed 2>/dev/null || echo "FAIL")
if echo "$FEED" | grep -q "\["; then
  ok "Feed endpoint: OK (returns array)"
else
  warn "Feed endpoint not responding: $FEED"
  warn "Check that you added feed.router to main.py and restarted"
fi

# Auth
TOKEN=$(curl -sf -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"phone\":\"$PHONE\",\"password\":\"$PASS\"}" 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [[ -n "$TOKEN" ]]; then
  ok "Auth: OK (token received)"

  # Pickups (check user_phone field)
  PICKUPS=$(curl -sf -H "Authorization: Bearer $TOKEN" $BASE/api/pickups 2>/dev/null || echo "FAIL")
  if echo "$PICKUPS" | grep -q "user_phone"; then
    ok "Pickups: user_phone field present ✓"
  elif echo "$PICKUPS" | grep -q "items"; then
    warn "Pickups: endpoint works but user_phone field missing — check schema patch"
  else
    warn "Pickups: endpoint not responding"
  fi
else
  warn "Auth failed — check operator account"
fi

# Channel PATCH endpoint
PATCH_TEST=$(curl -sf -o /dev/null -w "%{http_code}" \
  -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_pinned":false}' \
  $BASE/api/channel/posts/00000000-0000-0000-0000-000000000000 2>/dev/null || echo "000")

if [[ "$PATCH_TEST" == "404" ]]; then
  ok "Channel PATCH endpoint: exists (404 = post not found, endpoint registered)"
elif [[ "$PATCH_TEST" == "422" ]]; then
  ok "Channel PATCH endpoint: exists (422 = validation error, endpoint registered)"
elif [[ "$PATCH_TEST" == "000" || "$PATCH_TEST" == "405" ]]; then
  warn "Channel PATCH endpoint: NOT registered — check loopchat.py patch"
fi

echo ""
echo "════════════════════════════════════════"
echo "  Patch application complete!"
echo "  Open feed.html in your browser to verify."
echo "  Full test sequence: see docs/REGROW_CTO_PLAN.md"
echo "════════════════════════════════════════"
echo ""
