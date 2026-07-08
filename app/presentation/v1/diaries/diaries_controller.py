from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import diaries_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token


router = APIRouter(prefix="/api/v1/diaries", tags=["diaries"])


class DiaryCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    image_url: str | None = Field(default=None, alias="imageUrl")
    emotion: str | None = None
    visibility: str = "PRIVATE"


class DiaryPatchRequest(BaseModel):
    content: str | None = None
    image_url: str | None = Field(default=None, alias="imageUrl")
    emotion: str | None = None
    visibility: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_diary(
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = await diaries_service.payload_from_multipart(form, DiaryCreateRequest)
    else:
        payload = DiaryCreateRequest(**await request.json())
    return await diaries_service.create_diary(session, payload, user_id)


@router.get("")
async def list_diaries(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await diaries_service.list_diaries(session, user_id)


@router.get("/{diaryId}")
async def get_diary(
    diaryId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await diaries_service.get_diary(session, diaryId, user_id)


@router.patch("/{diaryId}")
async def update_diary(
    diaryId: int,
    payload: DiaryPatchRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await diaries_service.update_diary(session, diaryId, payload, user_id)


@router.delete("/{diaryId}")
async def delete_diary(
    diaryId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await diaries_service.delete_diary(session, diaryId, user_id)
