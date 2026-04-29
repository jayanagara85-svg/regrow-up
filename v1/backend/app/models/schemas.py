from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.models import PickupStatus, UserRole, Grade


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


# ─── User ─────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: UUID
    phone: str
    name: Optional[str]
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Pickup ───────────────────────────────────────────────────────────────────

class PickupCreate(BaseModel):
    user_id: str
    location: str = Field(..., min_length=5)
    waste_type: str = Field(..., min_length=2)
    estimated_weight: Optional[float] = None
    notes: Optional[str] = None


class PickupUpdate(BaseModel):
    status: Optional[PickupStatus] = None
    notes: Optional[str] = None


class GradeOut(BaseModel):
    id: UUID
    grade: Grade
    confidence: float
    reasoning: Optional[str]
    estimated_kg: Optional[float]
    graded_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class FileOut(BaseModel):
    id: UUID
    pickup_id: UUID
    file_path: str
    file_name: Optional[str]
    mime_type: Optional[str]
    created_at: datetime
    grade: Optional[GradeOut] = None

    class Config:
        from_attributes = True


class PickupOut(BaseModel):
    id: UUID
    user_id: UUID
    location: str
    waste_type: str
    estimated_weight: Optional[float]
    status: PickupStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    files: List[FileOut] = []

    class Config:
        from_attributes = True


class PickupListOut(BaseModel):
    id: UUID
    user_id: UUID
    location: str
    waste_type: str
    status: PickupStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ─── File ─────────────────────────────────────────────────────────────────────

class FileUploadResponse(BaseModel):
    file_id: str
    job_id: str
    message: str


# ─── Job Status ───────────────────────────────────────────────────────────────

class JobStatus(BaseModel):
    job_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


# ─── Generic ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class PaginatedPickups(BaseModel):
    items: List[PickupListOut]
    total: int
    page: int
    limit: int
