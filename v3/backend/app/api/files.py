from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.models import File, Pickup, PickupStatus
from app.models.schemas import FileUploadResponse, JobStatus
from app.services.storage import upload_file, get_presigned_url
from app.services.queue import enqueue_grading_job, get_job_status
import uuid
import logging

router = APIRouter(prefix="/api/files", tags=["files"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_MB = 20


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_waste_photo(
    pickup_id: str,
    file: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a waste photo for a pickup.
    - Validates file type and size
    - Stores in MinIO
    - Saves metadata to PostgreSQL
    - Enqueues AI grading job
    """
    # ── Validate pickup ───────────────────────────────────────────────────────
    try:
        pickup_uuid = uuid.UUID(pickup_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pickup_id")

    result = await db.execute(select(Pickup).where(Pickup.id == pickup_uuid))
    pickup = result.scalar_one_or_none()
    if not pickup:
        raise HTTPException(status_code=404, detail="Pickup not found")

    # ── Validate file ─────────────────────────────────────────────────────────
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {ALLOWED_TYPES}",
        )

    file_data = await file.read()
    size_mb = len(file_data) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_SIZE_MB} MB)")

    # ── Upload to MinIO ───────────────────────────────────────────────────────
    object_key = upload_file(
        file_data=file_data,
        file_name=file.filename or "upload.jpg",
        content_type=content_type,
    )

    # ── Save to DB ────────────────────────────────────────────────────────────
    file_record = File(
        pickup_id=pickup_uuid,
        file_path=object_key,
        file_name=file.filename,
        mime_type=content_type,
        size_bytes=len(file_data),
    )
    db.add(file_record)
    await db.flush()

    # Update pickup status to grading
    pickup.status = PickupStatus.grading
    await db.flush()

    # ── Enqueue grading job ───────────────────────────────────────────────────
    job_id = enqueue_grading_job(str(file_record.id))
    logger.info(f"Enqueued grading job {job_id} for file {file_record.id}")

    return FileUploadResponse(
        file_id=str(file_record.id),
        job_id=job_id,
        message="File uploaded successfully. AI grading is in progress.",
    )


@router.get("/job/{job_id}", response_model=JobStatus)
async def get_grading_job_status(job_id: str):
    """Poll the status of a grading job."""
    return get_job_status(job_id)


@router.get("/{file_id}/url")
async def get_file_url(file_id: str, db: AsyncSession = Depends(get_db)):
    """Get a presigned URL to view/download the file."""
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file_id")

    result = await db.execute(select(File).where(File.id == fid))
    file_record = result.scalar_one_or_none()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    url = get_presigned_url(file_record.file_path)
    return {"url": url, "expires_in": "1 hour"}
