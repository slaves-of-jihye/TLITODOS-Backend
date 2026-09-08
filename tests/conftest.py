import os
from uuid import uuid4

import pytest_asyncio
from fastapi import Header
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.infrastructure.database import (
    Base,
    Category,
    Group,
    GroupMember,
    Todo,
    User,
    get_session,
)
from app.main import app
from app.shared.auth import require_access_token


@compiles(JSONB, "sqlite")
def _compile_jsonb_as_json_for_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest_asyncio.fixture
async def engine():
    postgres_url = os.getenv("TLITODOS_TEST_DATABASE_URL")
    if postgres_url:
        url = make_url(postgres_url)
        if url.host != "127.0.0.1" or url.database != "figma_qa":
            raise RuntimeError("PostgreSQL tests only run on the local disposable figma_qa database")
        schema = f"qa_{uuid4().hex}"
        admin = create_async_engine(postgres_url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        test_engine = create_async_engine(postgres_url, connect_args={"server_settings": {"search_path": schema}})
        try:
            async with test_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            yield test_engine
        finally:
            await test_engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
        return
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    async def override_require_access_token(x_test_user_id: int = Header(alias="X-Test-User-Id")):
        return x_test_user_id

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[require_access_token] = override_require_access_token

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


def auth_headers(user_id: int) -> dict:
    return {"X-Test-User-Id": str(user_id)}


async def make_user(db, user_id: int, name: str = "user", bio: str = "") -> User:
    user = User(id=user_id, name=name, bio=bio)
    db.add(user)
    await db.commit()
    return user


async def make_group(db, group_id: int, name: str = "group") -> Group:
    group = Group(id=group_id, name=name, invite_code=f"code{group_id:04d}")
    db.add(group)
    await db.commit()
    return group


async def add_member(db, group_id: int, user_id: int, role: str = "MEMBER") -> GroupMember:
    member = GroupMember(group_id=group_id, user_id=user_id, role=role)
    db.add(member)
    await db.commit()
    return member


async def make_category(db, user_id: int, name: str = "category", is_deletable: bool = True) -> Category:
    category = Category(user_id=user_id, name=name, color="#123456", is_deletable=is_deletable)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def make_todo(
    db,
    user_id: int,
    category_id: int,
    group_id: int | None = None,
    title: str = "todo",
) -> Todo:
    todo = Todo(
        user_id=user_id,
        category_id=category_id,
        group_id=group_id,
        title=title,
        subtasks=[],
        dependencies=[],
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return todo
