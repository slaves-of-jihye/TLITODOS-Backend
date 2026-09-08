from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.infrastructure.database import GroupMember, Notification, Todo
from tests.conftest import (
    add_member,
    auth_headers,
    make_category,
    make_group,
    make_user,
)


async def setup_users(db):
    for user_id in (1, 2, 3):
        await make_user(db, user_id)
    await make_group(db, 10)
    await add_member(db, 10, 1, "LEADER")
    await add_member(db, 10, 2)
    return await make_category(db, 1)


async def new_todo(client, category_id, **fields):
    response = await client.post(
        "/api/v1/todos",
        headers=auth_headers(1),
        json={
            "title": "수학 과제",
            "description": "문제 10개 풀기",
            "categoryId": category_id,
            "startDate": "2026-09-08",
            "dueDate": "2026-09-10",
            **fields,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_date_range_is_inclusive_and_calendar_matches_other_user(client, db):
    category = await setup_users(db)
    todo = await new_todo(client, category.id, time="21:05")
    assert todo["startDate"] == "2026-09-08"
    assert todo["time"] == "21:05"
    assert "visibility" not in todo and "groupId" not in todo
    for day in range(7, 12):
        response = await client.get(
            "/api/v1/todos", params={"date": f"2026-09-{day:02}", "userId": 1}, headers=auth_headers(2)
        )
        assert [item["todoId"] for item in response.json()] == ([todo["todoId"]] if 8 <= day <= 10 else [])
    response = await client.get(
        "/api/v1/todos/daily-status", params={"month": "2026-09", "userId": 1, "groupId": 10}, headers=auth_headers(2)
    )
    assert [day["date"] for day in response.json() if day["incompleteCount"]] == [
        "2026-09-08",
        "2026-09-09",
        "2026-09-10",
    ]
    await client.patch(f"/api/v1/todos/{todo['todoId']}/complete", headers=auth_headers(1))
    status = (
        await client.get("/api/v1/todos/daily-status", params={"month": "2026-09"}, headers=auth_headers(1))
    ).json()
    assert all(day["incompleteCount"] == 0 for day in status)
    assert all(
        status[day - 1]["categoryStatuses"] == [{"categoryId": category.id, "isCompleted": True}] for day in (8, 9, 10)
    )
    denied = await client.get(
        "/api/v1/todos/daily-status", params={"month": "2026-09", "userId": 1, "groupId": 10}, headers=auth_headers(3)
    )
    assert denied.status_code == 403


async def test_change_deadline_does_not_move_start_and_can_clear_time(client, db):
    category = await setup_users(db)
    todo = await new_todo(client, category.id, dueDate="2026-09-08", time="00:00")
    result = await client.patch(
        f"/api/v1/todos/{todo['todoId']}", json={"dueDate": "2026-09-10", "time": None}, headers=auth_headers(1)
    )
    assert result.json()["startDate"] == "2026-09-08"
    assert result.json()["time"] is None
    assert (
        await client.patch(f"/api/v1/todos/{todo['todoId']}", json={"dueDate": "2026-09-07"}, headers=auth_headers(1))
    ).status_code == 422
    cleared = await client.patch(f"/api/v1/todos/{todo['todoId']}", json={"dueDate": None}, headers=auth_headers(1))
    assert cleared.status_code == 200
    assert (await client.get("/api/v1/todos", params={"date": "2026-09-09"}, headers=auth_headers(1))).json() == []


async def test_range_crosses_months_and_leap_day(client, db):
    category = await setup_users(db)
    await new_todo(client, category.id, startDate="2028-02-28", dueDate="2028-03-01")
    feb = (await client.get("/api/v1/todos/daily-status", params={"month": "2028-02"}, headers=auth_headers(1))).json()
    march = (
        await client.get("/api/v1/todos/daily-status", params={"month": "2028-03"}, headers=auth_headers(1))
    ).json()
    assert feb[-2]["incompleteCount"] == feb[-1]["incompleteCount"] == march[0]["incompleteCount"] == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"title": "x" * 41},
        {"title": "  "},
        {"description": "x" * 101},
        {"time": "21:03"},
        {"time": "21:05:01"},
        {"time": "21:05+09:00"},
        {"timezone": "invalid/zone"},
        {"startDate": "2026-02-30"},
        {"startDate": "2026-09-11", "dueDate": "2026-09-10"},
        {"groupId": 10},
        {"visibility": "PRIVATE"},
        {"isRoutine": True},
    ],
)
async def test_todo_contract_validation(client, db, fields):
    category = await setup_users(db)
    response = await client.post(
        "/api/v1/todos", json={"title": "할일", "categoryId": category.id, **fields}, headers=auth_headers(1)
    )
    assert response.status_code == 422
    assert await db.scalar(select(func.count(Todo.id))) == 0


