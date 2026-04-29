"""
WHATSAPP WEBHOOK — Updated to use Loopchat Router
All message logic is now in: app/loopchat/router.py
This file is ONLY responsible for:
  1. Webhook verification (Meta)
  2. Extracting message from payload
  3. Getting/creating the User record
  4. Calling route_message()
  5. Sending the response back
"""
from fastapi import APIRouter, Request, Response, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.models.models import User
from app.services.whatsapp import send_whatsapp_message
from app.loopchat.router import route_message
import logging

router = APIRouter(prefix="/api/webhook", tags=["whatsapp"])
logger = logging.getLogger("webhook")


# ─── Webhook Verification (GET) ───────────────────────────────────────────────

@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


# ─── Incoming Message (POST) ──────────────────────────────────────────────────

@router.post("/whatsapp")
async def receive_whatsapp_message(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid json"}

    try:
        entry  = body["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return {"status": "no_message"}

        msg      = entry["messages"][0]
        phone    = msg["from"]
        msg_type = msg.get("type", "text")

        if msg_type == "text":
            text = msg["text"]["body"]
        elif msg_type == "image":
            text = "upload foto"
        elif msg_type == "interactive":
            text = (
                msg.get("interactive", {}).get("button_reply", {}).get("title")
                or msg.get("interactive", {}).get("list_reply", {}).get("title")
                or ""
            )
        else:
            return {"status": "unsupported_type", "type": msg_type}

    except (KeyError, IndexError, TypeError) as e:
        logger.debug(f"Could not parse payload: {e}")
        return {"status": "ignored", "reason": "parse_error"}

    logger.info(f"WhatsApp from {phone}: {text[:60]!r}")

    result = await db.execute(select(User).where(User.phone == phone))
    user   = result.scalar_one_or_none()

    if not user:
        user = User(phone=phone, name=f"User {phone[-4:]}")
        db.add(user)
        await db.flush()
        await db.refresh(user)

    try:
        response_text = await route_message(user=user, message=text, db=db)
    except Exception as e:
        logger.error(f"Router error for {phone}: {e}", exc_info=True)
        response_text = (
            "Maaf, terjadi kesalahan sistem. Coba lagi."
        )

    await send_whatsapp_message(phone, response_text)
    return {"status": "ok"}
