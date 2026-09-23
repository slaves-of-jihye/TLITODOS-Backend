"""Response shapes shared with the generated frontend OpenAPI contract."""

from datetime import date

from pydantic import BaseModel

from app.shared.time_format import TimeFormat


class UserResponse(BaseModel):
    userId: int
    name: str
    profileImageUrl: str | None
    bio: str
    font: str
    timeFormat: TimeFormat
    isDiscordLinked: bool
    discordAlertEnabled: bool


class TimeFormatSettingResponse(BaseModel):
    success: bool
    timeFormat: TimeFormat


class NotificationsReadAllResponse(BaseModel):
    success: bool
    updatedCount: int


class TodoResponse(BaseModel):
    todoId: int
    userId: int
    title: str
    description: str
    categoryId: int
    startDate: date
    dueDate: date | None
    time: str | None
    timezone: str
    importance: str
    hardship: int
    x: float
    y: float
    isRoutine: bool
    routineId: int | None
    isCompleted: bool
    subtasks: list[dict]
    dependencies: list[int]
    createdAt: str | None
    completedAt: str | None


class CategoryStatusResponse(BaseModel):
    categoryId: int
    isCompleted: bool


class DailyStatusResponse(BaseModel):
    date: date
    incompleteCount: int
    categoryStatuses: list[CategoryStatusResponse]


class DiaryResponse(BaseModel):
    diaryId: int
    userId: int
    date: date
    content: str
    imageUrl: str | None
    emotion: str | None
    visibility: str
    createdAt: str | None


class ActorResponse(BaseModel):
    userId: int
    name: str
    profileImageUrl: str | None


class TodoPreviewResponse(BaseModel):
    todoId: int
    userId: int
    title: str
    description: str
    startDate: date
    dueDate: date | None


class BetResponse(BaseModel):
    betId: int
    todoId: int
    content: str
    requesterId: int
    requesterName: str | None
    todo: TodoPreviewResponse
    status: str
    proofImageUrl: str | None
    isVerified: bool


class NotificationResponse(BaseModel):
    notificationId: int
    groupId: int | None
    type: str
    actor: ActorResponse
    todo: TodoPreviewResponse | None
    diaryId: int | None
    bet: BetResponse | None
    createdAt: str
    readAt: str | None


class NotificationsPageResponse(BaseModel):
    items: list[NotificationResponse]
    nextCursor: int | None


class NotificationUnreadStatusResponse(BaseModel):
    TODO_COMPLETED: bool
    DIARY_CREATED: bool
    BET_REQUESTED: bool


class RoutineDeleteResponse(BaseModel):
    success: bool
    routineId: int
    deletedCount: int


class RoutineResponse(BaseModel):
    routineId: int
    definition: dict
