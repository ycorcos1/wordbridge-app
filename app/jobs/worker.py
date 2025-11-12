from __future__ import annotations

import datetime
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import boto3
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# In production, environment variables should be set directly
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    # Try loading from current directory
    load_dotenv(override=True)

# CRITICAL: Reset any existing database connection before importing models
# This ensures we pick up the correct DATABASE_URL from environment
from models import reset_engine
reset_engine()

from config.settings import get_settings
from models import init_db
from app.repositories import recommendations_repo, student_profiles_repo, uploads_repo
from app.services import content_filter, pii, recommendations, text_extraction
from app.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIResponseError,
)
from app.services.recommendations import RecommendationParseError
from app.services.text_extraction import UnsupportedFileTypeError
from app.utils.retry import execute_with_retry

from .queue import ack_job, dequeue_upload_job

logger = logging.getLogger(__name__)


class PermanentJobError(Exception):
    """Raised when a job cannot succeed even with retries (e.g., invalid input)."""


@dataclass(slots=True)
class JobResult:
    upload_id: int
    success: bool
    error: Optional[str] = None


def _make_boto_client(service: str):
    settings = get_settings()
    kwargs: dict[str, str] = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client(service, **kwargs)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Return (bucket, key) tuple for s3:// URI."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Not an S3 URI: {uri}")
    path = uri[len("s3://") :]
    parts = path.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parts[0], parts[1]


def _load_upload_content(
    upload: dict[str, object],
    *,
    s3_client=None,
) -> bytes:
    file_path = str(upload.get("file_path", ""))

    if file_path.startswith("s3://"):
        bucket, key = _parse_s3_uri(file_path)
        client = s3_client or _make_boto_client("s3")
        buffer = io.BytesIO()
        client.download_fileobj(bucket, key, buffer)
        return buffer.getvalue()

    with open(file_path, "rb") as handle:
        return handle.read()


def _required_word_count(student_profile: dict[str, object]) -> int:
    settings = get_settings()
    last_analyzed = student_profile.get("last_analyzed_at")
    if last_analyzed:
        return settings.MIN_UPDATE_ANALYSIS_WORDS
    return settings.MIN_INITIAL_ANALYSIS_WORDS


def _baseline_vocabulary_level(grade_level: int | str | None) -> int:
    mapping = {6: 450, 7: 550, 8: 650}
    try:
        grade_value = int(grade_level) if grade_level is not None else None
    except (TypeError, ValueError):
        grade_value = None
    return mapping.get(grade_value, 500)


def _compute_vocabulary_level(
    profile: dict[str, object],
    recommendations_payload: list[dict[str, object]],
) -> int:
    base_level = _baseline_vocabulary_level(profile.get("grade_level"))

    scores: list[int] = []
    for entry in recommendations_payload:
        if entry is None:
            continue
        raw_score = entry.get("difficulty_score")
        try:
            score_value = int(raw_score)
        except (TypeError, ValueError):
            continue
        score_value = max(1, min(10, score_value))
        scores.append(score_value)

    if scores:
        avg_score = sum(scores) / len(scores)
    else:
        avg_score = 5

    proposed = int(round(base_level + (avg_score - 5) * 40))
    proposed = max(200, min(1000, proposed))

    previous_level_raw = profile.get("vocabulary_level")
    try:
        previous_level = int(previous_level_raw)
    except (TypeError, ValueError):
        previous_level = None

    last_analyzed = profile.get("last_analyzed_at")
    if previous_level is None or not last_analyzed:
        return proposed

    blended = previous_level * 0.7 + proposed * 0.3
    return int(round(blended))


