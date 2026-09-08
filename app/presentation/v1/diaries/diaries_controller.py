from datetime import date as CalendarDate
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.application import diaries_service
from app.infrastructure.database import get_session
from app.presentation.v1.responses import DiaryResponse
from app.shared.auth import require_access_token
from app.shared.scheduling import RequestModel, read_json, today, validate_body
from app.shared.uploads import save_upload

router = APIRouter(prefix="/api/v1/diaries", tags=["diaries"])


class DiaryCreateRequest(RequestModel):
    date: CalendarDate = Field(default_factory=today)
    content: str = Field(min_length=1, max_length=10000, pattern=r"\S")
    image_url: str | None = Field(default=None, alias="imageUrl")
    emotion: str | None = Field(default=None, max_length=40)
    visibility: Literal["PRIVATE", "GROUP", "PUBLIC"] = Field(
        default="PRIVATE",
        description="PUBLIC=같은 그룹원, PRIVATE=나만. GROUP(일부 공개)은 보류 상태로 작성자만 조회할 수 있습니다.",
    )


class DiaryPatchRequest(RequestModel):
    date: CalendarDate | None = None
    content: str | None = Field(default=None, min_length=1, max_length=10000, pattern=r"\S")
    image_url: str | None = Field(default=None, alias="imageUrl")
    emotion: str | None = Field(default=None, max_length=40)
    visibility: Literal["PRIVATE", "GROUP", "PUBLIC"] | None = None

    @model_validator(mode="after")
    def no_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set & {"date", "content", "visibility"}):
            raise ValueError("날짜, 내용, 공개범위는 null일 수 없습니다.")
        return self


def diary_request_body(model):
    schema = model.model_json_schema()
    multipart = {**schema, "properties": {**schema["properties"], "image": {"type": "string", "format": "binary"}}}
    return {
        "requestBody": {
            "content": {"application/json": {"schema": schema}, "multipart/form-data": {"schema": multipart}}
        }
    }


async def parse_diary_request(request, model):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = validate_body(model, {key: value for key, value in form.items() if key != "image"})
        if "image" in form:
            if not isinstance(form["image"], UploadFile):
                raise HTTPException(422, detail={"message": "image는 파일이어야 합니다."})
            payload.image_url = await save_upload(form["image"], "diaries")
            payload._uploaded_image = True
        return payload
    if "application/json" not in content_type:
        raise HTTPException(415, detail={"message": "JSON 또는 multipart/form-data를 사용하세요."})
    return validate_body(model, await read_json(request))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DiaryResponse,
    openapi_extra=diary_request_body(DiaryCreateRequest),
)
async def create_diary(
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    payload = await parse_diary_request(request, DiaryCreateRequest)
    return await diaries_service.create_diary(session, payload, user_id)


@router.get("", response_model=list[DiaryResponse])
async def list_diaries(
    date: CalendarDate | None = None,
    target_user_id: int | None = Query(default=None, alias="userId"),
    group_id: int | None = Query(default=None, alias="groupId"),
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await diaries_service.list_diaries(session, user_id, date, target_user_id, group_id)


@router.get("/{diaryId}", response_model=DiaryResponse)
async def get_diary(
    diaryId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await diaries_service.get_diary(session, diaryId, user_id)


@router.patch("/{diaryId}", response_model=DiaryResponse, openapi_extra=diary_request_body(DiaryPatchRequest))
async def update_diary(
    diaryId: int,
    request: Request,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    await diaries_service.find_diary(session, diaryId, user_id)
    payload = await parse_diary_request(request, DiaryPatchRequest)
    return await diaries_service.update_diary(session, diaryId, payload, user_id)


@router.delete("/{diaryId}")
async def delete_diary(
    diaryId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await diaries_service.delete_diary(session, diaryId, user_id)
