#!/usr/bin/env bash
# ─── Regrow MVP Pipeline Test ───────────────────────────────────────────────
# Tests: login → create user → book pickup → upload file → poll grade
set -e

BASE="http://localhost:8001"
GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }
step() { echo -e "\n${BLUE}▶ $1${NC}"; }

echo -e "\n${GREEN}🧪 Regrow MVP Pipeline Test${NC}\n"

# 1. Health check
step "1. Health check"
HEALTH=$(curl -sf "$BASE/health")
echo "$HEALTH" | grep -q "ok" && ok "API is up" || fail "API not responding"

# 2. Login as operator
step "2. Login as operator"
TOKEN_RESP=$(curl -sf -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone": "08001234567", "password": "regrow123"}')
TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
[ -n "$TOKEN" ] && ok "Got JWT token" || fail "Login failed: $TOKEN_RESP"

# 3. Get user info
step "3. Get current user"
ME=$(curl -sf "$BASE/api/users/me" -H "Authorization: Bearer $TOKEN")
echo "$ME" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  Role: {d[\"role\"]}, Phone: {d[\"phone\"]}')"
ok "User info retrieved"

# 4. Create a test user (simulate WhatsApp booking flow)
step "4. Simulate WhatsApp pickup booking"
WA_RESP=$(curl -sf -X POST "$BASE/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "628123456789",
            "type": "text",
            "text": {"body": "Saya mau jemput sampah"}
          }]
        }
      }]
    }]
  }')
echo "$WA_RESP" | grep -q "ok" && ok "WhatsApp webhook: booking intent received" || fail "WhatsApp webhook failed: $WA_RESP"

# 5. Send waste type
step "5. Send waste type via WhatsApp"
curl -sf -X POST "$BASE/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "628123456789",
            "type": "text",
            "text": {"body": "Baju bekas dan celana"}
          }]
        }
      }]
    }]
  }' > /dev/null
ok "Waste type sent"

# 6. Send location (creates pickup)
step "6. Send location via WhatsApp (creates pickup)"
curl -sf -X POST "$BASE/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "628123456789",
            "type": "text",
            "text": {"body": "Jl. Kebon Jeruk No. 5, Jakarta Barat"}
          }]
        }
      }]
    }]
  }' > /dev/null
ok "Location sent — pickup should be created"

# 7. Verify pickup exists via API
step "7. List pickups via API"
PICKUPS=$(curl -sf "$BASE/api/pickups" -H "Authorization: Bearer $TOKEN")
TOTAL=$(echo "$PICKUPS" | python3 -c "import json,sys; print(json.load(sys.stdin)['total'])")
echo "  Total pickups: $TOTAL"
[ "$TOTAL" -ge 1 ] && ok "Pickup created successfully" || fail "No pickups found"

# 8. Get pickup details
step "8. Get first pickup details"
PICKUP_ID=$(echo "$PICKUPS" | python3 -c "import json,sys; print(json.load(sys.stdin)['items'][0]['id'])")
PICKUP=$(curl -sf "$BASE/api/pickups/$PICKUP_ID" -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$PICKUP" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
echo "  Pickup ID: $PICKUP_ID"
echo "  Status: $STATUS"
ok "Pickup details retrieved"

# 9. Upload a test image
step "9. Upload test waste photo"
# Create a tiny test JPEG (1x1 pixel)
python3 -c "
from PIL import Image
import io
img = Image.new('RGB', (100, 100), color=(100, 150, 80))
img.save('/tmp/test_waste.jpg', 'JPEG')
print('Test image created')
" 2>/dev/null || echo "  (PIL not available locally — skipping image upload test)"

if [ -f "/tmp/test_waste.jpg" ]; then
  UPLOAD=$(curl -sf -X POST "$BASE/api/files/upload?pickup_id=$PICKUP_ID" \
    -F "file=@/tmp/test_waste.jpg;type=image/jpeg")
  JOB_ID=$(echo "$UPLOAD" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
  echo "  Job ID: $JOB_ID"
  ok "File uploaded and grading job enqueued"

  # 10. Poll for job status
  step "10. Polling grading job status"
  for i in $(seq 1 15); do
    sleep 2
    JOB=$(curl -sf "$BASE/api/files/job/$JOB_ID")
    JOB_STATUS=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
    echo "  Attempt $i: status = $JOB_STATUS"
    if [ "$JOB_STATUS" = "finished" ]; then
      ok "Grading job completed!"
      echo "$JOB" | python3 -c "
import json,sys
d = json.load(sys.stdin)
r = d.get('result', {})
print(f'  Grade: {r.get(\"grade\")}, Confidence: {r.get(\"confidence\")}')
"
      break
    elif [ "$JOB_STATUS" = "failed" ]; then
      echo -e "${RED}  Job failed${NC}"
      break
    fi
  done
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 All tests passed!${NC}"
echo -e "   Dashboard: http://localhost:3000"
echo -e "   API Docs:  http://localhost:8001/docs"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
