"""
LOOPCHAT EXTENSION MODELS
Extends existing Regrow models with:
  - MarketplaceListing
  - Community / UserCommunity
  - ChannelPost
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey,
    Enum as SAEnum, Float, Text, Boolean, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


# ─── Marketplace ──────────────────────────────────────────────────────────────

class ListingStatus(str, enum.Enum):
    open      = "open"
    matched   = "matched"
    completed = "completed"
    cancelled = "cancelled"


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    waste_type     = Column(String(100), nullable=False)
    weight         = Column(Float, nullable=True)          # kg
    price_estimate = Column(Float, nullable=True)          # IDR
    description    = Column(Text, nullable=True)
    status         = Column(SAEnum(ListingStatus), default=ListingStatus.open, nullable=False)
    buyer_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    seller = relationship("User", foreign_keys=[user_id])
    buyer  = relationship("User", foreign_keys=[buyer_id])


# ─── Community ────────────────────────────────────────────────────────────────

class Community(Base):
    __tablename__ = "communities"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(150), nullable=False)
    area       = Column(String(150), nullable=True)   # city / district
    description= Column(Text, nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    members = relationship("UserCommunity", back_populates="community")


class UserCommunity(Base):
    __tablename__ = "user_communities"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    community_id = Column(UUID(as_uuid=True), ForeignKey("communities.id"), nullable=False, index=True)
    joined_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_admin     = Column(Boolean, default=False)

    community = relationship("Community", back_populates="members")
    user      = relationship("User")


# ─── Channel (BBM-style feed) ─────────────────────────────────────────────────

class ChannelPost(Base):
    __tablename__ = "channel_posts"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title      = Column(String(200), nullable=False)
    content    = Column(Text, nullable=False)
    category   = Column(String(50), default="info")   # info | promo | announcement
    author_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_pinned  = Column(Boolean, default=False)
    views      = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    author = relationship("User")
