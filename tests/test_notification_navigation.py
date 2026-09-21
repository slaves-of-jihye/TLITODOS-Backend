from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, event

from app.infrastructure.database import GroupMember
from tests.conftest import add_member, auth_headers, make_group, make_todo
from tests.test_figma_contract import new_todo, setup_users

URL = "/api/v1/notifications"


async def test_shared_group_navigation_is_deterministic_and_paginated(client, db, engine):
    category = await setup_users(db)
    for group_id, members in ((20, [1, 2]), (5, [1])):
        await make_group(db, group_id)
        for user_id in members:
            await add_member(db, group_id, user_id)
    for index in range(3):
        todo = await new_todo(client, category.id, title=str(index))
        await client.patch(f"/api/v1/todos/{todo['todoId']}/complete", headers=auth_headers(1))
    queries = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        queries.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        response = await client.get(URL, params={"limit": 2}, headers=auth_headers(2))
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert len(queries) == 1  # No per-notification group/Todo lookups.
    page = response.json()
    assert len(page["items"]) == 2 and page["nextCursor"] is not None
    last = (await client.get(URL, params={"cursor": page["nextCursor"]}, headers=auth_headers(2))).json()
    items = page["items"] + last["items"]
    assert len({item["notificationId"] for item in items}) == 3
    assert last["nextCursor"] is None
    for item in items:
        assert item["groupId"] == 10  # Group 5 belongs to the actor only.
        assert item["todo"]["userId"] == 1
        assert item["todo"]["startDate"] == "2026-09-08"
        assert item["todo"]["dueDate"] == "2026-09-10"
        calendar = await client.get(
            "/api/v1/todos",
            params={"userId": item["todo"]["userId"], "groupId": item["groupId"], "date": item["todo"]["startDate"]},
            headers=auth_headers(2),
        )
        assert calendar.status_code == 200
        assert item["todo"]["todoId"] in [row["todoId"] for row in calendar.json()]
    await db.execute(delete(GroupMember).where(GroupMember.group_id == 10, GroupMember.user_id == 2))
    await db.commit()
    assert all(item["groupId"] == 20 for item in (await client.get(URL, headers=auth_headers(2))).json()["items"])
    await db.execute(delete(GroupMember).where(GroupMember.group_id == 20, GroupMember.user_id == 2))
    await db.commit()
    assert (await client.get(URL, headers=auth_headers(2))).json()["items"] == []


@pytest.mark.parametrize("requester,expected_group", [(2, 10), (3, None)])
async def test_bet_navigation_targets_todo_owner_not_actor(client, db, requester, expected_group):
    category = await setup_users(db)
    todo = await new_todo(client, category.id, dueDate=None)
    response = await client.post(
        f"/api/v1/todos/{todo['todoId']}/bets", json={"content": "내기"}, headers=auth_headers(requester)
    )
    assert response.status_code == 201
    item = (await client.get(URL, headers=auth_headers(1))).json()["items"][0]
    assert item["actor"]["userId"] == requester
    assert item["groupId"] == expected_group
    assert item["todo"]["userId"] == 1
    assert item["todo"]["startDate"] == "2026-09-08"
    assert item["todo"]["dueDate"] is None


async def test_routine_notification_contains_occurrence_date(client, db):
    category = await setup_users(db)
    response = await client.post(
        "/api/v1/todos/routines",
        json={
            "requestId": str(uuid4()),
            "title": "운동",
            "categoryId": category.id,
            "startDate": "2026-09-08",
            "endDate": "2026-09-10",
        },
        headers=auth_headers(1),
    )
    assert response.status_code == 201
    todos = (await client.get("/api/v1/todos", params={"date": "2026-09-09"}, headers=auth_headers(1))).json()
    assert len(todos) == 1
    await client.patch(f"/api/v1/todos/{todos[0]['todoId']}/complete", headers=auth_headers(1))
    item = (await client.get(URL, headers=auth_headers(2))).json()["items"][0]
    assert item["todo"]["startDate"] == item["todo"]["dueDate"] == "2026-09-09"


@pytest.mark.parametrize("due_date,expected_start", [("2026-09-08", "2026-09-08"), (None, "2026-09-01")])
async def test_legacy_dates_use_same_fallback_as_todo_detail(client, db, due_date, expected_start):
    category = await setup_users(db)
    todo = await make_todo(db, 1, category.id)
    todo.due_date = due_date
    todo.created_at = datetime(2026, 9, 1, 12)
    await db.commit()
    await client.patch(f"/api/v1/todos/{todo.id}/complete", headers=auth_headers(1))
    item = (await client.get(URL, headers=auth_headers(2))).json()["items"][0]
    detail = (await client.get(f"/api/v1/todos/{todo.id}", headers=auth_headers(2))).json()
    assert item["todo"]["startDate"] == detail["startDate"] == expected_start
    assert item["todo"]["dueDate"] == detail["dueDate"] == due_date


async def test_diary_notifications_keep_nullable_todo_and_group_hint(client, db):
    await setup_users(db)
    response = await client.post(
        "/api/v1/diaries",
        json={"content": "일기", "date": "2026-09-08", "visibility": "PUBLIC"},
        headers=auth_headers(1),
    )
    assert response.status_code == 201
    item = (await client.get(URL, headers=auth_headers(2))).json()["items"][0]
    assert item["groupId"] == 10
    assert item["todo"] is None
    assert item["diaryId"] == response.json()["diaryId"]
