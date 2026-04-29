from fastapi import APIRouter, Request, Response, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.config import settings
from app.models.models import User, Pickup, PickupStatus
from app.services.whatsapp import send_whatsapp_message, parse_intent, HELP_MESSAGE
import logging
import uuid

router = APIRouter(prefix="/api/webhook", tags=["whatsapp"])
logger = logging.getLogger(__name__)

# In-memory conversation state (use Redis in production)
_conversation_state: dict = {}


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta webhook verification."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/whatsapp")
async def receive_whatsapp_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive and process incoming WhatsApp messages.
    Implements a simple conversation state machine.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    # Extract message from Meta webhook payload
    try:
        entry = body["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return {"status": "no_message"}

        msg = entry["messages"][0]
        phone = msg["from"]
        msg_type = msg.get("type", "text")

        # Handle text messages
        if msg_type == "text":
            text = msg["text"]["body"]
        elif msg_type == "image":
            # User sent a photo directly
            text = "upload foto"
        else:
            text = ""

    except (KeyError, IndexError):
        logger.debug("Could not extract message from payload")
        return {"status": "ignored"}

    logger.info(f"WhatsApp msg from {phone}: {text[:50]}")

    # ── Get or create user ────────────────────────────────────────────────────
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        user = User(phone=phone, name=f"User {phone[-4:]}")
        db.add(user)
        await db.flush()
        await db.refresh(user)

    user_id = str(user.id)
    state = _conversation_state.get(phone, {})

    # ── Route based on conversation state ─────────────────────────────────────
    if state.get("step") == "awaiting_location":
        await _handle_location_input(phone, user_id, text, state, db)
        return {"status": "ok"}

    if state.get("step") == "awaiting_waste_type":
        await _handle_waste_type_input(phone, user_id, text, state, db)
        return {"status": "ok"}

    # ── Fresh intent detection ────────────────────────────────────────────────
    intent = parse_intent(text)
    logger.info(f"Intent: {intent['intent']} for {phone}")

    if intent["intent"] == "book_pickup":
        _conversation_state[phone] = {"step": "awaiting_waste_type", "user_id": user_id}
        await send_whatsapp_message(
            phone,
            "✅ Siap! Apa jenis sampah yang akan dijemput?\n\n"
            "Contoh: *Baju bekas*, *Kain perca*, *Sepatu*, dll."
        )

    elif intent["intent"] == "check_status":
        await _handle_check_status(phone, user_id, db)

    elif intent["intent"] == "upload_photo":
        await send_whatsapp_message(
            phone,
            "📸 Silakan kirim foto sampah Anda langsung di sini.\n"
            "Pastikan foto jelas agar AI bisa menilai kualitasnya.",
        )

    elif intent["intent"] == "help":
        await send_whatsapp_message(phone, HELP_MESSAGE)

    else:
        await send_whatsapp_message(
            phone,
            "Maaf, saya kurang mengerti 😅\n"
            "Ketik *menu* untuk melihat pilihan yang tersedia.",
        )

    return {"status": "ok"}


async def _handle_waste_type_input(
    phone: str, user_id: str, text: str, state: dict, db: AsyncSession
):
    """User has provided waste type — ask for location next."""
    _conversation_state[phone] = {
        "step": "awaiting_location",
        "user_id": user_id,
        "waste_type": text.strip(),
    }
    await send_whatsapp_message(
        phone,
        f"👍 Sampah: *{text.strip()}*\n\n"
        "Sekarang kirimkan *alamat lengkap* untuk penjemputan:",
    )


async def _handle_location_input(
    phone: str, user_id: str, text: str, state: dict, db: AsyncSession
):
    """User has provided location — create the pickup."""
    waste_type = state.get("waste_type", "Tidak ditentukan")
    location = text.strip()

    # Create pickup record
    pickup = Pickup(
        user_id=uuid.UUID(user_id),
        location=location,
        waste_type=waste_type,
        status=PickupStatus.pending,
    )
    db.add(pickup)
    await db.flush()
    await db.refresh(pickup)

    # Clear conversation state
    _conversation_state.pop(phone, None)

    pickup_id = str(pickup.id)[:8].upper()
    await send_whatsapp_message(
        phone,
        f"🎉 Booking berhasil!\n\n"
        f"📋 ID Pickup: *{pickup_id}*\n"
        f"♻️ Jenis: *{waste_type}*\n"
        f"📍 Lokasi: *{location}*\n\n"
        f"Tim kami akan segera menghubungi Anda. "
        f"Ketik *status* untuk cek perkembangan pickup.",
    )


async def _handle_check_status(phone: str, user_id: str, db: AsyncSession):
    """Show the most recent pickup status to the user."""
    result = await db.execute(
        select(Pickup)
        .where(Pickup.user_id == uuid.UUID(user_id))
        .order_by(Pickup.created_at.desc())
        .limit(1)
    )
    pickup = result.scalar_one_or_none()

    if not pickup:
        await send_whatsapp_message(
            phone,
            "Belum ada booking pickup. Ketik *jemput* untuk mulai.",
        )
        return

    status_emoji = {
        "pending": "⏳",
        "confirmed": "✅",
        "grading": "🔍",
        "graded": "🎯",
        "completed": "✨",
        "cancelled": "❌",
    }
    emoji = status_emoji.get(pickup.status.value, "📦")
    pid = str(pickup.id)[:8].upper()

    await send_whatsapp_message(
        phone,
        f"📋 Status Pickup *{pid}*\n\n"
        f"{emoji} Status: *{pickup.status.value.upper()}*\n"
        f"♻️ Jenis: {pickup.waste_type}\n"
        f"📍 Lokasi: {pickup.location}\n"
        f"📅 Tanggal: {pickup.created_at.strftime('%d/%m/%Y %H:%M')}",
    )
