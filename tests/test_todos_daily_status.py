import pytest

from tests.conftest import auth_headers, make_category, make_todo, make_user


async def test_daily_status_returns_every_day_and_category_completion(client, db):
    await make_user(db, 1, "owner")
    first_category = await make_category(db, 1, name="first")
    second_category = await make_category(db, 1, name="second")
    empty_category = await make_category(db, 1, name="empty")

    completed = await make_todo(db, 1, first_category.id, title="completed")
    incomplete = await make_todo(db, 1, first_category.id, title="incomplete")
    all_completed = await make_todo(db, 1, second_category.id, title="all-completed")
    next_day = await make_todo(db, 1, first_category.id, title="next-day")
    outside_month = await make_todo(db, 1, first_category.id, title="outside-month")

    completed.due_date = "2026-09-01"
    completed.is_completed = True
    incomplete.due_date = "2026-09-01"
    all_completed.due_date = "2026-09-01"
    all_completed.is_completed = True
    next_day.due_date = "2026-09-02"
    next_day.is_completed = True
    outside_month.due_date = "2026-10-01"
    await db.commit()

    response = await client.get(
        "/api/v1/todos/daily-status",
        params={"month": "2026-09"},
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    days = response.json()
    assert len(days) == 30
    assert days[0] == {
        "date": "2026-09-01",
        "incompleteCount": 1,
        "categoryStatuses": [
            {"categoryId": first_category.id, "isCompleted": True},
            {"categoryId": second_category.id, "isCompleted": True},
        ],
    }
    assert days[1] == {
        "date": "2026-09-02",
        "incompleteCount": 0,
        "categoryStatuses": [{"categoryId": first_category.id, "isCompleted": True}],
    }
    assert days[-1] == {
        "date": "2026-09-30",
        "incompleteCount": 0,
        "categoryStatuses": [],
    }
    assert empty_category.id not in {category["categoryId"] for day in days for category in day["categoryStatuses"]}


async def test_daily_status_only_counts_authenticated_users_todos(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "other")
    requester_category = await make_category(db, 1)
    other_category = await make_category(db, 2)
    requester_todo = await make_todo(db, 1, requester_category.id)
    other_todo = await make_todo(db, 2, other_category.id)
    requester_todo.due_date = "2026-09-01"
    other_todo.due_date = "2026-09-01"
    await db.commit()

    response = await client.get(
        "/api/v1/todos/daily-status",
        params={"month": "2026-09"},
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    assert response.json()[0]["incompleteCount"] == 1
    assert response.json()[0]["categoryStatuses"] == [{"categoryId": requester_category.id, "isCompleted": False}]


async def test_daily_status_rejects_invalid_month(client):
    response = await client.get(
        "/api/v1/todos/daily-status",
        params={"month": "2026-13"},
        headers=auth_headers(1),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "completion_states", [[], [False], [True], [False, False], [True, True], [True, False], [False, True]]
)
async def test_category_completion_uses_any_completed_todo(client, db, completion_states):
    await make_user(db, 1)
    category = await make_category(db, 1)
    for completed in completion_states:
        todo = await make_todo(db, 1, category.id)
        todo.due_date = "2026-09-11"
        todo.is_completed = completed
    await db.commit()
    response = await client.get("/api/v1/todos/daily-status", params={"month": "2026-09"}, headers=auth_headers(1))
    assert response.status_code == 200
    day = response.json()[10]
    assert day["categoryStatuses"] == (
        [{"categoryId": category.id, "isCompleted": any(completion_states)}] if completion_states else []
    )
    assert day["incompleteCount"] == completion_states.count(False)
