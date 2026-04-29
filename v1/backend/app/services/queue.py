import redis
from rq import Queue
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_redis_conn: redis.Redis = None
_grading_queue: Queue = None


def get_redis() -> redis.Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = redis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis_conn


def get_grading_queue() -> Queue:
    global _grading_queue
    if _grading_queue is None:
        _grading_queue = Queue(
            "grading_queue",
            connection=get_redis(),
            default_timeout=300,  # 5 minute timeout per job
        )
    return _grading_queue


def enqueue_grading_job(file_id: str) -> str:
    """
    Enqueue a grading job for the given file.
    Returns the RQ job ID.
    """
    from app.workers.classification_worker import grade_file

    queue = get_grading_queue()
    job = queue.enqueue(
        grade_file,
        file_id,
        job_id=f"grade-{file_id}",
        retry=3,
    )
    logger.info(f"Enqueued grading job: {job.id} for file: {file_id}")
    return job.id


def get_job_status(job_id: str) -> dict:
    """Fetch job status from RQ."""
    from rq.job import Job, NoSuchJobError

    try:
        job = Job.fetch(job_id, connection=get_redis())
        return {
            "job_id": job_id,
            "status": job.get_status().value,
            "result": job.result,
            "error": str(job.exc_info) if job.exc_info else None,
        }
    except Exception as e:
        return {
            "job_id": job_id,
            "status": "not_found",
            "result": None,
            "error": str(e),
        }
