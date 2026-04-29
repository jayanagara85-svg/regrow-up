from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.database import create_tables
from app.services.storage import ensure_bucket_exists

from app.api import auth, pickups, files, webhook, users

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("regrow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🌱 Starting Regrow API...")

    # Create DB tables (idempotent)
    await create_tables()
    logger.info("✅ Database tables ready")

    # Ensure MinIO bucket exists
    try:
        ensure_bucket_exists()
        logger.info("✅ MinIO bucket ready")
    except Exception as e:
        logger.warning(f"⚠️  MinIO not available: {e}")

    yield
    logger.info("🛑 Shutting down Regrow API")


app = FastAPI(
    title="Regrow API",
    description="Circular Economy OS — Waste Textile + ESG",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(pickups.router)
app.include_router(files.router)
app.include_router(webhook.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "regrow-api", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "service": "Regrow Circular Economy OS",
        "docs": "/docs",
        "health": "/health",
    }
