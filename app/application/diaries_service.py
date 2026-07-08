from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.infrastructure.database import Diary, diary_to_response
from app.shared.uploads import save_upload


async def find_diary(session: AsyncSession, diary_id: int, user_id: int) -> Diary:
    diary = await session.scalar(select(Diary).where(Diary.id == diary_id, Diary.user_id == user_id))
    if diary is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 일기입니다."})
    return diary


async def payload_from_multipart(form, request_model):
    image = form.get("image")
    return request_model(
        content=str(form.get("content", "")),
        imageUrl=await save_upload(image, "diaries") if isinstance(image, UploadFile) else None,
        emotion=str(form["emotion"]) if "emotion" in form else None,
        visibility=str(form.get("visibility", "PRIVATE")),
    )


async def create_diary(session: AsyncSession, payload, user_id: int) -> dict:
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


async def list_diaries(session: AsyncSession, user_id: int) -> list[dict]:
    diaries = await session.scalars(select(Diary).where(Diary.user_id == user_id).order_by(Diary.id))
    return [diary_to_response(diary) for diary in diaries]


async def get_diary(session: AsyncSession, diary_id: int, user_id: int) -> dict:
    return diary_to_response(await find_diary(session, diary_id, user_id))


async def update_diary(session: AsyncSession, diary_id: int, payload, user_id: int) -> dict:
    diary = await find_diary(session, diary_id, user_id)
    updates = payload.model_dump(by_alias=True, exclude_unset=True)
    for key, value in updates.items():
        setattr(diary, {"imageUrl": "image_url"}.get(key, key), value)
    await session.commit()
    await session.refresh(diary)
    return diary_to_response(diary)


async def delete_diary(session: AsyncSession, diary_id: int, user_id: int) -> dict:
    diary = await find_diary(session, diary_id, user_id)
    await session.delete(diary)
    await session.commit()
    return {"success": True, "message": "일기가 삭제되었습니다."}
