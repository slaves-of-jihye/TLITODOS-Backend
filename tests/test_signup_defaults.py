from uuid import uuid4

from sqlalchemy import func, select

from app.application import auth_service
from app.infrastructure.database import (
    Category,
    Group,
    GroupMember,
    User,
    ensure_user_defaults,
)
from tests.conftest import add_member, auth_headers, make_group, make_user


async def test_signup_has_categories_but_no_group_and_can_create_todos(client, db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "signup-test-only-secret-not-for-production-1234567890")
    async def google_profile(_):
        return {"googleSub": "new-account", "name": "신규 사용자", "email": "signup@example.com", "isNewUser": False}

    monkeypatch.setattr(auth_service, "fetch_google_profile", google_profile)
    login = await client.post("/api/v1/auth/google", json={"googleAccessToken": "mock-google-token"})
    assert login.status_code == 200
    assert login.json()["isNewUser"] is True
    user = await db.scalar(select(User).where(User.google_sub == "new-account"))
    categories = list(await db.scalars(select(Category).where(Category.user_id == user.id)))
    assert {category.name for category in categories} == {"취미", "할일"}
    assert await db.scalar(select(func.count(Group.id))) == 0
    assert await db.scalar(select(func.count(GroupMember.id))) == 0
    headers = auth_headers(user.id)
    assert (await client.get("/api/v1/groups", headers=headers)).json() == []
    category_id = next(category.id for category in categories if category.name == "할일")

    todo = await client.post(
        "/api/v1/todos", headers=headers, json={"title": "그룹 없는 할일", "categoryId": category_id}
    )
    assert todo.status_code == 201, todo.text
    routine = await client.post(
        "/api/v1/todos/routines",
        headers=headers,
        json={
            "requestId": str(uuid4()),
            "title": "그룹 없는 루틴",
            "categoryId": category_id,
            "startDate": "2026-09-08",
            "endDate": "2026-09-08",
        },
    )
    assert routine.status_code == 201, routine.text
    relogin = await client.post("/api/v1/auth/google", json={"googleAccessToken": "mock-google-token"})
    assert relogin.status_code == 200
    assert relogin.json()["isNewUser"] is False
    assert await db.scalar(select(func.count(Category.id))) == 2
    assert await db.scalar(select(func.count(Group.id))) == 0

    # Only the explicit group-create endpoint creates a group and its leader.
    created = await client.post("/api/v1/groups", headers=headers, json={"name": "직접 만든 그룹"})
    assert created.status_code == 201, created.text
    member = await db.scalar(select(GroupMember).where(GroupMember.group_id == created.json()["groupId"]))
    assert member.user_id == user.id and member.role == "LEADER"
    assert await db.scalar(select(func.count(Group.id))) == 1


async def test_default_initialization_preserves_existing_groups_without_creating_more(db):
    await make_user(db, 1)
    await make_user(db, 2)
    await make_group(db, 10, "개인 그룹")
    await add_member(db, 10, 1, "LEADER")
    await add_member(db, 10, 2)
    for _ in range(2):
        for user_id in (1, 2):
            await ensure_user_defaults(db, user_id)
        await db.commit()
    assert await db.scalar(select(func.count(Group.id))) == 1
    assert await db.scalar(select(func.count(GroupMember.id))) == 2
    assert await db.scalar(select(func.count(Category.id))) == 4
    assert (await db.get(Group, 10)).name == "개인 그룹"
