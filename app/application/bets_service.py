from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.infrastructure.database import Bet, Todo, bet_to_response
from app.shared.uploads import save_upload


async def find_bet(session: AsyncSession, bet_id: int, user_id: int, role="owner") -> Bet:
    condition = Todo.user_id == user_id if role == "owner" else Bet.requester_id == user_id
    if role == "participant":
        condition = or_(Todo.user_id == user_id, Bet.requester_id == user_id)
    bet = await session.scalar(
        select(Bet).join(Todo, Todo.id == Bet.todo_id).where(Bet.id == bet_id, condition).with_for_update(of=Bet)
    )
    if bet is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 내기입니다."})
    return bet


async def update_bet_status(session: AsyncSession, bet_id: int, payload, user_id: int) -> dict:
    bet = await find_bet(session, bet_id, user_id)
    if bet.status not in {"PENDING", payload.status}:
        raise HTTPException(409, detail={"message": "이미 처리된 내기입니다."})
    bet.status = payload.status
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)


async def upload_bet_proof(session: AsyncSession, bet_id: int, form, user_id: int) -> dict:
    bet = await find_bet(session, bet_id, user_id)
    if bet.status != "ACCEPTED":
        raise HTTPException(409, detail={"message": "수락된 내기에만 인증 사진을 올릴 수 있습니다."})
    image = form.get("image")
    if not isinstance(image, UploadFile):
        raise HTTPException(status_code=400, detail={"message": "이미지 파일이 필요합니다."})
    bet.proof_image_url = await save_upload(image, "bet-proofs")
    await session.commit()
    return {"success": True, "betId": bet_id, "proofImageUrl": bet.proof_image_url}


async def verify_bet(session: AsyncSession, bet_id: int, payload, user_id: int) -> dict:
    bet = await find_bet(session, bet_id, user_id, role="requester")
    if bet.status != "ACCEPTED" or not bet.proof_image_url:
        raise HTTPException(409, detail={"message": "수락 및 사진 제출 후 확인할 수 있습니다."})
    bet.is_verified = payload.approved
    if payload.approved:
        bet.status = "VERIFIED"
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)


async def list_bets(session, user_id):
    bets = await session.scalars(
        select(Bet)
        .join(Todo, Bet.todo_id == Todo.id)
        .where(or_(Bet.requester_id == user_id, Todo.user_id == user_id))
        .order_by(Bet.id.desc())
    )
    return [bet_to_response(bet) for bet in bets]
