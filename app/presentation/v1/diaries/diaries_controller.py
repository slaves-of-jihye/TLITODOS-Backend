from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.infrastructure.database import Diary, diary_to_response, get_session
from app.shared.auth import require_access_token
from app.shared.uploads import save_upload


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


async def _find_diary(session: AsyncSession, diaryId: int, user_id: int) -> Diary:
    diary = await session.scalar(select(Diary).where(Diary.id == diaryId, Diary.user_id == user_id))
    if diary is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 일기입니다."})
    return diary


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_diary(
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        image = form.get("image")
        payload = DiaryCreateRequest(
            content=str(form.get("content", "")),
            imageUrl=await save_upload(image, "diaries") if isinstance(image, UploadFile) else None,
            emotion=str(form["emotion"]) if "emotion" in form else None,
            visibility=str(form.get("visibility", "PRIVATE")),
        )
    else:
        payload = DiaryCreateRequest(**await request.json())
    diary = Diary(
        user_id=user_id,
        content=payload.content,
        image_url=payload.image_url,
        emotion=payload.emotion,
        visibility=payload.visibility,
    )
    session.add(diary)
    await session.commit()
    await session.refresh(diary)
    return diary_to_response(diary)


@router.get("")
async def list_diaries(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    diaries = await session.scalars(select(Diary).where(Diary.user_id == user_id).order_by(Diary.id))
    return [diary_to_response(diary) for diary in diaries]


@router.get("/{diaryId}")
async def get_diary(
    diaryId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return diary_to_response(await _find_diary(session, diaryId, user_id))


@router.patch("/{diaryId}")
async def update_diary(
    diaryId: int,
    payload: DiaryPatchRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    diary = await _find_diary(session, diaryId, user_id)
    updates = payload.model_dump(by_alias=True, exclude_unset=True)
    for key, value in updates.items():
        setattr(diary, {"imageUrl": "image_url"}.get(key, key), value)
    await session.commit()
    await session.refresh(diary)
    return diary_to_response(diary)


@router.delete("/{diaryId}")
async def delete_diary(
    diaryId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    diary = await _find_diary(session, diaryId, user_id)
    await session.delete(diary)
    await session.commit()
    return {
        "success": True,
        "message": "일기가 삭제되었습니다.",
    }
