"""
LOOPCHAT ROUTER
────────────────────────────────────────────────────────────────────────────
Central dispatcher for all WhatsApp messages in the Regrow system.

Architecture:
  WhatsApp message
      → detect_intent()
      → check active user state
      → route to correct handler
      → return plain text response

Handlers are in loopchat/handlers.py
State machine is in loopchat/state.py
Intent detection is in loopchat/intent.py
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.loopchat.intent import detect_intent, Intent
from app.loopchat.state import get_user_state, clear_user_state, set_user_state
from app.loopchat import handlers
import logging

logger = logging.getLogger("loopchat.router")


async def route_message(
    user: User,
    message: str,
    db: AsyncSession,
) -> str:
    """
    Main entry point called by the webhook.

    1. Get current user state from Redis.
    2. If inside an active flow → continue that flow.
    3. Otherwise → detect fresh intent → dispatch to handler.

    Returns: plain text string to send back via WhatsApp.
    """
    text = message.strip()

    # ── Always handle cancel first ────────────────────────────────────────────
    intent = detect_intent(text)
    if intent == "cancel":
        clear_user_state(user.phone)
        return "✅ Dibatalkan.\n\n" + handlers.fallback_menu()

    # ── Check active conversation state ───────────────────────────────────────
    state = get_user_state(user.phone)
    active_state = state.get("state", "idle")

    logger.info(
        f"[Router] phone={user.phone} state={active_state} intent={intent} msg={text[:40]}"
    )

    # ── BOOKING FLOW (multi-step) ─────────────────────────────────────────────
    if active_state == "booking":
        return await handlers.handle_pickup_step(user, text, db)

    # ── MARKETPLACE FLOW (multi-step) ─────────────────────────────────────────
    if active_state == "marketplace":
        return await handlers.handle_marketplace_step(user, text, db)

    # ── COMMUNITY FLOW (multi-step) ───────────────────────────────────────────
    if active_state == "community":
        step = state.get("data", {}).get("step")
        if step == "awaiting_join":
            return await handlers.handle_community_join(user, text, db)

    # ── FRESH INTENT ROUTING ──────────────────────────────────────────────────

    if intent == "pickup":
        return await handlers.handle_pickup_start(user, db)

    if intent == "status":
        return await handlers.handle_status(user, db)

    if intent == "marketplace":
        return await handlers.handle_marketplace_start(user, text, db)

    if intent == "community":
        return await handlers.handle_community(user, db)

    if intent == "channel":
        # Check if user wants a specific post: "info 2"
        match = re.search(r"\d+", text)
        if match:
            post_number = int(match.group())
            return await handlers.handle_channel_detail(post_number, db)
        return await handlers.handle_channel(user, db)

    if intent == "menu":
        return handlers.fallback_menu()

    # ── Sub-intents not caught by main intent ─────────────────────────────────

    lower = text.lower()

    # "lihat listing" or "listing saya"
    if "lihat listing" in lower or "listing saya" in lower:
        return await handlers.handle_list_my_listings(user, db)

    # "broadcast [pesan]" — community admin action
    if lower.startswith("broadcast "):
        msg_to_broadcast = text[10:].strip()
        if msg_to_broadcast:
            return await _handle_broadcast(user, msg_to_broadcast, db)

    # ── Unknown ───────────────────────────────────────────────────────────────
    return (
        "Maaf, saya kurang mengerti 😅\n\n"
        + handlers.fallback_menu()
    )


async def _handle_broadcast(user: User, message: str, db: AsyncSession) -> str:
    """Admin broadcasts a message to their community."""
    from sqlalchemy import select
    from app.models.loopchat_models import UserCommunity, Community

    result = await db.execute(
        select(UserCommunity).where(
            UserCommunity.user_id == user.id,
            UserCommunity.is_admin.is_(True),
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        return "❌ Hanya admin komunitas yang bisa broadcast."

    comm_result = await db.execute(
        select(Community).where(Community.id == membership.community_id)
    )
    community = comm_result.scalar_one_or_none()
    if not community:
        return "Komunitas tidak ditemukan."

    # Format broadcast
    broadcast_text = (
        f"📣 *Pesan dari {community.name}*\n\n"
        f"{message}"
    )

    count = await handlers.broadcast_to_community(
        str(membership.community_id), broadcast_text, db
    )

    return f"✅ Pesan terkirim ke *{count}* anggota komunitas *{community.name}*."