def _process_attempt(
    upload_id: int,
    *,
    s3_client=None,
) -> None:
    # Ensure we have a fresh database connection
    from models import reset_engine, get_connection
    reset_engine()
    
    upload = uploads_repo.fetch_upload(upload_id)
    if not upload:
        # Log more details for debugging
        logger.error(f"Upload {upload_id} not found. Checking database...")
        conn = get_connection()
        cur = conn.cursor()
        try:
            from models import _backend
            is_sqlite = _backend == "sqlite" if _backend else "sqlite3" in str(type(conn))
            if is_sqlite:
                cur.execute("SELECT id, status FROM uploads WHERE id = ?", (upload_id,))
            else:
                cur.execute("SELECT id, status FROM uploads WHERE id = %s", (upload_id,))
            row = cur.fetchone()
            if row:
                logger.error(f"Upload {upload_id} exists in database but fetch_upload() returned None")
            else:
                logger.error(f"Upload {upload_id} does not exist in database")
        except Exception as e:
            logger.error(f"Error checking database for upload {upload_id}: {e}")
        finally:
            cur.close()
        raise PermanentJobError(f"Upload {upload_id} was not found.")

    student_id = int(upload["student_id"])
    profile = student_profiles_repo.fetch_profile(student_id)
    if not profile:
        raise PermanentJobError(f"Student profile {student_id} not found.")

    try:
        file_bytes = _load_upload_content(upload, s3_client=s3_client)
    except FileNotFoundError as exc:
        raise PermanentJobError(f"Upload file missing for upload {upload_id}.") from exc

    filename = str(upload.get("filename", ""))
    try:
        extracted_text = text_extraction.extract_text(file_bytes, filename)
    except UnsupportedFileTypeError as exc:
        raise PermanentJobError(str(exc)) from exc

    word_count = text_extraction.word_count(extracted_text)
    required_words = _required_word_count(profile)
    if word_count < required_words:
        raise PermanentJobError(
            f"Upload {upload_id} has {word_count} words; {required_words} required."
        )

    cleaned_text = pii.scrub_pii(extracted_text)

    grade_level = int(profile.get("grade_level", 0) or 0)
    baseline_words = (
        student_profiles_repo.load_baseline_words(grade_level, limit=60)
        if grade_level
        else []
    )

    try:
        generated = recommendations.generate_recommendations(
            student_profile=profile,
            writing_sample=cleaned_text,
            baseline_words=baseline_words,
            target_batch_size=5,
        )
    except (OpenAIConfigurationError, OpenAIResponseError) as exc:
        raise RuntimeError(f"OpenAI error for upload {upload_id}: {exc}") from exc
    except RecommendationParseError as exc:
        raise RuntimeError(str(exc)) from exc

    filtered = content_filter.filter_recommendations(generated)
    if len(filtered) < 5:
        raise PermanentJobError(
            "Fewer than 5 recommendations remained after filtering profanity."
        )

    new_vocabulary_level = _compute_vocabulary_level(profile, filtered)

    recommendations_repo.replace_recommendations_for_upload(
        student_id=student_id,
        upload_id=upload_id,
        records=filtered,
    )

    student_profiles_repo.update_vocabulary_level(student_id, new_vocabulary_level)
    student_profiles_repo.mark_analyzed(student_id)


def process_upload_job(
    upload_id: int,
    *,
    s3_client=None,
    now: Optional[datetime.datetime] = None,
) -> JobResult:
    """Process a single upload job."""
    timestamp = now or datetime.datetime.utcnow()
    uploads_repo.mark_processing(upload_id)

    settings = get_settings()

    try:
        execute_with_retry(
            lambda: _process_attempt(upload_id, s3_client=s3_client),
            max_attempts=settings.AI_MAX_RETRIES,
            base_delay=settings.AI_RETRY_BACKOFF_BASE,
            cap_seconds=settings.AI_RETRY_BACKOFF_CAP,
            non_retry_exceptions=(PermanentJobError,),
        )
    except PermanentJobError as exc:
        uploads_repo.mark_failed(upload_id, processed_at=timestamp)
        logger.warning("Permanent failure processing upload %s: %s", upload_id, exc)
        return JobResult(upload_id=upload_id, success=False, error=str(exc))
    except Exception as exc:  # pragma: no cover - unexpected
        uploads_repo.mark_failed(upload_id, processed_at=timestamp)
        logger.exception("Failed to process upload %s", upload_id)
        return JobResult(upload_id=upload_id, success=False, error=str(exc))

    uploads_repo.mark_completed(upload_id, processed_at=timestamp)
    return JobResult(upload_id=upload_id, success=True, error=None)


def _recover_stuck_uploads() -> None:
    """Check for pending or processing uploads that are stuck and re-enqueue them."""
    try:
        # CRITICAL: Reset connection to ensure we're using PostgreSQL
        from models import reset_engine, get_connection
        reset_engine()
        
        from app.jobs.queue import enqueue_upload_job
        from models import update_upload_status
        
        conn = get_connection()
        cur = conn.cursor()
        
        from models import _backend
        is_sqlite = _backend == "sqlite" if _backend else 'sqlite3' in str(type(conn))
        
        # Log which database we're checking
        logger.debug(f"Recovering stuck uploads from {_backend if _backend else 'unknown'} database")
        
        all_stuck = []
        
        if is_sqlite:
            # Check for ALL pending uploads (not just old ones - catch immediately if not enqueued)
            cur.execute("""
                SELECT id FROM uploads 
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 20
            """)
            pending_rows = cur.fetchall()
            
            # Check for stuck processing uploads (older than 10 minutes)
            cur.execute("""
                SELECT id FROM uploads 
                WHERE status = 'processing' 
                AND datetime(created_at) < datetime('now', '-10 minutes')
                ORDER BY created_at ASC
                LIMIT 10
            """)
            processing_rows = cur.fetchall()
        else:
            # PostgreSQL - check for ALL pending uploads (not just old ones)
            cur.execute("""
                SELECT id FROM uploads 
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 20
            """)
            pending_rows = cur.fetchall()
            
            # PostgreSQL - processing uploads (older than 10 minutes)
            cur.execute("""
                SELECT id FROM uploads 
                WHERE status = 'processing' 
                AND created_at < NOW() - INTERVAL '10 minutes'
                ORDER BY created_at ASC
                LIMIT 10
            """)
            processing_rows = cur.fetchall()
        
        # Collect all stuck uploads
        for row in pending_rows:
            upload_id = row[0] if isinstance(row, (list, tuple)) else row.get("id")
            all_stuck.append(("pending", upload_id))
        
        for row in processing_rows:
            upload_id = row[0] if isinstance(row, (list, tuple)) else row.get("id")
            all_stuck.append(("processing", upload_id))
        
        if all_stuck:
            logger.info(f"Found {len(all_stuck)} stuck upload(s), re-enqueueing...")
            for status, upload_id in all_stuck:
                try:
                    # Reset status to pending before re-enqueueing
                    update_upload_status(int(upload_id), "pending")
                    enqueue_upload_job(int(upload_id))
                    logger.info(f"Re-enqueued stuck {status} upload {upload_id}")
                except Exception as e:
                    logger.warning(f"Failed to re-enqueue upload {upload_id}: {e}")
        
        cur.close()
    except Exception as e:
        logger.warning(f"Error checking for stuck uploads: {e}")


