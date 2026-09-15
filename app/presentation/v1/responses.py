"""Response shapes shared with the generated frontend OpenAPI contract."""

from datetime import date

from pydantic import BaseModel


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


class BetResponse(BaseModel):
    betId: int
    todoId: int
    content: str
    requesterId: int
    status: str
    proofImageUrl: str | None
    isVerified: bool


class ActorResponse(BaseModel):
    userId: int
    name: str
    profileImageUrl: str | None


class TodoPreviewResponse(BaseModel):
    todoId: int
    title: str
    description: str


class NotificationResponse(BaseModel):
    notificationId: int
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