async def test_patch_checks_category_ownership_and_nonnull_fields(client, db):
    category = await setup_users(db)
    other = await make_category(db, 2)
    todo = await new_todo(client, category.id)
    url = f"/api/v1/todos/{todo['todoId']}"
    assert (await client.patch(url, json={"categoryId": other.id}, headers=auth_headers(1))).status_code == 404
    for field in ("title", "description", "categoryId", "startDate", "importance", "x"):
        assert (await client.patch(url, json={field: None}, headers=auth_headers(1))).status_code == 422


@pytest.mark.parametrize(
    "start,end,rule,expected",
    [
        (
            "2026-09-09",
            "2026-10-01",
            {"frequency": "WEEKLY", "interval": 2, "weekdays": [1, 3, 5]},
            ["2026-09-09", "2026-09-11", "2026-09-21", "2026-09-23", "2026-09-25"],
        ),
        (
            "2026-09-13",
            "2026-09-28",
            {"frequency": "WEEKLY", "interval": 2, "weekdays": [7]},
            ["2026-09-13", "2026-09-27"],
        ),
        ("2026-01-31", "2026-05-31", {"frequency": "MONTHLY"}, ["2026-01-31", "2026-03-31", "2026-05-31"]),
        ("2028-02-29", "2037-02-28", {"frequency": "YEARLY"}, ["2028-02-29", "2032-02-29", "2036-02-29"]),
        ("2026-09-08", "2029-09-08", {"frequency": "YEARLY"}, ["2026-09-08", "2027-09-08", "2028-09-08", "2029-09-08"]),
        ("2026-09-08", "2026-09-21", {"frequency": "WEEKLY"}, ["2026-09-08", "2026-09-15"]),
    ],
)
async def test_recurrence_rules(client, db, start, end, rule, expected):
    category = await setup_users(db)
    payload = {
        "requestId": str(uuid4()),
        "title": "운동",
        "categoryId": category.id,
        "startDate": start,
        "endDate": end,
        "recurrence": rule,
        "time": "23:55",
    }
    response = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert response.status_code == 201, response.text
    assert [item["dueDate"] for item in response.json()["occurrences"]] == expected
    todos = list(await db.scalars(select(Todo)))
    assert all(todo.start_date.isoformat() == todo.due_date for todo in todos)
    assert all(todo.time.hour == 23 for todo in todos)


@pytest.mark.parametrize(
    "rule",
    [
        {"frequency": "WEEKLY", "weekdays": []},
        {"frequency": "WEEKLY", "weekdays": [True]},
        {"frequency": "WEEKLY", "interval": 0},
        {"frequency": "WEEKLY", "interval": 3},
        {"frequency": "MONTHLY", "weekdays": [1]},
        {"frequency": "YEARLY", "interval": 2},
        {"frequency": "BIWEEKLY"},
    ],
)
async def test_recurrence_rejects_ambiguous_rules(client, db, rule):
    category = await setup_users(db)
    response = await client.post(
        "/api/v1/todos/routines",
        json={
            "requestId": str(uuid4()),
            "title": "운동",
            "categoryId": category.id,
            "startDate": "2026-09-08",
            "endDate": "2026-09-30",
            "recurrence": rule,
        },
        headers=auth_headers(1),
    )
    assert response.status_code == 422