def run_worker_loop(stop_after: Optional[int] = None) -> None:
    """
    Continuously poll the queue and process upload jobs.

    Args:
        stop_after: Optional number of jobs to process before exiting (useful for tests).
    """
    processed = 0
    settings = get_settings()
    
    # Check for stuck uploads on startup
    logger.info("Checking for stuck pending uploads on startup...")
    _recover_stuck_uploads()
    
    # Check for stuck uploads every 1 minute (more aggressive to catch issues faster)
    import time
    last_recovery_check = time.time()
    recovery_interval = 60  # 1 minute

    while True:
        job = dequeue_upload_job(timeout=settings.JOB_POLL_INTERVAL_SECONDS)
        if job is None:
            # Periodically check for stuck uploads
            current_time = time.time()
            if current_time - last_recovery_check >= recovery_interval:
                _recover_stuck_uploads()
                last_recovery_check = current_time
            
            if stop_after is not None and processed >= stop_after:
                break
            continue

        upload_id = int(job["upload_id"])
        logger.info(f"Processing upload job {upload_id}...")
        try:
            result = process_upload_job(upload_id)
            if result.success:
                logger.info(f"Successfully processed upload {upload_id}")
            else:
                logger.warning(f"Failed to process upload {upload_id}: {result.error}")
        except Exception as exc:
            # Safety net: if process_upload_job itself crashes, try to mark as failed
            logger.exception(f"CRITICAL: process_upload_job crashed for upload {upload_id}: {exc}")
            try:
                uploads_repo.mark_failed(upload_id)
                logger.info(f"Marked upload {upload_id} as failed after crash")
            except Exception as mark_error:
                logger.error(f"Could not mark upload {upload_id} as failed: {mark_error}")
        finally:
            # Always ack the job so it doesn't get redelivered
            ack_job(job)

        processed += 1
        if stop_after is not None and processed >= stop_after:
            break


__all__ = [
    "process_upload_job",
    "run_worker_loop",
    "PermanentJobError",
]


if __name__ == "__main__":
    import logging
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    def signal_handler(sig, frame):
        logger.info("Received interrupt signal, shutting down gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting WordBridge background worker...")
    
    # Ensure we're using the correct database connection
    # Reset connection to ensure we pick up environment variables
    reset_engine()
    
    # Verify database configuration
    settings = get_settings()
    database_url = settings.DATABASE_URL
    if database_url:
        # Mask password in logs
        masked_url = database_url.split("@")[-1] if "@" in database_url else database_url
        logger.info(f"Database URL configured: postgresql://***@{masked_url}")
    else:
        logger.warning("DATABASE_URL not set, will use default SQLite database")
    
    # Initialize database to ensure tables exist
    try:
        logger.info("Initializing database...")
        init_db()
        
        # Reset connection again after init_db to ensure fresh connection
        reset_engine()
        
        # Verify connection works and can query uploads
        from models import get_connection
        conn = get_connection()
        # Check connection type directly since _backend might not be set yet
        is_postgres = "psycopg" in str(type(conn))
        backend = "PostgreSQL" if is_postgres else "SQLite"
        logger.info(f"Database initialized successfully (using {backend})")
        
        # Test that we can actually query the database
        cur = conn.cursor()
        try:
            if is_postgres:
                cur.execute("SELECT COUNT(*) FROM uploads")
            else:
                cur.execute("SELECT COUNT(*) FROM uploads")
            result = cur.fetchone()
            count = result[0] if isinstance(result, (tuple, list)) else result.get("count", 0) if isinstance(result, dict) else 0
            logger.info(f"Database connection verified - found {count} upload(s) in database")
        except Exception as db_test_error:
            logger.warning(f"Could not query uploads table (may not exist yet): {db_test_error}")
        finally:
            cur.close()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        logger.error("Worker cannot continue without database. Exiting.")
        sys.exit(1)
    
    logger.info("Worker will poll for upload jobs and process them asynchronously.")
    try:
        run_worker_loop()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
    except Exception as exc:
        logger.exception("Worker crashed: %s", exc)
        sys.exit(1)

