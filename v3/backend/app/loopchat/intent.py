"""
INTENT DETECTION ENGINE
Maps raw WhatsApp text → typed intent string.

Supports:
  pickup      → jemput, pickup, ambil, mau jemput
  status      → status, cek, sudah, gimana, hasil
  marketplace → jual, jual sampah, listing, dagang, harga
  community   → komunitas, komuniti, group, kelompok
  channel     → info, berita, news, pengumuman, update
  menu        → menu, bantuan, help, hai, halo
  cancel      → batal, cancel, stop, selesai
"""
import re
from typing import Literal

Intent = Literal[
    "pickup",
    "status",
    "marketplace",
    "community",
    "channel",
    "menu",
    "cancel",
    "unknown",
]

# ─── Keyword map ──────────────────────────────────────────────────────────────
_INTENT_MAP: list[tuple[list[str], Intent]] = [
    # cancel always wins first
    (["batal", "cancel", "stop", "selesai", "keluar", "exit"], "cancel"),

    # pickup
    (["jemput", "pickup", "ambil", "mau jemput", "saya mau jemput",
      "request pickup", "book", "antar"], "pickup"),

    # status
    (["status", "cek status", "cek", "udah", "sudah", "gimana", "kapan",
      "hasil", "berapa", "progress"], "status"),

    # marketplace
    (["jual", "jual sampah", "listing", "dagang", "harga", "beli",
      "pasar", "marketplace", "tawaran"], "marketplace"),

    # community
    (["komunitas", "komuniti", "group", "kelompok", "bank sampah",
      "teman", "komuniti", "area", "wilayah"], "community"),

    # channel / feed
    (["info", "berita", "news", "pengumuman", "update", "artikel",
      "kabar", "terbaru", "siaran"], "channel"),

    # menu / help
    (["menu", "bantuan", "help", "halo", "hai", "hello", "hi",
      "start", "mulai", "apa", "bagaimana"], "menu"),
]


def detect_intent(text: str) -> Intent:
    """
    Detect intent from a raw message string.
    Normalizes text and checks against keyword list.
    """
    normalized = text.lower().strip()
    # remove punctuation for matching
    cleaned = re.sub(r"[^\w\s]", "", normalized)

    for keywords, intent in _INTENT_MAP:
        for kw in keywords:
            if kw in cleaned or cleaned.startswith(kw):
                return intent

    return "unknown"


def parse_marketplace_message(text: str) -> dict:
    """
    Parse a marketplace listing message.

    Examples:
      "jual plastik 2kg"
      "jual baju bekas 5 kg 30000"
      "jual kain perca 1.5kg harga 10000"

    Returns:
      {"waste_type": str, "weight": float|None, "price": float|None, "raw": str}
    """
    lower = text.lower()

    # Remove common prefixes
    for prefix in ["jual ", "mau jual ", "saya jual ", "listing "]:
        if lower.startswith(prefix):
            lower = lower[len(prefix):]
            break

    # Extract weight (e.g. "2kg", "1.5 kg", "3 kilo")
    weight = None
    weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)", lower)
    if weight_match:
        weight = float(weight_match.group(1))
        lower = lower[:weight_match.start()] + lower[weight_match.end():]

    # Extract price (e.g. "30000", "30rb", "30k")
    price = None
    price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:rb|ribu|k|000)?", lower)
    if price_match:
        raw_price = price_match.group(0).strip()
        numeric = float(price_match.group(1))
        if "rb" in raw_price or "ribu" in raw_price:
            price = numeric * 1000
        elif raw_price.endswith("k") and not raw_price.endswith("kg"):
            price = numeric * 1000
        elif numeric > 100:
            price = numeric
        lower = lower[:price_match.start()] + lower[price_match.end():]

    # Whatever's left is the waste type
    waste_type = lower.strip().strip("-").strip()
    if not waste_type:
        waste_type = text.strip()

    return {
        "waste_type": waste_type or "tidak diketahui",
        "weight": weight,
        "price": price,
        "raw": text,
    }
