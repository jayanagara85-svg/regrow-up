from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.database import create_tables
from app.services.storage import ensure_bucket_exists

# ── Existing routes ────────────────────────────────────────────────────────────
from app.api import auth, pickups, files, users
# ── Updated webhook (now uses Loopchat Router) ────────────────────────────────
from app.api import webhook
# ── New Loopchat routes ───────────────────────────────────────────────────────
from app.api import loopchat

# ── Import ALL models so SQLAlchemy creates tables ────────────────────────────
from app.models import models          # noqa: F401 — users, pickups, files, grades
from app.models import loopchat_models # noqa: F401 — marketplace, community, channel

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("regrow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🌱 Starting Regrow + LoopChat...")
    await create_tables()
    logger.info("✅ All DB tables ready (Regrow + LoopChat)")
    try:
        ensure_bucket_exists()
        logger.info("✅ MinIO bucket ready")
    except Exception as e:
        logger.warning(f"⚠️  MinIO: {e}")
    yield
    logger.info("🛑 Shutting down")


app = FastAPI(
    title="Regrow + LoopChat API",
    description="Circular Economy OS — WhatsApp · Marketplace · Community · Channel",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Existing ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(pickups.router)
app.include_router(files.router)
app.include_router(webhook.router)

# ── LoopChat extension ────────────────────────────────────────────────────────
app.include_router(loopchat.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "features": ["pickup", "marketplace", "community", "channel"]}

@app.get("/")
async def root():
    return {"service": "Regrow + LoopChat", "docs": "/docs"}
