from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))


async def save_upload(file: UploadFile, namespace: str) -> str:
    # Bound memory/disk usage and never serve uploaded HTML/SVG as an image.
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, detail={"message": "이미지는 최대 10MB입니다."})
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif data.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        suffix = ".gif"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        suffix = ".webp"
    else:
        raise HTTPException(422, detail={"message": "PNG, JPEG, GIF, WebP 이미지 파일만 지원합니다."})
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = UPLOAD_DIR / namespace
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_urlsafe(18)}{suffix}"
    target = target_dir / filename
    with target.open("wb") as output:
        output.write(data)
    return f"/uploads/{namespace}/{filename}"
