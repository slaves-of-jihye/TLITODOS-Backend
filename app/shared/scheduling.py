from datetime import UTC, date, datetime
from datetime import time as ClockTime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator


def validate_body(model, data):
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


async def read_json(request):
    from fastapi import HTTPException

    try:
        return await request.json()
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, detail={"message": "유효한 JSON 본문을 보내세요."}) from exc


def today() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def todo_dates(todo) -> tuple[date, date]:
    # Old rows without a start date keep their original single-day placement.
    end = date.fromisoformat(todo.due_date) if todo.due_date else None
    start = todo.start_date or end or (todo.created_at.date() if todo.created_at else today())
    return start, end or start


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimedRequest(RequestModel):
    time: ClockTime | None = None
    timezone: str = "Asia/Seoul"

    @field_validator("time")
    @classmethod
    def local_time(cls, value):
        if value and (value.tzinfo is not None or value.second or value.microsecond or value.minute % 5):
            raise ValueError("시간은 시간대 없는 HH:MM, 5분 단위로 지정하세요.")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("유효한 IANA 시간대를 지정하세요.")
        return value
