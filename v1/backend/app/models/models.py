import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey,
    Enum as SAEnum, Float, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    operator = "operator"
    admin = "admin"


class PickupStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    grading = "grading"
    graded = "graded"
    completed = "completed"
    cancelled = "cancelled"


class Grade(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# ─── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    role = Column(SAEnum(UserRole), default=UserRole.user, nullable=False)
    password_hash = Column(String(255), nullable=True)  # for operators/admins
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    pickups = relationship("Pickup", back_populates="user", lazy="select")


# ─── Pickup ───────────────────────────────────────────────────────────────────

class Pickup(Base):
    __tablename__ = "pickups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    location = Column(Text, nullable=False)
    waste_type = Column(String(100), nullable=False)
    estimated_weight = Column(Float, nullable=True)
    status = Column(SAEnum(PickupStatus), default=PickupStatus.pending, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="pickups")
    files = relationship("File", back_populates="pickup", lazy="select")


# ─── File ─────────────────────────────────────────────────────────────────────

class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pickup_id = Column(UUID(as_uuid=True), ForeignKey("pickups.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)   # MinIO object key
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    pickup = relationship("Pickup", back_populates="files")
    grade = relationship("GradeResult", back_populates="file", uselist=False, lazy="select")


# ─── Grade Result ─────────────────────────────────────────────────────────────

class GradeResult(Base):
    __tablename__ = "grades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, unique=True, index=True)
    grade = Column(SAEnum(Grade), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)
    estimated_kg = Column(Float, nullable=True)
    graded_by = Column(String(50), default="gemini", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    file = relationship("File", back_populates="grade")
