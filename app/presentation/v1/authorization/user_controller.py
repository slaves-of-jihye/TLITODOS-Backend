from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.application import auth_service
from app.infrastructure.database import get_session
from app.presentation.v1.responses import TimeFormatSettingResponse
from app.shared.auth import require_access_token
from app.shared.fonts import SUPPORTED_FONTS
from app.shared.scheduling import RequestModel, read_json, validate_body
from app.shared.time_format import TimeFormat
from app.shared.uploads import save_upload

router = APIRouter(prefix="/api/v1/users/me", tags=["authorization"])


class NotificationSettingsRequest(BaseModel):
    discord_alert_enabled: bool = Field(alias="discordAlertEnabled")


class FontSettingRequest(BaseModel):
    font: str

    @field_validator("font")
    @classmethod
    def known_font(cls, value: str) -> str:
        if value not in SUPPORTED_FONTS:
            raise ValueError("unsupported font")
        return value


class TimeFormatSettingRequest(RequestModel):
    time_format: TimeFormat = Field(alias="timeFormat")


class ProfilePatchRequest(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"\S")
    bio: str | None = Field(default=None, max_length=30)
    profileImageUrl: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def no_null_text(self):
        if any(getattr(self, key) is None for key in self.model_fields_set & {"name", "bio"}):
            raise ValueError("이름과 자기소개는 null일 수 없습니다.")
        return self


@router.get("")
async def get_me(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.get_me(session, user_id)


@router.patch(
    "",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {"schema": ProfilePatchRequest.model_json_schema()},
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "minLength": 1, "maxLength": 80},
                            "bio": {"type": "string", "maxLength": 30},
                            "image": {"type": "string", "format": "binary"},
                        },
                    }
                },
            }
        }
    },
)
async def update_me(
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    updates: dict[str, str] = {}
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        updates = validate_body(ProfilePatchRequest, await read_json(request)).model_dump(exclude_unset=True)
    elif "multipart/form-data" in content_type:
        form = await request.form()
        updates = validate_body(
            ProfilePatchRequest, {key: value for key, value in form.items() if key != "image"}
        ).model_dump(exclude_unset=True)
        if "image" in form:
            if not isinstance(form["image"], UploadFile):
                raise HTTPException(422, detail={"message": "image는 파일이어야 합니다."})
            updates["profileImageUrl"] = await save_upload(form["image"], "profiles")
    else:
        raise HTTPException(415, detail={"message": "JSON 또는 multipart/form-data를 사용하세요."})
    return await auth_service.update_me(session, user_id, updates)


@router.patch("/notifications")
async def update_notifications(
    payload: NotificationSettingsRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.update_notifications(session, user_id, payload.discord_alert_enabled)


@router.patch(
    "/time-format",
    response_model=TimeFormatSettingResponse,
    summary="시간 표기 방식 변경",
    description="본인의 시간 표시 설정을 12H 또는 24H로 변경합니다. 기본값은 12H이며 저장된 할 일 시각과 시간대는 변경하지 않습니다.",
)
async def update_time_format(
    payload: TimeFormatSettingRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.update_time_format(session, user_id, payload.time_format)


@router.patch("/font")
async def update_font(
    payload: FontSettingRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await auth_service.update_font(session, user_id, payload.font)
