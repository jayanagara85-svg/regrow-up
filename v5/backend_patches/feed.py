"""
GET /api/feed — Activity event stream for the operator dashboard.
No auth required (internal operator dashboard tool).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.core.database import get_db
from app.models.activity_model import ActivityEvent

router = APIRouter(prefix="/api/feed", tags=["feed"])


class ActivityEventOut(BaseModel):
    id: UUID
    event_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ActivityEventOut])
async def get_feed(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns latest activity events, most recent first.
    Used by Dashboard.html to populate the activity sidebar.
    """
    result = await db.execute(
        select(ActivityEvent)
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
