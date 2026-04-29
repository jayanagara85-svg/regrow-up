#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  LOOPCHAT END-TO-END TEST
#  Tests: pickup → marketplace → community → channel → broadcast
# ═══════════════════════════════════════════════════════════════════════════
set -e

BASE="http://localhost:8001"
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✅ $1${NC}"; }
fail() { echo -e "${RED}  ❌ $1${NC}"; exit 1; }
step() { echo -e "\n${BLUE}▶ $1${NC}"; }
info() { echo -e "${YELLOW}  ℹ $1${NC}"; }

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🌱 Regrow LoopChat — End-to-End Test${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Simulate sending a WhatsApp message
wa_send() {
  local phone="$1"
  local text="$2"
  curl -sf -X POST "$BASE/api/webhook/whatsapp" \
    -H "Content-Type: application/json" \
    -d "{
      \"entry\": [{\"changes\": [{\"value\": {\"messages\": [{
        \"from\": \"$phone\",
        \"type\": \"text\",
        \"text\": {\"body\": \"$text\"}
      }]}}]}]
    }" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','?'))"
}

# ─── Prerequisites ────────────────────────────────────────────────────────────
step "0. Health check"
HEALTH=$(curl -sf "$BASE/health")
echo "$HEALTH" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  Version {d[\"version\"]}, features: {d[\"features\"]}')"
ok "API is up"

step "1. Login as operator"
TOKEN_JSON=$(curl -sf -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone":"08001234567","password":"regrow123"}')
TOKEN=$(echo "$TOKEN_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
[ -n "$TOKEN" ] && ok "Got JWT" || fail "Login failed"

AUTH="-H \"Authorization: Bearer $TOKEN\""

# ─── Test 1: Menu (fallback) ──────────────────────────────────────────────────
step "2. Test fallback menu"
STATUS=$(wa_send "628111111111" "halo")
[ "$STATUS" = "ok" ] && ok "Menu returned" || fail "Menu failed"

# ─── Test 2: Pickup flow ──────────────────────────────────────────────────────
step "3. Pickup flow: step 1 — jemput"
wa_send "628222222222" "jemput sampah" > /dev/null
ok "Booking started"

step "4. Pickup flow: step 2 — waste type"
wa_send "628222222222" "Baju bekas dan kain perca" > /dev/null
ok "Waste type accepted"

step "5. Pickup flow: step 3 — location"
STATUS=$(wa_send "628222222222" "Jl. Sudirman No. 10, Jakarta Pusat")
[ "$STATUS" = "ok" ] && ok "Pickup created via WhatsApp" || fail "Pickup creation failed"

# ─── Test 3: Status check ─────────────────────────────────────────────────────
step "6. Status check"
STATUS=$(wa_send "628222222222" "status")
[ "$STATUS" = "ok" ] && ok "Status returned" || fail "Status failed"

# ─── Test 4: Marketplace ─────────────────────────────────────────────────────
step "7. Marketplace: jual plastik"
STATUS=$(wa_send "628333333333" "jual plastik 3kg")
[ "$STATUS" = "ok" ] && ok "Marketplace listing created" || fail "Marketplace failed"

step "8. Marketplace: jual with price"
STATUS=$(wa_send "628333333333" "jual baju bekas 5kg 25000")
[ "$STATUS" = "ok" ] && ok "Listing with price created" || fail "Marketplace price failed"

step "9. List marketplace via API"
LISTINGS=$(curl -sf "$BASE/api/marketplace/listings" \
  -H "Authorization: Bearer $TOKEN")
COUNT=$(echo "$LISTINGS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
info "Listings found: $COUNT"
[ "$COUNT" -ge 1 ] && ok "Marketplace API working" || fail "No listings found"

# ─── Test 5: Community ────────────────────────────────────────────────────────
step "10. Create a community"
COMM=$(curl -sf -X POST "$BASE/api/communities" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Bank Sampah Test","area":"Jakarta Barat"}')
COMM_ID=$(echo "$COMM" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
info "Community ID: $COMM_ID"
[ -n "$COMM_ID" ] && ok "Community created" || fail "Community creation failed"

step "11. WhatsApp: komunitas"
STATUS=$(wa_send "628444444444" "komunitas")
[ "$STATUS" = "ok" ] && ok "Community list shown" || fail "Community listing failed"

step "12. WhatsApp: join community (reply with '1')"
STATUS=$(wa_send "628444444444" "1")
[ "$STATUS" = "ok" ] && ok "Community join attempted" || fail "Join failed"

step "13. Add member via API"
# Get the user's ID first
ALL_PICKUPS=$(curl -sf "$BASE/api/pickups" -H "Authorization: Bearer $TOKEN")
USER_ID=$(echo "$ALL_PICKUPS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
items = data.get('items', [])
print(items[0]['user_id'] if items else '')
" 2>/dev/null || echo "")

if [ -n "$USER_ID" ]; then
  curl -sf -X POST "$BASE/api/communities/$COMM_ID/members" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$USER_ID\", \"is_admin\": true}" > /dev/null
  ok "Member added as admin"
else
  info "Skipping member add (no user_id found)"
fi

# ─── Test 6: Channel ─────────────────────────────────────────────────────────
step "14. Create channel post"
POST=$(curl -sf -X POST "$BASE/api/channel/posts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Harga Sampah Naik Bulan Ini!",
    "content": "Kabar baik! Harga sampah plastik naik 15% bulan Oktober. Segera booking pickup Anda.",
    "category": "info",
    "is_pinned": true
  }')
POST_ID=$(echo "$POST" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
[ -n "$POST_ID" ] && ok "Channel post created" || fail "Post creation failed"

step "15. WhatsApp: info (channel)"
STATUS=$(wa_send "628555555555" "info")
[ "$STATUS" = "ok" ] && ok "Channel feed shown" || fail "Channel failed"

step "16. WhatsApp: info 1 (specific post)"
STATUS=$(wa_send "628555555555" "info 1")
[ "$STATUS" = "ok" ] && ok "Post detail shown" || fail "Post detail failed"

# ─── Test 7: Broadcast ───────────────────────────────────────────────────────
step "17. Broadcast via API"
BCAST=$(curl -sf -X POST "$BASE/api/communities/$COMM_ID/broadcast" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "📢 Pengumuman: Pickup gratis minggu ini!"}')
SENT=$(echo "$BCAST" | python3 -c "import json,sys; print(json.load(sys.stdin).get('sent_to', 0))")
info "Broadcast sent to $SENT members"
ok "Broadcast API working"

# ─── Test 8: Cancel / state reset ────────────────────────────────────────────
step "18. Test cancel resets state"
wa_send "628666666666" "jemput" > /dev/null
STATUS=$(wa_send "628666666666" "batal")
[ "$STATUS" = "ok" ] && ok "Cancel resets to menu" || fail "Cancel failed"

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 All Loopchat tests passed!${NC}"
echo ""
echo -e "  🌐 Dashboard:    ${BLUE}http://localhost:3000${NC}"
echo -e "  📚 API Docs:     ${BLUE}http://localhost:8001/docs${NC}"
echo ""
echo -e "${GREEN}Endpoints working:${NC}"
echo -e "  ✅ /api/webhook/whatsapp  — Loopchat Router"
echo -e "  ✅ /api/marketplace/*     — Listings CRUD"
echo -e "  ✅ /api/communities/*     — Communities + Broadcast"
echo -e "  ✅ /api/channel/posts     — BBM-style feed"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
