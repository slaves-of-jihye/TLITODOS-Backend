from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import notifications_service
from app.infrastructure.database import get_session
from app.presentation.v1.responses import NotificationsPageResponse
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


@router.patch("/{notificationId}/read")
async def read_notification(
    notificationId: int, user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)
):
    return await notifications_service.read_notification(session, notificationId, user_id)