async def test_convert_preserves_source_id_and_delete_removes_whole_series(client, db):
    category = await setup_users(db)
    original = await new_todo(client, category.id)
    follower = await new_todo(client, category.id, title="후속")
    await client.post(
        f"/api/v1/todos/{follower['todoId']}/dependencies",
        json={"dependencyTodoId": original["todoId"]},
        headers=auth_headers(1),
    )
    payload = {
        "requestId": str(uuid4()),
        "startDate": "2026-09-09",
        "endDate": "2026-09-11",
        "recurrence": {"frequency": "DAILY"},
    }
    endpoint = f"/api/v1/todos/{original['todoId']}/routine"
    result = await client.post(endpoint, json=payload, headers=auth_headers(1))
    assert result.status_code == 201, result.text
    assert result.json()["occurrences"][0]["todoId"] == original["todoId"]
    assert await db.scalar(select(func.count(Todo.id))) == 4
    assert (await client.post(endpoint, json=payload, headers=auth_headers(1))).json() == result.json()
    routine_id = result.json()["routineId"]
    assert (await client.delete(f"/api/v1/todos/routines/{routine_id}", headers=auth_headers(2))).status_code == 404
    await client.patch(f"/api/v1/todos/{original['todoId']}/complete", headers=auth_headers(1))
    # Deleting from an occurrence's UI also means deleting the whole routine.
    deleted = await client.delete(f"/api/v1/todos/{original['todoId']}", headers=auth_headers(1))
    assert deleted.json()["deletedCount"] == 3
    assert await db.scalar(select(func.count(Todo.id))) == 1
    remaining = (await client.get(f"/api/v1/todos/{follower['todoId']}", headers=auth_headers(1))).json()
    assert remaining["dependencies"] == []
    assert (await client.post(endpoint, json=payload, headers=auth_headers(1))).status_code == 410
    assert (await client.delete(f"/api/v1/todos/routines/{routine_id}", headers=auth_headers(1))).json()[
        "deletedCount"
    ] == 0


async def test_dependencies_can_be_replaced_unchecked_and_reject_cycles(client, db):
    category = await setup_users(db)
    a, b, c = [await new_todo(client, category.id, title=title) for title in ("a", "b", "c")]

    async def set_deps(todo, ids):
        return await client.put(
            f"/api/v1/todos/{todo['todoId']}/dependencies", json={"dependencyTodoIds": ids}, headers=auth_headers(1)
        )

    assert (await set_deps(b, [a["todoId"]])).status_code == 200
    assert (await set_deps(c, [b["todoId"]])).status_code == 200
    assert (await set_deps(a, [c["todoId"]])).status_code == 422
    assert (await set_deps(a, [a["todoId"]])).status_code == 422
    assert (await set_deps(a, [9999])).status_code == 404
    removed = await client.delete(f"/api/v1/todos/{b['todoId']}/dependencies/{a['todoId']}", headers=auth_headers(1))
    assert removed.json()["dependencies"] == []
    assert (await set_deps(a, [c["todoId"]])).status_code == 200


async def test_profile_and_category_partial_updates(client, db):
    category = await setup_users(db)
    assert (await client.patch("/api/v1/users/me", json={"bio": "가" * 30}, headers=auth_headers(1))).status_code == 200
    assert (await client.patch("/api/v1/users/me", json={"bio": "가" * 31}, headers=auth_headers(1))).status_code == 422
    assert (
        await client.patch(
            "/api/v1/users/me",
            data={"bio": "가" * 31},
            files={"image": ("test.png", b"not-an-image")},
            headers=auth_headers(1),
        )
    ).status_code == 422
    named = await client.patch(f"/api/v1/categories/{category.id}", json={"name": "프로젝트"}, headers=auth_headers(1))
    assert named.json()["color"] == "#123456"
    colored = await client.patch(
        f"/api/v1/categories/{category.id}", json={"color": "#654321"}, headers=auth_headers(1)
    )
    assert colored.json()["name"] == "프로젝트"
    assert (
        await client.patch(f"/api/v1/categories/{category.id}", json={"color": None}, headers=auth_headers(1))
    ).status_code == 422


