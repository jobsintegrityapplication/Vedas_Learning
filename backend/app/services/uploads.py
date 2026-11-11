from fastapi import HTTPException, UploadFile

from app.core.config import get_settings
from app.services.audio_validation import AudioInspection, AudioValidationError, inspect_audio


async def read_audio_upload(upload: UploadFile) -> tuple[bytes, str, str, AudioInspection]:
    filename = (upload.filename or "audio.wav").replace("\\", "/").split("/")[-1]
    data = await upload.read(get_settings().max_upload_bytes + 1)
    content_type = upload.content_type or "application/octet-stream"
    try:
        inspection = inspect_audio(data, filename, content_type)
    except AudioValidationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return data, content_type, filename, inspection
