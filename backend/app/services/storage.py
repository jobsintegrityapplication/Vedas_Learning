import logging
import time
from uuid import uuid4

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings

log = logging.getLogger(__name__)

NAMESPACES = {"guru", "learner"}
_MEMORY: dict[str, tuple[bytes, str]] = {}


def reset_memory_store() -> None:
    _MEMORY.clear()


def _use_memory() -> bool:
    return get_settings().audio_store.lower() == "memory"


def ensure_bucket(attempts: int = 15) -> None:
    if _use_memory():
        return
    settings = get_settings()
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            client = _client()
            try:
                client.head_bucket(Bucket=settings.s3_bucket)
            except ClientError:
                client.create_bucket(Bucket=settings.s3_bucket)
            log.info("Audio bucket %s is ready", settings.s3_bucket)
            return
        except (BotoCoreError, ClientError, Exception) as exc:
            last_error = exc
            log.warning("Waiting for object storage (attempt %s/%s): %s", attempt, attempts, exc)
            time.sleep(2)
    raise RuntimeError("Audio storage bucket could not be created") from last_error


def _client(endpoint: str | None = None):
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def put_bytes(key: str, data: bytes, content_type: str) -> str:
    if not key.startswith("guru/") and not key.startswith("learner/"):
        raise ValueError("Audio keys must use the guru/ or learner/ namespace")
    if _use_memory():
        _MEMORY[key] = (data, content_type)
        return key
    settings = get_settings()
    try:
        _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError) as exc:
        log.exception("Storage upload failed")
        raise RuntimeError("Audio storage is unavailable") from exc
    return key


def get_bytes(key: str) -> tuple[bytes, str] | None:
    if not key:
        return None
    if _use_memory():
        return _MEMORY.get(key)
    settings = get_settings()
    try:
        response = _client().get_object(Bucket=settings.s3_bucket, Key=key)
        return response["Body"].read(), response.get("ContentType") or "application/octet-stream"
    except (BotoCoreError, ClientError):
        log.exception("Storage download failed for %s", key)
        return None


def object_key(kind: str, owner_id: str, filename: str) -> str:
    if kind not in NAMESPACES:
        raise ValueError("Audio kind must be guru or learner")
    safe = filename.replace("\\", "/").split("/")[-1]
    return f"{kind}/{owner_id}/{uuid4().hex}_{safe}"


def presigned_get(key: str, expires: int = 3600) -> str | None:
    if not key:
        return None
    settings = get_settings()
    try:
        public = settings.s3_public_endpoint_url or settings.s3_endpoint_url
        return _client(public).generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )
    except (BotoCoreError, ClientError):
        log.exception("Presign failed for %s", key)
        return None
