from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.bets_service import find_bet
from app.application.diaries_service import require_diary_access
from app.infrastructure.database import Bet, Diary, get_session
from app.shared.auth import require_access_token
from app.shared.uploads import UPLOAD_DIR

router = APIRouter(tags=["uploads"])
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def image_response(namespace, filename, private=True):
    root = (UPLOAD_DIR / namespace).resolve()
    path = (root / filename).resolve()
    if path.parent != root or path.suffix.lower() not in IMAGE_TYPES or not path.is_file():
        raise HTTPException(404, detail={"message": "이미지를 찾을 수 없습니다."})
    return FileResponse(
        path,
        media_type=IMAGE_TYPES[path.suffix.lower()],
        headers={
            "Cache-Control": "private, no-store" if private else "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/uploads/profiles/{filename}")
async def profile_image(filename: str):
    return image_response("profiles", filename, private=False)


@router.get("/uploads/diaries/{filename}")
async def diary_image(
    filename: str, user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)
):
    diaries = list(await session.scalars(select(Diary).where(Diary.image_url == f"/uploads/diaries/{filename}")))
    for diary in diaries:
        try:
            await require_diary_access(session, diary, user_id)
        except HTTPException:
            continue
        return image_response("diaries", filename)
    raise HTTPException(404, detail={"message": "이미지를 찾을 수 없습니다."})


@router.get("/uploads/bet-proofs/{filename}")
async def bet_image(
    filename: str, user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)
):
    bet = await session.scalar(select(Bet).where(Bet.proof_image_url == f"/uploads/bet-proofs/{filename}"))
    if bet is None:
        raise HTTPException(404, detail={"message": "이미지를 찾을 수 없습니다."})
    await find_bet(session, bet.id, user_id, role="participant")
    return image_response("bet-proofs", filename)
