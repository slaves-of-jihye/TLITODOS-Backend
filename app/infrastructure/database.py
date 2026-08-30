from __future__ import annotations

import os
import secrets
import string
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.shared.fonts import DEFAULT_FONT


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://tlitodos:tlitodos@127.0.0.1:5432/tlitodos",
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    profile_image_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_discord_linked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discord_alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    discord_username: Mapped[str | None] = mapped_column(String(120))
    font: Mapped[str] = mapped_column(String(32), default=DEFAULT_FONT, nullable=False)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(512), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    is_deletable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    invite_code: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=False)


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    importance: Mapped[str] = mapped_column(String(20), default="NONE", nullable=False)
    hardship: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String(40))
    visibility: Mapped[str] = mapped_column(String(20), default="PRIVATE", nullable=False)
    x: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    y: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    is_routine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subtasks: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    dependencies: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    todo_id: Mapped[int] = mapped_column(ForeignKey("todos.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    requester_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    proof_image_url: Mapped[str | None] = mapped_column(String(500))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Diary(Base):
    __tablename__ = "diaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    emotion: Mapped[str | None] = mapped_column(String(40))
    visibility: Mapped[str] = mapped_column(String(20), default="PRIVATE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255)"))
        await connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)"))
        await connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS font VARCHAR(32) NOT NULL DEFAULT 'KYOBO_HANDWRITING_2019'")
        )
        await connection.execute(text("ALTER TABLE auth_tokens ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP"))
        await connection.execute(text("ALTER TABLE auth_tokens ALTER COLUMN token TYPE VARCHAR(512)"))
        await connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub_unique ON users (google_sub) WHERE google_sub IS NOT NULL"))
        await connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users (email) WHERE email IS NOT NULL"))

    async with SessionLocal() as session:
        if await session.get(User, 1) is None:
            session.add(
                User(
                    id=1,
                    google_sub="local-dev-user",
                    email="local-dev@example.com",
                    name="이형민",
                    profile_image_url="https://example.com/profile.jpg",
                    bio="자기소개 메모입니다.",
                )
            )
            await session.flush()

        await ensure_user_defaults(session, 1)

        await session.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1), true)"))
        await session.execute(text("SELECT setval(pg_get_serial_sequence('categories', 'id'), COALESCE((SELECT MAX(id) FROM categories), 1), true)"))
        await session.execute(text("SELECT setval(pg_get_serial_sequence('groups', 'id'), COALESCE((SELECT MAX(id) FROM groups), 1), true)"))
        await session.commit()


async def create_invite_code(session: AsyncSession) -> str:
    alphabet = string.ascii_lowercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = await session.scalar(select(Group.id).where(Group.invite_code == code))
        if exists is None:
            return code


async def ensure_user_defaults(session: AsyncSession, user_id: int) -> None:
    existing_categories = await session.scalar(select(func.count(Category.id)).where(Category.user_id == user_id))
    if existing_categories == 0:
        session.add_all(
            [
                Category(user_id=user_id, name="취미", color="#FF5733", is_deletable=False),
                Category(user_id=user_id, name="할일", color="#33FF57", is_deletable=True),
            ]
        )

    existing_personal_group = await session.scalar(
        select(GroupMember.id).where(GroupMember.user_id == user_id, GroupMember.role == "LEADER")
    )
    if existing_personal_group is None:
        group = Group(
            name="개인 그룹",
            description="개인 할일 관리를 위한 기본 그룹입니다.",
            invite_code=await create_invite_code(session),
        )
        session.add(group)
        await session.flush()
        session.add(GroupMember(group_id=group.id, user_id=user_id, role="LEADER"))


def user_to_response(user: User) -> dict:
    return {
        "userId": user.id,
        "name": user.name,
        "profileImageUrl": user.profile_image_url,
        "bio": user.bio,
        "font": user.font,
        "isDiscordLinked": user.is_discord_linked,
        "discordAlertEnabled": user.discord_alert_enabled,
    }


def category_to_response(category: Category) -> dict:
    return {
        "categoryId": category.id,
        "name": category.name,
        "color": category.color,
        "isDeletable": category.is_deletable,
    }


def todo_to_response(todo: Todo) -> dict:
    return {
        "todoId": todo.id,
        "userId": todo.user_id,
        "title": todo.title,
        "categoryId": todo.category_id,
        "importance": todo.importance,
        "hardship": todo.hardship,
        "dueDate": todo.due_date,
        "visibility": todo.visibility,
        "groupId": todo.group_id,
        "x": todo.x,
        "y": todo.y,
        "isRoutine": todo.is_routine,
        "isCompleted": todo.is_completed,
        "subtasks": todo.subtasks,
        "dependencies": todo.dependencies,
        "createdAt": todo.created_at.isoformat() if todo.created_at else None,
        "completedAt": todo.completed_at.isoformat() if todo.completed_at else None,
    }


def bet_to_response(bet: Bet) -> dict:
    return {
        "betId": bet.id,
        "todoId": bet.todo_id,
        "content": bet.content,
        "requesterId": bet.requester_id,
        "status": bet.status,
        "proofImageUrl": bet.proof_image_url,
        "isVerified": bet.is_verified,
    }


def diary_to_response(diary: Diary) -> dict:
    return {
        "diaryId": diary.id,
        "userId": diary.user_id,
        "content": diary.content,
        "imageUrl": diary.image_url,
        "emotion": diary.emotion,
        "visibility": diary.visibility,
        "createdAt": diary.created_at.isoformat() if diary.created_at else None,
    }
