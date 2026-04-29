from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Pickup, User, UserRole, PickupStatus
from app.models.schemas import (
    PickupCreate, PickupUpdate, PickupOut,
    PickupListOut, PaginatedPickups, MessageResponse
)
import uuid
import logging

router = APIRouter(prefix="/api/pickups", tags=["pickups"])
logger = logging.getLogger(__name__)


@router.post("", response_model=PickupOut, status_code=201)
async def create_pickup(body: PickupCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new pickup booking.
    Called by WhatsApp webhook (no auth) or directly.
    """
    # Ensure the user exists; auto-create from phone if not
    try:
        user_uuid = uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    pickup = Pickup(
        user_id=user_uuid,
        location=body.location,
        waste_type=body.waste_type,
        estimated_weight=body.estimated_weight,
        notes=body.notes,
        status=PickupStatus.pending,
    )
    db.add(pickup)
    await db.flush()
    await db.refresh(pickup, ["files"])
    return pickup


@router.get("", response_model=PaginatedPickups)
async def list_pickups(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[PickupStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all pickups (operator/admin only)."""
    q = select(Pickup)
    if status:
        q = q.where(Pickup.status == status)
    q = q.order_by(Pickup.created_at.desc())

    # count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar()

    # paginate
    q = q.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    return PaginatedPickups(items=rows, total=total, page=page, limit=limit)


@router.get("/{pickup_id}", response_model=PickupOut)
async def get_pickup(
    pickup_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        uid = uuid.UUID(pickup_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pickup_id")

    result = await db.execute(
        select(Pickup)
        .options(selectinload(Pickup.files).selectinload(lambda f: f.grade))
        .where(Pickup.id == uid)
    )
    pickup = result.scalar_one_or_none()
    if not pickup:
        raise HTTPException(status_code=404, detail="Pickup not found")
    return pickup


@router.patch("/{pickup_id}", response_model=PickupOut)
async def update_pickup(
    pickup_id: str,
    body: PickupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update pickup status (operator only)."""
    try:
        uid = uuid.UUID(pickup_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pickup_id")

    result = await db.execute(select(Pickup).where(Pickup.id == uid))
    pickup = result.scalar_one_or_none()
    if not pickup:
        raise HTTPException(status_code=404, detail="Pickup not found")

    if body.status:
        pickup.status = body.status
    if body.notes is not None:
        pickup.notes = body.notes

    await db.flush()
    await db.refresh(pickup, ["files"])
    return pickup
