from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import groups_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token


router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class GroupJoinRequest(BaseModel):
    invite_code: str = Field(alias="inviteCode", pattern=r"^[a-z0-9]{8}$")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.create_group(session, payload, user_id)


@router.get("")
async def list_groups(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.list_groups(session, user_id)


@router.post("/join")
async def join_group(
    payload: GroupJoinRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.join_group(session, payload, user_id)


@router.get("/{groupId}")
async def get_group(
    groupId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.get_group(session, groupId, user_id)


@router.get("/{groupId}/invite-code")
async def get_invite_code(
    groupId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.get_invite_code(session, groupId, user_id)


@router.delete("/{groupId}/members/{userId}")
async def remove_member(
    groupId: int,
    userId: int,
    request_user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.remove_member(session, groupId, userId, request_user_id)


@router.post("/{groupId}/leave")
async def leave_group(
    groupId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.leave_group(session, groupId, user_id)


@router.delete("/{groupId}")
async def delete_group(
    groupId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await groups_service.delete_group(session, groupId, user_id)
