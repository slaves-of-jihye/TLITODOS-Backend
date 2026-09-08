from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import routines_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token

router = APIRouter(prefix="/api/v1/todos/routines", tags=["todos"])


class RoutineCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(alias="requestId", description="한 번의 생성 동작마다 발급하고 재시도할 때 재사용하는 UUID")
    title: str = Field(min_length=1, max_length=200)
    category_id: int = Field(alias="categoryId")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    weekdays: list[Annotated[int, Field(strict=True, ge=1, le=7)]] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5, 6, 7], min_length=1, max_length=7,
        description="ISO 요일: 월요일=1, 일요일=7. 생략하면 매일 반복",
    )
    importance: Literal["NONE", "LOW", "HIGH"] = "NONE"
    hardship: int = Field(default=1, ge=1, le=5)
    x: float = Field(default=0, allow_inf_nan=False)
    y: float = Field(default=0, allow_inf_nan=False)

    @field_validator("weekdays")
    @classmethod
    def normalize_weekdays(cls, value: list[int]) -> list[int]:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        span = (self.end_date - self.start_date).days
        if span < 0 or span >= 366:
            raise ValueError("시작일과 종료일을 포함한 기간은 1~366일이어야 합니다.")
        return self


class RoutineOccurrenceResponse(BaseModel):
    todoId: int
    dueDate: date


class RoutineCreateResponse(BaseModel):
    routineId: int
    createdCount: int
    occurrences: list[RoutineOccurrenceResponse]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RoutineCreateResponse)
async def create_routine(
    payload: RoutineCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await routines_service.create_routine(session, payload, user_id)
