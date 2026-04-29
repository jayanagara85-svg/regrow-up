import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v20.0"


async def send_whatsapp_message(phone_number: str, message: str) -> bool:
    """
    Send a WhatsApp text message via Meta Graph API.
    Returns True if sent successfully.
    """
    if settings.WHATSAPP_API_TOKEN == "not-set":
        logger.warning(f"[WhatsApp MOCK] To {phone_number}: {message}")
        return True

    url = f"{GRAPH_URL}/{settings.WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            logger.info(f"WhatsApp message sent to {phone_number}")
            return True
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return False


def parse_intent(message_text: str) -> dict:
    """
    Parse the intent from an incoming WhatsApp message.
    Returns: {"intent": str, "data": dict}
    """
    text = message_text.lower().strip()

    # ── Intent: book pickup ──────────────────────────────────────────────────
    if any(kw in text for kw in ["jemput", "mau jemput", "pickup", "ambil", "booking"]):
        return {"intent": "book_pickup", "data": {"raw": message_text}}

    # ── Intent: check status ─────────────────────────────────────────────────
    if any(kw in text for kw in ["cek status", "status", "sudah berapa", "gimana", "kapan"]):
        return {"intent": "check_status", "data": {"raw": message_text}}

    # ── Intent: upload photo ─────────────────────────────────────────────────
    if any(kw in text for kw in ["upload", "foto", "kirim gambar", "photo"]):
        return {"intent": "upload_photo", "data": {"raw": message_text}}

    # ── Intent: get help ─────────────────────────────────────────────────────
    if any(kw in text for kw in ["help", "bantuan", "menu", "halo", "hai", "hello", "hi"]):
        return {"intent": "help", "data": {}}

    return {"intent": "unknown", "data": {"raw": message_text}}


HELP_MESSAGE = """🌱 *Regrow* — Layanan Jemput Sampah Tekstil

Ketik salah satu:
• *jemput* — Booking jemput sampah
• *status* — Cek status pickup Anda
• *upload* — Kirim foto sampah

Atau balas dengan pertanyaan Anda 😊"""
