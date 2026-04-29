#!/usr/bin/env bash
set -e

# ─── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}✅ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo ""
echo -e "${GREEN}🌱 REGROW — Circular Economy OS${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── Check prerequisites ──────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || err "Docker is required. Install: https://docs.docker.com/get-docker/"
command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1 || err "Docker Compose is required."
log "Prerequisites checked"

# ─── Setup .env ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  log ".env file created from .env.example"
  warn "Edit .env to add your GEMINI_API_KEY and WHATSAPP_* settings"
else
  info ".env already exists — skipping"
fi

# ─── Build images ─────────────────────────────────────────────────────────────
info "Building Docker images..."
docker compose build --quiet
log "Docker images built"

# ─── Start services ───────────────────────────────────────────────────────────
info "Starting services..."
docker compose up -d postgres redis minio
sleep 5  # Wait for DB to be ready

info "Starting backend + worker + frontend..."
docker compose up -d
log "All services started"

# ─── Wait for backend ─────────────────────────────────────────────────────────
info "Waiting for backend API..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8001/health >/dev/null 2>&1; then
    log "Backend API is ready"
    break
  fi
  sleep 2
  if [ "$i" -eq 30 ]; then
    err "Backend did not start in time. Check: docker compose logs backend"
  fi
done

# ─── Create default operator ──────────────────────────────────────────────────
info "Creating default operator account..."
RESPONSE=$(curl -sf -X POST http://localhost:8001/api/auth/register-operator \
  -H "Content-Type: application/json" \
  -d '{"phone": "08001234567", "password": "regrow123"}' 2>&1 || true)

if echo "$RESPONSE" | grep -q "created\|already"; then
  log "Operator account ready"
else
  warn "Operator setup: $RESPONSE"
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 REGROW is running!${NC}"
echo ""
echo -e "  🌐 Dashboard:      ${BLUE}http://localhost:3000${NC}"
echo -e "  🔌 API Docs:       ${BLUE}http://localhost:8001/docs${NC}"
echo -e "  📦 MinIO Console:  ${BLUE}http://localhost:9001${NC}"
echo ""
echo -e "  👤 Operator login:"
echo -e "     Phone:    ${YELLOW}08001234567${NC}"
echo -e "     Password: ${YELLOW}regrow123${NC}"
echo ""
echo -e "  📱 WhatsApp Webhook:"
echo -e "     ${BLUE}http://localhost:8001/api/webhook/whatsapp${NC}"
echo -e "     Verify token: ${YELLOW}regrow-verify-token${NC}"
echo ""
echo -e "  📝 Logs:"
echo -e "     ${BLUE}docker compose logs -f backend${NC}"
echo -e "     ${BLUE}docker compose logs -f worker${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
