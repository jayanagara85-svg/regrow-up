"""
LOOPCHAT HANDLERS
Each handler receives (user, session, db) and returns a plain text response
that will be sent back via WhatsApp.

Handlers are pure async functions — no FastAPI dependency injection here.
They receive an AsyncSession from the router.
"""
from __future__ import annotations

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.models import User, Pickup, PickupStatus
from app.models.loopchat_models import (
    MarketplaceListing, ListingStatus,
    Community, UserCommunity, ChannelPost,
)
from app.loopchat.intent import parse_marketplace_message
from app.loopchat.state import (
    set_user_state, get_user_state, clear_user_state, update_state_data
)
import logging

logger = logging.getLogger("loopchat.handlers")


# ═══════════════════════════════════════════════════════════════════════════════
#  FALLBACK MENU
# ═══════════════════════════════════════════════════════════════════════════════

MAIN_MENU = """🌱 *Regrow LoopChat*

Ketik salah satu:
♻️  *jemput* — Booking jemput sampah
📋  *status* — Cek status pickup
🏪  *jual* — Jual sampah ke marketplace
👥  *komunitas* — Lihat komunitas saya
📢  *info* — Berita & pengumuman

Ketik *batal* kapan saja untuk kembali ke menu."""


def fallback_menu() -> str:
    return MAIN_MENU


# ═══════════════════════════════════════════════════════════════════════════════
#  PICKUP HANDLER  (delegates to existing Regrow pickup flow)
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_pickup_start(user: User, db: AsyncSession) -> str:
    """Begin the pickup booking conversation."""
    set_user_state(user.phone, "booking", {"step": "awaiting_waste_type"})
    return (
        "✅ *Booking Jemput Sampah*\n\n"
        "Apa jenis sampah yang akan dijemput?\n"
        "Contoh: _baju bekas_, _kain perca_, _sepatu_, _celana_"
    )


async def handle_pickup_step(user: User, text: str, db: AsyncSession) -> str:
    """Handle subsequent steps inside pickup booking flow."""
    state_data = get_user_state(user.phone)
    step = state_data["data"].get("step")

    if step == "awaiting_waste_type":
        update_state_data(user.phone, {"waste_type": text.strip(), "step": "awaiting_location"})
        return (
            f"👍 Sampah: *{text.strip()}*\n\n"
            "Sekarang kirimkan *alamat lengkap* penjemputan:"
        )

    elif step == "awaiting_location":
        waste_type = state_data["data"].get("waste_type", "?")
        location   = text.strip()

        # Create pickup directly via ORM (reuse existing model)
        pickup = Pickup(
            user_id    = user.id,
            location   = location,
            waste_type = waste_type,
            status     = PickupStatus.pending,
        )
        db.add(pickup)
        await db.flush()
        await db.refresh(pickup)

        clear_user_state(user.phone)
        pid = str(pickup.id)[:8].upper()

        return (
            f"🎉 *Booking berhasil!*\n\n"
            f"📋 ID Pickup: *{pid}*\n"
            f"♻️ Jenis: *{waste_type}*\n"
            f"📍 Lokasi: *{location}*\n\n"
            f"Tim kami akan segera konfirmasi.\n"
            f"Ketik *status* untuk pantau perkembangan."
        )

    return fallback_menu()


# ═══════════════════════════════════════════════════════════════════════════════
#  STATUS HANDLER  (reads from existing Pickup table)
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_status(user: User, db: AsyncSession) -> str:
    """Show the latest pickup status for this user."""
    result = await db.execute(
        select(Pickup)
        .where(Pickup.user_id == user.id)
        .order_by(Pickup.created_at.desc())
        .limit(3)
    )
    pickups = result.scalars().all()

    if not pickups:
        return "Belum ada booking pickup.\nKetik *jemput* untuk mulai."

    emoji_map = {
        "pending":   "⏳", "confirmed": "✅",
        "grading":   "🔍", "graded":    "🎯",
        "completed": "✨", "cancelled": "❌",
    }

    lines = ["📋 *Status Pickup Terbaru:*\n"]
    for p in pickups:
        pid   = str(p.id)[:8].upper()
        emoji = emoji_map.get(p.status.value, "📦")
        lines.append(
            f"{emoji} *{pid}* — {p.waste_type}\n"
            f"   Status: _{p.status.value}_\n"
            f"   Lokasi: {p.location[:40]}\n"
        )

    return "\n".join(lines).strip()


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKETPLACE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_marketplace_start(user: User, text: str, db: AsyncSession) -> str:
    """
    Route marketplace interactions.
    If text contains listing info → create immediately.
    Otherwise → prompt for details.
    """
    parsed = parse_marketplace_message(text)

    # If we got at least a waste_type → create listing directly
    if parsed["waste_type"] and parsed["waste_type"] != "tidak diketahui":
        return await _create_listing(user, parsed, db)

    # Otherwise start guided flow
    set_user_state(user.phone, "marketplace", {"step": "awaiting_listing"})
    return (
        "🏪 *Marketplace Sampah*\n\n"
        "Kirimkan detail sampah yang ingin dijual.\n"
        "Format: *[jenis] [berat]kg [harga opsional]*\n\n"
        "Contoh:\n"
        "• _plastik 2kg_\n"
        "• _baju bekas 5kg 30000_\n"
        "• _kain perca 1.5kg_"
    )


