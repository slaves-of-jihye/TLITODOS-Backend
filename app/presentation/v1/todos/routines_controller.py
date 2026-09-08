from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import routines_service
from app.infrastructure.database import get_session
from app.presentation.v1.responses import RoutineDeleteResponse, RoutineResponse
from app.shared.auth import require_access_token
from app.shared.scheduling import RequestModel, TimedRequest

router = APIRouter(prefix="/api/v1/todos", tags=["routines"])
Weekday = Annotated[int, Field(strict=True, ge=1, le=7)]


class Recurrence(RequestModel):
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]
    interval: Annotated[int, Field(strict=True, ge=1, le=2)] = 1
    weekdays: list[Weekday] | None = Field(default=None, min_length=1, max_length=7)

    @field_validator("weekdays")
    @classmethod
    def normalize_days(cls, value):
        return sorted(set(value)) if value else value

    @model_validator(mode="after")
    def weekly_options(self):
        if self.frequency != "WEEKLY" and (self.interval != 1 or self.weekdays is not None):
            raise ValueError("요일 선택과 interval=2(격주)는 WEEKLY에서만 사용할 수 있습니다.")
        return self


class RoutineScheduleRequest(TimedRequest):
    request_id: UUID = Field(alias="requestId")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    recurrence: Recurrence | None = None
    weekdays: list[Weekday] | None = Field(
        default=None,
        min_length=1,
        max_length=7,
        description="이전 클라이언트 호환 필드. recurrence와 동시에 보내지 않습니다.",
    )

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 36600:
            raise ValueError("종료일은 시작일 이후, 기간은 최대 36,600일입니다.")
        if self.recurrence is not None and self.weekdays is not None:
            raise ValueError("recurrence와 weekdays 중 하나만 지정하세요.")
        if self.recurrence is None:
            days = sorted(set(self.weekdays or range(1, 8)))
            self.recurrence = (
                Recurrence(frequency="DAILY")
                if days == list(range(1, 8))
                else Recurrence(frequency="WEEKLY", weekdays=days)
            )
        if self.recurrence.frequency == "WEEKLY" and self.recurrence.weekdays is None:
            self.recurrence.weekdays = [self.start_date.isoweekday()]
        self.weekdays = None
        return self


class RoutineCreateRequest(RoutineScheduleRequest):
    title: str = Field(min_length=1, max_length=40, pattern=r"\S")
    description: str = Field(default="", max_length=100)
    category_id: int = Field(alias="categoryId")
    importance: Literal["NONE", "LOW", "HIGH"] = "NONE"
    hardship: int = Field(default=1, ge=1, le=5)
    x: float = Field(default=0, allow_inf_nan=False)
    y: float = Field(default=0, allow_inf_nan=False)


class RoutineOccurrenceResponse(RequestModel):
    todoId: int
    dueDate: date


class RoutineCreateResponse(RequestModel):
    routineId: int
    createdCount: int
    occurrences: list[RoutineOccurrenceResponse]


@router.post(
    "/routines",
    status_code=status.HTTP_201_CREATED,
    response_model=RoutineCreateResponse,
    summary="루틴 일괄 생성",
    description="매일·매주·격주·매월·매년. 양끝 포함, 없는 날짜는 건너뜀. 최대 1,000회차. 같은 requestId 재시도는 중복 생성하지 않습니다.",
)
async def create_routine(
    payload: RoutineCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await routines_service.create_routine(session, payload, user_id)


@router.post(
    "/{todoId}/routine",
    status_code=201,
    response_model=RoutineCreateResponse,
    summary="기존 할 일을 루틴의 첫 회차로 전환",
)
async def convert_routine(
    todoId: int,
    payload: RoutineScheduleRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await routines_service.create_routine(session, payload, user_id, source_todo_id=todoId)


@router.get("/routines/{routineId}", response_model=RoutineResponse)
async def get_routine(
    routineId: int, user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)
):
    return await routines_service.get_routine(session, routineId, user_id)


@router.delete("/routines/{routineId}", response_model=RoutineDeleteResponse, summary="루틴 및 모든 회차 전체 삭제")
async def delete_routine(
    routineId: int, user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)
):
    return await routines_service.delete_routine(session, routineId, user_id)
