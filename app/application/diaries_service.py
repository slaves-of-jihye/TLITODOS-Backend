from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.groups_service import require_shared_group_membership
from app.application.notifications_service import notify_peers, peer_ids
from app.infrastructure.database import Diary, Notification, diary_to_response


async def find_diary(session: AsyncSession, diary_id: int, user_id: int) -> Diary:
    diary = await session.scalar(select(Diary).where(Diary.id == diary_id, Diary.user_id == user_id).with_for_update())
    if diary is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 일기입니다."})
    return diary


async def create_diary(session: AsyncSession, payload, user_id: int) -> dict:
    await validate_image_reference(session, payload, user_id)
    diary = Diary(
        user_id=user_id,
        content=payload.content,
        image_url=payload.image_url,
        emotion=payload.emotion,
        visibility=payload.visibility,
        date=payload.date,
    )
    session.add(diary)
    await session.flush()
    if diary.visibility == "PUBLIC":
        await notify_peers(session, user_id, "DIARY_CREATED", f"diary:{diary.id}", diary_id=diary.id)
    await session.commit()
    await session.refresh(diary)
    return diary_to_response(diary)


async def list_diaries(
    session: AsyncSession, user_id: int, date=None, target_user_id=None, group_id=None
) -> list[dict]:
    owner_id = target_user_id if target_user_id is not None else user_id
    statement = select(Diary).where(Diary.user_id == owner_id)
    if owner_id != user_id:
        if group_id is not None:
            await require_shared_group_membership(session, group_id, user_id, owner_id)
        if owner_id not in set(await session.scalars(peer_ids(user_id))):
            raise HTTPException(403, detail={"message": "같은 그룹원의 공개 일기만 조회할 수 있습니다."})
        statement = statement.where(Diary.visibility == "PUBLIC")
    if date is not None:
        statement = statement.where(Diary.date == date)
    diaries = await session.scalars(statement.order_by(Diary.date.desc(), Diary.id.desc()))
    return [diary_to_response(diary) for diary in diaries]


async def get_diary(session: AsyncSession, diary_id: int, user_id: int) -> dict:
    diary = await session.get(Diary, diary_id)
    await require_diary_access(session, diary, user_id)
    return diary_to_response(diary)


async def require_diary_access(session, diary, user_id):
    if diary is None or (
        diary.user_id != user_id
        and (diary.visibility != "PUBLIC" or diary.user_id not in set(await session.scalars(peer_ids(user_id))))
    ):
        raise HTTPException(404, detail={"message": "존재하지 않거나 공개되지 않은 일기입니다."})


async def update_diary(session: AsyncSession, diary_id: int, payload, user_id: int) -> dict:
    diary = await find_diary(session, diary_id, user_id)
    await validate_image_reference(session, payload, user_id)
    was_public = diary.visibility == "PUBLIC"
    updates = payload.model_dump(by_alias=True, exclude_unset=True)
    for key, value in updates.items():
        setattr(diary, {"imageUrl": "image_url"}.get(key, key), value)
    if diary.visibility != "PUBLIC":
        await session.execute(delete(Notification).where(Notification.diary_id == diary.id))
    elif not was_public:
        await notify_peers(session, user_id, "DIARY_CREATED", f"diary:{diary.id}", diary_id=diary.id)
    await session.commit()
    await session.refresh(diary)
    return diary_to_response(diary)


async def delete_diary(session: AsyncSession, diary_id: int, user_id: int) -> dict:
    diary = await find_diary(session, diary_id, user_id)
    await session.delete(diary)
    await session.commit()
    return {"success": True, "message": "일기가 삭제되었습니다."}


async def validate_image_reference(session, payload, user_id):
    url = payload.image_url
    if not url or getattr(payload, "_uploaded_image", False):
        return
    if url.startswith("/uploads/diaries/"):
        owned = await session.scalar(select(Diary.id).where(Diary.user_id == user_id, Diary.image_url == url).limit(1))
        if owned is not None:
            return
    # Private images must be uploaded to this server, not unprotected remote URLs.
    raise HTTPException(
        422, detail={"message": "이미지는 multipart의 image 파일로 첨부하거나 본인 일기의 기존 imageUrl을 사용하세요."}
    )
