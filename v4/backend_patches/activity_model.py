"""
ACTIVITY FEED MODEL
Lightweight event log — one row per significant system event.
Drives the live feed in Dashboard and gives operators context on what's happening.

Events recorded:
  pickup_created   → user booked via WhatsApp
  pickup_confirmed → operator confirmed
  grade_completed  → AI grading finished
  listing_created  → new marketplace listing
  listing_matched  → buyer matched to listing
  listing_completed → transaction completed
  broadcast_sent   → community broadcast fired
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type   = Column(String(50),  nullable=False, index=True)
    entity_type  = Column(String(50),  nullable=True)   # pickup | listing | community
    entity_id    = Column(String(100), nullable=True)   # UUID as string (flexible)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title        = Column(String(200), nullable=False)
    subtitle     = Column(Text,        nullable=True)
    created_at   = Column(DateTime,    default=datetime.utcnow, nullable=False, index=True)
