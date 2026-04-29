"""
ACTIVITY FEED SERVICE
Call log_event() from any API route or worker to emit a feed event.
Events show up in Dashboard's activity feed via GET /api/feed.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.activity_model import ActivityEvent
import logging

logger = logging.getLogger("feed")


async def log_event(
    db: AsyncSession,
    event_type: str,
    title: str,
    subtitle: str = None,
    entity_type: str = None,
    entity_id: str = None,
    user_id=None,
):
    """
    Insert one activity event. Does NOT commit — caller must commit.

    Usage:
        await log_event(db, "pickup_created", "Pickup baru dari +62812...", user_id=user.id)
        await db.commit()  # caller commits

    Or inside a route that already does commit:
        await log_event(db, ...)
        # get_db() auto-commits on context exit
    """
    try:
        event = ActivityEvent(
            event_type  = event_type,
            entity_type = entity_type,
            entity_id   = str(entity_id) if entity_id else None,
            user_id     = user_id,
            title       = title[:200],
            subtitle    = subtitle[:500] if subtitle else None,
        )
        db.add(event)
        logger.debug(f"[Feed] {event_type}: {title}")
    except Exception as e:
        logger.error(f"[Feed] Failed to log event: {e}")
        # Never raise — feed logging should never break the main flow