async def handle_marketplace_step(user: User, text: str, db: AsyncSession) -> str:
    """Handle text input during marketplace flow."""
    parsed = parse_marketplace_message(text)
    return await _create_listing(user, parsed, db)


async def _create_listing(user: User, parsed: dict, db: AsyncSession) -> str:
    listing = MarketplaceListing(
        user_id        = user.id,
        waste_type     = parsed["waste_type"],
        weight         = parsed.get("weight"),
        price_estimate = parsed.get("price"),
        status         = ListingStatus.open,
    )
    db.add(listing)
    await db.flush()
    await db.refresh(listing)

    clear_user_state(user.phone)

    weight_str = f"{listing.weight} kg" if listing.weight else "berat tidak diisi"
    price_str  = f"Rp {int(listing.price_estimate):,}" if listing.price_estimate else "harga terbuka"
    lid        = str(listing.id)[:8].upper()

    return (
        f"✅ *Listing Berhasil!*\n\n"
        f"🏷️ ID: *{lid}*\n"
        f"♻️ Jenis: *{listing.waste_type}*\n"
        f"⚖️ Berat: *{weight_str}*\n"
        f"💰 Harga: *{price_str}*\n\n"
        f"Pembeli akan segera dihubungi.\n"
        f"Ketik *lihat listing* untuk lihat semua."
    )


