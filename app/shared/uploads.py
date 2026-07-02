from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import UploadFile


UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))


async def save_upload(file: UploadFile, namespace: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = UPLOAD_DIR / namespace
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    filename = f"{secrets.token_urlsafe(18)}{suffix}"
    target = target_dir / filename
    with target.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            output.write(chunk)
    return f"/uploads/{namespace}/{filename}"
