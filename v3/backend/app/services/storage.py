import io
import uuid
from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_client: Minio = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def ensure_bucket_exists():
    """Create the bucket if it doesn't exist yet."""
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info(f"Created MinIO bucket: {bucket}")
        else:
            logger.info(f"MinIO bucket exists: {bucket}")
    except S3Error as e:
        logger.error(f"MinIO bucket setup error: {e}")
        raise


def upload_file(
    file_data: bytes,
    file_name: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload bytes to MinIO.
    Returns the object key (path on MinIO).
    """
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET

    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else "bin"
    object_key = f"uploads/{uuid.uuid4().hex}.{ext}"

    client.put_object(
        bucket_name=bucket,
        object_name=object_key,
        data=io.BytesIO(file_data),
        length=len(file_data),
        content_type=content_type,
    )
    logger.info(f"Uploaded file to MinIO: {object_key}")
    return object_key


def download_file(object_key: str) -> bytes:
    """Download object from MinIO as bytes."""
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET
    response = client.get_object(bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def get_presigned_url(object_key: str, expires_hours: int = 1) -> str:
    """Generate a time-limited presigned URL for direct download."""
    from datetime import timedelta
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET
    url = client.presigned_get_object(
        bucket_name=bucket,
        object_name=object_key,
        expires=timedelta(hours=expires_hours),
    )
    return url
