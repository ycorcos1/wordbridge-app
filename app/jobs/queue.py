from __future__ import annotations

import queue
from typing import Optional

import boto3

from config.settings import get_settings

_LOCAL_QUEUE: "queue.Queue[dict[str, int]]" = queue.Queue()


def queue_mode() -> str:
    settings = get_settings()
    if settings.AWS_SQS_QUEUE_URL and settings.AWS_SQS_QUEUE_URL.strip():
        return "sqs"
    return settings.JOB_QUEUE_PROVIDER or "inmemory"


def _make_boto_client(service_name: str, region_name: Optional[str] = None):
    settings = get_settings()
    kwargs: dict[str, str] = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    
    # Extract region from SQS queue URL if provided and no region specified
    if region_name is None and service_name == "sqs" and settings.AWS_SQS_QUEUE_URL:
        # Extract region from queue URL: https://sqs.REGION.amazonaws.com/...
        try:
            from urllib.parse import urlparse
            parsed = urlparse(settings.AWS_SQS_QUEUE_URL)
            # Format: sqs.us-east-2.amazonaws.com
            hostname_parts = parsed.hostname.split(".")
            if len(hostname_parts) >= 2 and hostname_parts[0] == "sqs":
                region_name = hostname_parts[1]
        except Exception:
            pass
    
    if region_name:
        kwargs["region_name"] = region_name
    
    return boto3.client(service_name, **kwargs)


def enqueue_upload_job(upload_id: int) -> None:
    """Add an upload job to the active queue backend."""
    mode = queue_mode()
    if mode == "sqs":
        settings = get_settings()
        queue_url = settings.AWS_SQS_QUEUE_URL
        if not queue_url or not queue_url.strip():
            # fall back to local queue when URL not configured
            _LOCAL_QUEUE.put({"upload_id": int(upload_id)})
            return
        try:
            sqs = _make_boto_client("sqs")
            import uuid
            import time
            
            # Create a unique message ID that includes timestamp and UUID
            # This ensures each upload (even the same file after deletion) gets a unique message
            # For FIFO queues, this prevents deduplication
            # For standard queues, this is harmless but ensures uniqueness
            unique_id = f"upload-{upload_id}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
            
            # Build message parameters
            message_params = {
                "QueueUrl": queue_url,
                "MessageBody": f"upload_job_{upload_id}_{int(time.time())}",
                "MessageAttributes": {
                    "upload_id": {"StringValue": str(upload_id), "DataType": "Number"}
                },
            }
            
            # Only add MessageDeduplicationId for FIFO queues
            if ".fifo" in queue_url:
                message_params["MessageDeduplicationId"] = unique_id
                # FIFO queues also require MessageGroupId
                message_params["MessageGroupId"] = "upload-jobs"
            
            sqs.send_message(**message_params)
            
            # Log for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Enqueued upload job {upload_id} with unique ID: {unique_id}")
            return
        except Exception as e:
            # If SQS fails, fall back to local queue and log the error
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"SQS enqueue failed, falling back to local queue: {e}")
            _LOCAL_QUEUE.put({"upload_id": int(upload_id)})
            return

    _LOCAL_QUEUE.put({"upload_id": int(upload_id)})


def dequeue_upload_job(
    timeout: Optional[float] = None,
) -> Optional[dict[str, object]]:
    """Return the next upload job payload or None when none available."""
    mode = queue_mode()
    poll_timeout = timeout
    if poll_timeout is None:
        poll_timeout = get_settings().JOB_POLL_INTERVAL_SECONDS

    if mode == "sqs":
        settings = get_settings()
        queue_url = settings.AWS_SQS_QUEUE_URL
        if not queue_url or not queue_url.strip():
            # Fall back to local queue if SQS URL not configured
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("SQS queue URL not configured, falling back to local queue")
            try:
                payload = _LOCAL_QUEUE.get(timeout=poll_timeout)
            except queue.Empty:
                return None
            return dict(payload)

        sqs = _make_boto_client("sqs")
        wait_time = max(0, min(int(poll_timeout), 20))
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                MessageAttributeNames=["All"],
                WaitTimeSeconds=wait_time,
            )
            messages = response.get("Messages")
            if not messages:
                return None
            message = messages[0]
            attributes = message.get("MessageAttributes") or {}
            upload_id_attr = attributes.get("upload_id") or {}
            upload_id_value = upload_id_attr.get("StringValue")
            if not upload_id_value:
                # ack malformed message
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )
                return None
            return {
                "upload_id": int(upload_id_value),
                "receipt_handle": message["ReceiptHandle"],
            }
        except Exception as e:
            # If SQS receive fails, fall back to local queue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"SQS receive_message failed, falling back to local queue: {e}")
            try:
                payload = _LOCAL_QUEUE.get(timeout=0.1)  # Quick check, don't wait long
            except queue.Empty:
                return None
            return dict(payload)

    try:
        payload = _LOCAL_QUEUE.get(timeout=poll_timeout)
    except queue.Empty:
        return None
    return dict(payload)


def ack_job(job_payload: dict[str, object]) -> None:
    """Acknowledge job completion for the active queue backend."""
    mode = queue_mode()
    if mode == "sqs":
        settings = get_settings()
        queue_url = settings.AWS_SQS_QUEUE_URL
        receipt_handle = job_payload.get("receipt_handle")
        if queue_url and receipt_handle:
            sqs = _make_boto_client("sqs")
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
    else:
        # local queue acknowledgement handled automatically by Queue.get
        pass


def clear_local_queue() -> None:
    """Utility for tests: drain the in-memory queue."""
    while not _LOCAL_QUEUE.empty():
        try:
            _LOCAL_QUEUE.get_nowait()
        except queue.Empty:
            break