async def test_google_relogin_preserves_edited_profile(db):
    from app.application.auth_service import upsert_google_user

    user = await make_user(db, 1, name="직접 설정한 이름")
    user.google_sub = "google-sub"
    user.profile_image_url = "/uploads/profiles/mine.png"
    await db.commit()
    found = await upsert_google_user(
        db, {"googleSub": "google-sub", "name": "구글 이름", "picture": "https://example.com/google.png"}
    )
    assert found.name == "직접 설정한 이름"
    assert found.profile_image_url == "/uploads/profiles/mine.png"


async def test_group_rename_and_bulk_removal_are_authorized_and_atomic(client, db):
    await setup_users(db)
    assert (
        await client.patch("/api/v1/groups/10", json={"name": "새 그룹"}, headers=auth_headers(2))
    ).status_code == 403
    renamed = await client.patch("/api/v1/groups/10", json={"name": "새 그룹"}, headers=auth_headers(1))
    assert renamed.json()["name"] == "새 그룹"
    for ids, code in [([2, 3], 404), ([1, 2], 400)]:
        result = await client.post("/api/v1/groups/10/members/remove", json={"userIds": ids}, headers=auth_headers(1))
        assert result.status_code == code
        assert await db.scalar(select(func.count(GroupMember.id))) == 2
    removed = await client.post("/api/v1/groups/10/members/remove", json={"userIds": [2, 2]}, headers=auth_headers(1))
    assert removed.json()["removedUserIds"] == [2]


async def test_bet_actor_and_recipient_roles_and_notifications(client, db):
    category = await setup_users(db)
    todo = await new_todo(client, category.id)
    url = f"/api/v1/todos/{todo['todoId']}/bets"
    assert (
        await client.post(url, json={"content": "내기", "requesterId": 3}, headers=auth_headers(2))
    ).status_code == 422
    assert (await client.post(url, json={"content": "내기"}, headers=auth_headers(1))).status_code == 400
    response = await client.post(url, json={"content": "초코에몽"}, headers=auth_headers(2))
    assert response.status_code == 201
    bet = response.json()
    assert bet["requesterId"] == 2
    status_url = f"/api/v1/bets/{bet['betId']}/status"
    assert (await client.patch(status_url, json={"status": "ACCEPTED"}, headers=auth_headers(2))).status_code == 404
    assert (await client.patch(status_url, json={"status": "ACCEPTED"}, headers=auth_headers(1))).status_code == 200
    assert (await client.patch(status_url, json={"status": "REJECTED"}, headers=auth_headers(1))).status_code == 409
    assert (await client.get(f"/api/v1/bets/{bet['betId']}", headers=auth_headers(3))).status_code == 404
    items = (
        await client.get("/api/v1/notifications", params={"type": "BET_REQUESTED"}, headers=auth_headers(1))
    ).json()["items"]
    assert items[0]["actor"]["userId"] == 2
    assert items[0]["bet"]["status"] == "ACCEPTED"


async def test_completion_events_are_deduplicated_and_paginated(client, db):
    category = await setup_users(db)
    await make_group(db, 20)
    await add_member(db, 20, 1)
    await add_member(db, 20, 2)
    for index in range(3):
        todo = await new_todo(client, category.id, title=str(index))
        for _ in range(2):
            assert (
                await client.patch(f"/api/v1/todos/{todo['todoId']}/complete", headers=auth_headers(1))
            ).status_code == 200
    assert await db.scalar(select(func.count(Notification.id))) == 3
    assert all(todo.completed_at is not None for todo in await db.scalars(select(Todo)))
    page = (await client.get("/api/v1/notifications", params={"limit": 2}, headers=auth_headers(2))).json()
    assert len(page["items"]) == 2 and page["nextCursor"]
    last = (
        await client.get("/api/v1/notifications", params={"cursor": page["nextCursor"]}, headers=auth_headers(2))
    ).json()
    assert len(last["items"]) == 1 and last["nextCursor"] is None
    notification_id = page["items"][0]["notificationId"]
    assert (
        await client.patch(f"/api/v1/notifications/{notification_id}/read", headers=auth_headers(3))
    ).status_code == 404
    assert (await client.patch(f"/api/v1/notifications/{notification_id}/read", headers=auth_headers(2))).json()[
        "readAt"
    ]
    assert (await client.get("/api/v1/notifications", headers=auth_headers(3))).json()["items"] == []
