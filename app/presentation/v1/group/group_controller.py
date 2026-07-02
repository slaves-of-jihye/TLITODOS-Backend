from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import Group, GroupMember, User, create_invite_code, get_session
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
    group = Group(name=payload.name, description=payload.description, invite_code=await create_invite_code(session))
    session.add(group)
    await session.flush()
    session.add(GroupMember(group_id=group.id, user_id=user_id, role="LEADER"))
    await session.commit()
    return {
        "groupId": group.id,
        "name": group.name,
        "inviteCode": group.invite_code,
    }


@router.get("")
async def list_groups(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Group, GroupMember.role)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user_id)
    )
    groups = []
    for group, role in result.all():
        member_count = await session.scalar(select(func.count(GroupMember.id)).where(GroupMember.group_id == group.id))
        groups.append(
            {
                "groupId": group.id,
                "name": group.name,
                "memberCount": member_count,
                "isLeader": role == "LEADER",
            },
        )
    return groups


@router.post("/join")
async def join_group(
    payload: GroupJoinRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    group = await session.scalar(select(Group).where(Group.invite_code == payload.invite_code))
    if group is None:
        raise HTTPException(status_code=404, detail={"message": "유효하지 않거나 만료된 초대 코드입니다."})
    existing = await session.scalar(select(GroupMember.id).where(GroupMember.group_id == group.id, GroupMember.user_id == user_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"message": "이미 가입된 그룹입니다."})
    member_count = await session.scalar(select(func.count(GroupMember.id)).where(GroupMember.group_id == group.id))
    if member_count >= 30:
        raise HTTPException(status_code=400, detail={"message": "그룹 정원(30명)이 초과되어 가입할 수 없습니다."})
    session.add(GroupMember(group_id=group.id, user_id=user_id, role="MEMBER"))
    await session.commit()
    return {
        "groupId": group.id,
        "name": group.name,
        "message": "그룹에 성공적으로 가입되었습니다.",
    }


@router.get("/{groupId}")
async def get_group(
    groupId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    group = await session.get(Group, groupId)
    if group is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 그룹입니다."})
    membership = await session.scalar(select(GroupMember).where(GroupMember.group_id == groupId, GroupMember.user_id == user_id))
    if membership is None:
        raise HTTPException(status_code=403, detail={"message": "해당 그룹의 멤버가 아닙니다."})
    result = await session.execute(
        select(User, GroupMember.role)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == groupId)
        .limit(30)
    )
    return {
        "groupId": group.id,
        "name": group.name,
        "description": group.description,
        "inviteCode": group.invite_code,
        "members": [
            {
                "userId": user.id,
                "name": user.name,
                "profileImageUrl": user.profile_image_url,
                "role": role,
            }
            for user, role in result.all()
        ],
    }


@router.delete("/{groupId}/members/{userId}")
async def remove_member(
    groupId: int,
    userId: int,
    request_user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    group = await session.get(Group, groupId)
    if group is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 그룹입니다."})
    leader = await session.scalar(select(GroupMember).where(GroupMember.group_id == groupId, GroupMember.user_id == request_user_id, GroupMember.role == "LEADER"))
    if leader is None:
        raise HTTPException(status_code=403, detail={"message": "멤버를 강퇴할 권한(그룹장)이 없습니다."})
    if userId == leader.user_id:
        raise HTTPException(status_code=400, detail={"message": "그룹장 자신을 강퇴할 수 없습니다. (그룹 탈퇴 또는 삭제 기능을 이용해주세요)"})
    member = await session.scalar(select(GroupMember).where(GroupMember.group_id == groupId, GroupMember.user_id == userId))
    if member is None:
        raise HTTPException(status_code=404, detail={"message": "멤버를 찾을 수 없습니다."})
    await session.delete(member)
    await session.commit()
    return {
        "success": True,
        "message": "멤버가 그룹에서 퇴장되었습니다.",
    }
