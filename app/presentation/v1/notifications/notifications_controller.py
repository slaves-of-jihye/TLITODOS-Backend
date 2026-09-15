from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import notifications_service
from app.infrastructure.database import get_session
from app.presentation.v1.responses import (
    NotificationsPageResponse,
    NotificationUnreadStatusResponse,
)
from app.shared.auth import require_access_token

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsPageResponse)
async def list_notifications(
    type: Literal["TODO_COMPLETED", "DIARY_CREATED", "BET_REQUESTED"] | None = None,
    cursor: int | None = Query(default=None, gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await notifications_service.list_notifications(session, user_id, type, cursor, limit)


@router.get(
    "/unread-status",
    response_model=NotificationUnreadStatusResponse,
    summary="알림 타입별 안 읽은 알림 존재 여부",
    description="본인이 조회할 수 있는 알림 전체에서 readAt이 null인 알림이 하나라도 있으면 해당 타입이 true입니다. 조회로 읽음 상태를 변경하지 않습니다.",
)
async def unread_status(user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)):
    return await notifications_service.unread_status(session, user_id)


@router.patch("/{notificationId}/read")
async def read_notification(
    notificationId: int, user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)
):
    return await notifications_service.read_notification(session, notificationId, user_id)
