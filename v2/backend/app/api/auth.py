from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.models.models import User, UserRole
from app.models.schemas import LoginRequest, TokenResponse, MessageResponse
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.value, "phone": user.phone})
    return TokenResponse(access_token=token, user_id=str(user.id), role=user.role.value)


@router.post("/register-operator", response_model=MessageResponse)
async def register_operator(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Quick endpoint to create an operator/admin account for dashboard login."""
    result = await db.execute(select(User).where(User.phone == body.phone))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = User(
        phone=body.phone,
        name=f"Operator {body.phone[-4:]}",
        role=UserRole.operator,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    return MessageResponse(message=f"Operator created: {body.phone}")
