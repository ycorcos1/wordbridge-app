from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config.settings import get_settings

logger = logging.getLogger(__name__)


class QueueConfigurationError(RuntimeError):
    """Raised when the job queue is not configured correctly."""


class QueueOperationError(RuntimeError):
    """Raised when an operation against the job queue fails."""


def _require_queue_url() -> str:
    settings = get_settings()
    queue_url = settings.AWS_SQS_QUEUE_URL
    if not queue_url or not queue_url.strip():
        raise QueueConfigurationError(
            "AWS_SQS_QUEUE_URL must be set; SQS is required for background processing."
        )
    return queue_url


def _make_boto_client(service_name: str, region_name: Optional[str] = None):
    settings = get_settings()
    kwargs: dict[str, str] = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    if region_name is None and service_name == "sqs" and settings.AWS_SQS_QUEUE_URL:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(settings.AWS_SQS_QUEUE_URL)
            hostname_parts = parsed.hostname.split(".")
            if len(hostname_parts) >= 2 and hostname_parts[0] == "sqs":
                region_name = hostname_parts[1]
        except Exception:  # pragma: no cover - defensive
            pass

    if region_name:
        kwargs["region_name"] = region_name

    return boto3.client(service_name, **kwargs)


def enqueue_upload_job(upload_id: int) -> None:
    """Add an upload job to the SQS queue, raising on failure."""
    queue_url = _require_queue_url()
    sqs = _make_boto_client("sqs")
    try:
        # Use full UUID for deduplication ID to ensure uniqueness even for same file re-uploads
        # This prevents SQS from rejecting messages when the same file is uploaded after deletion
        unique_id = f"upload-{upload_id}-{uuid.uuid4().hex}"
        message_params = {
            "QueueUrl": queue_url,
            "MessageBody": f"upload_job_{upload_id}_{int(time.time())}",
            "MessageAttributes": {
                "upload_id": {"StringValue": str(upload_id), "DataType": "Number"}
            },
        }
        if ".fifo" in queue_url:
            message_params["MessageDeduplicationId"] = unique_id
            message_params["MessageGroupId"] = "upload-jobs"

        response = sqs.send_message(**message_params)
        message_id = response.get("MessageId", "unknown")
        logger.info(
            "Successfully enqueued upload job %s to SQS (MessageId: %s, Queue: %s)",
            upload_id,
            message_id,
            queue_url,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Failed to enqueue upload %s: %s", upload_id, exc, exc_info=True)
        raise QueueOperationError(f"Failed to enqueue upload {upload_id}") from exc


def dequeue_upload_job(
    timeout: Optional[float] = None,
) -> Optional[dict[str, object]]:
    """Return the next upload job payload or None when none available."""
    poll_timeout = timeout
    if poll_timeout is None:
        poll_timeout = get_settings().JOB_POLL_INTERVAL_SECONDS

    queue_url = _require_queue_url()
    sqs = _make_boto_client("sqs")
    wait_time = max(0, min(int(poll_timeout), 20))
    logger.info("Polling SQS queue for messages (timeout: %s seconds, queue: %s)", wait_time, queue_url)
    try:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            MessageAttributeNames=["All"],
            WaitTimeSeconds=wait_time,
        )
        message_count = len(response.get("Messages", []))
        logger.info("SQS receive_message returned %s message(s)", message_count)
    except (ClientError, BotoCoreError) as exc:
        logger.error("Failed to poll SQS for jobs: %s", exc, exc_info=True)
        raise QueueOperationError("Failed to poll SQS for jobs.") from exc

    messages = response.get("Messages")
    if not messages:
        logger.info("No messages available in SQS queue")
        return None

    message = messages[0]
    logger.info("Received message from SQS queue (MessageId: %s)", message.get("MessageId"))
    attributes = message.get("MessageAttributes") or {}
    upload_id_attr = attributes.get("upload_id") or {}
    upload_id_value = upload_id_attr.get("StringValue")
    if not upload_id_value:
        logger.warning("Discarding malformed SQS message: %s", message)
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=message["ReceiptHandle"],
        )
        return None

    return {
        "upload_id": int(upload_id_value),
        "receipt_handle": message["ReceiptHandle"],
    }


def ack_job(job_payload: dict[str, object]) -> None:
    """Acknowledge job completion for the SQS queue."""
    queue_url = _require_queue_url()
    receipt_handle = job_payload.get("receipt_handle")
    if not receipt_handle:
        logger.debug("No receipt handle provided; skipping ack.")
        return

    sqs = _make_boto_client("sqs")
    try:
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - defensive
        logger.warning("Failed to delete SQS message: %s", exc)