async def handle_list_my_listings(user: User, db: AsyncSession) -> str:
    """Show the user's own marketplace listings."""
    result = await db.execute(
        select(MarketplaceListing)
        .where(MarketplaceListing.user_id == user.id)
        .order_by(MarketplaceListing.created_at.desc())
        .limit(5)
    )
    listings = result.scalars().all()

    if not listings:
        return "Belum ada listing.\nKetik *jual [jenis] [berat]kg* untuk mulai."

    status_emoji = {"open": "🟢", "matched": "🟡", "completed": "✅", "cancelled": "❌"}
    lines = ["🏪 *Listing Anda:*\n"]
    for l in listings:
        lid    = str(l.id)[:8].upper()
        emoji  = status_emoji.get(l.status.value, "📦")
        weight = f"{l.weight}kg" if l.weight else "?"
        lines.append(f"{emoji} *{lid}* — {l.waste_type} {weight}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMUNITY HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_community(user: User, db: AsyncSession) -> str:
    """Show the user's community info."""
    result = await db.execute(
        select(UserCommunity)
        .where(UserCommunity.user_id == user.id)
        .limit(1)
    )
    membership = result.scalar_one_or_none()

    if not membership:
        # Show available communities to join
        comms_result = await db.execute(
            select(Community).where(Community.is_active.is_(True)).limit(5)
        )
        communities = comms_result.scalars().all()

        if not communities:
            return (
                "👥 *Komunitas*\n\n"
                "Belum ada komunitas tersedia di area Anda.\n"
                "Hubungi admin untuk bergabung."
            )

        lines = ["👥 *Pilih Komunitas:*\n"]
        for i, c in enumerate(communities, 1):
            lines.append(f"{i}. *{c.name}* — {c.area or 'Area tidak diset'}")
        lines.append("\nBalas dengan nomor komunitas yang ingin diikuti.")

        set_user_state(user.phone, "community", {
            "step": "awaiting_join",
            "options": [str(c.id) for c in communities],
        })
        return "\n".join(lines)

    # Get community details
    comm_result = await db.execute(
        select(Community).where(Community.id == membership.community_id)
    )
    community = comm_result.scalar_one_or_none()

    if not community:
        return "Komunitas Anda tidak ditemukan. Hubungi admin."

    # Member count
    count_result = await db.execute(
        select(func.count()).select_from(UserCommunity)
        .where(UserCommunity.community_id == community.id)
    )
    member_count = count_result.scalar()
    role = "👑 Admin" if membership.is_admin else "👤 Member"

    return (
        f"👥 *Komunitas Anda*\n\n"
        f"🏘️ Nama: *{community.name}*\n"
        f"📍 Area: {community.area or 'Belum diset'}\n"
        f"👤 Anggota: *{member_count} orang*\n"
        f"🎖️ Peran: {role}\n\n"
        f"Ketik *broadcast [pesan]* untuk kirim pesan ke semua anggota."
    )


async def handle_community_join(user: User, choice_text: str, db: AsyncSession) -> str:
    """User chose a community to join."""
    state = get_user_state(user.phone)
    options = state["data"].get("options", [])

    try:
        idx = int(choice_text.strip()) - 1
        if idx < 0 or idx >= len(options):
            return "Pilihan tidak valid. Balas dengan angka yang tertera."
        community_id = uuid.UUID(options[idx])
    except (ValueError, IndexError):
        return "Pilihan tidak valid. Ketik angka yang tersedia."

    # Check existing membership
    existing = await db.execute(
        select(UserCommunity).where(
            UserCommunity.user_id == user.id,
            UserCommunity.community_id == community_id,
        )
    )
    if existing.scalar_one_or_none():
        clear_user_state(user.phone)
        return "Anda sudah terdaftar di komunitas ini."

    membership = UserCommunity(user_id=user.id, community_id=community_id)
    db.add(membership)
    await db.flush()

    comm = await db.execute(select(Community).where(Community.id == community_id))
    community = comm.scalar_one()

    clear_user_state(user.phone)
    return (
        f"🎉 Selamat bergabung di *{community.name}*!\n\n"
        f"Ketik *komunitas* untuk lihat info komunitas Anda."
    )


async def broadcast_to_community(community_id: str, message: str, db: AsyncSession) -> int:
    """
    Broadcast a message to all users in a community.
    Returns number of users messaged.
    """
    from app.services.whatsapp import send_whatsapp_message

    result = await db.execute(
        select(UserCommunity).where(
            UserCommunity.community_id == uuid.UUID(community_id)
        )
    )
    memberships = result.scalars().all()

    count = 0
    for m in memberships:
        user_result = await db.execute(
            select(User).where(User.id == m.user_id)
        )
        member = user_result.scalar_one_or_none()
        if member:
            await send_whatsapp_message(member.phone, message)
            count += 1

    return count


# ═══════════════════════════════════════════════════════════════════════════════
#  CHANNEL (BBM-STYLE FEED) HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_channel(user: User, db: AsyncSession) -> str:
    """Show the latest 3 channel posts."""
    result = await db.execute(
        select(ChannelPost)
        .order_by(ChannelPost.is_pinned.desc(), ChannelPost.created_at.desc())
        .limit(3)
    )
    posts = result.scalars().all()

    if not posts:
        return (
            "📢 *Kanal Info Regrow*\n\n"
            "Belum ada postingan.\n"
            "Cek kembali nanti untuk info terbaru."
        )

    category_emoji = {
        "info":         "ℹ️",
        "promo":        "🎁",
        "announcement": "📣",
    }

    lines = ["📢 *Kanal Info Terbaru:*\n"]
    for post in posts:
        emoji = category_emoji.get(post.category, "📝")
        pinned = "📌 " if post.is_pinned else ""
        date   = post.created_at.strftime("%d/%m")
        lines.append(
            f"{pinned}{emoji} *{post.title}*\n"
            f"_{date}_ — {post.content[:120]}{'...' if len(post.content) > 120 else ''}\n"
        )

    lines.append("Ketik *info [nomor]* untuk baca selengkapnya.")
    return "\n".join(lines)


async def handle_channel_detail(post_number: int, db: AsyncSession) -> str:
    """Show full content of a specific channel post."""
    result = await db.execute(
        select(ChannelPost)
        .order_by(ChannelPost.is_pinned.desc(), ChannelPost.created_at.desc())
        .offset(post_number - 1)
        .limit(1)
    )
    post = result.scalar_one_or_none()

    if not post:
        return "Postingan tidak ditemukan."

    # Increment view count
    post.views = (post.views or 0) + 1
    await db.flush()

    return (
        f"📢 *{post.title}*\n"
        f"_{post.created_at.strftime('%d %B %Y')}_\n\n"
        f"{post.content}"
    )
