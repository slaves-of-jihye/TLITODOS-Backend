from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.infrastructure.database import Todo, TodoRoutine
from tests.conftest import auth_headers, make_category, make_todo, make_user

URL = "/api/v1/todos/routines"


async def setup(db):
    await make_user(db, 1)
    category = await make_category(db, 1)
    return {
        "title": "운동",
        "categoryId": category.id,
        "startDate": "2026-11-02",
        "endDate": "2026-11-08",
    }


async def create(client, fields):
    response = await client.post(URL, json={"requestId": str(uuid4()), **fields}, headers=auth_headers(1))
    assert response.status_code == 201, response.text
    return response.json()


def ids_by_day(result):
    return {row["dueDate"]: row["todoId"] for row in result["occurrences"]}


async def assert_dependencies(client, result, expected):
    for day, todo_id in ids_by_day(result).items():
        response = await client.get(f"/api/v1/todos/{todo_id}", headers=auth_headers(1))
        assert response.status_code == 200
        assert response.json()["dependencies"] == sorted(expected[day])


async def test_daily_series_matches_same_day_and_retains_ordinary_dependencies(client, db):
    fields = await setup(db)
    predecessor = await create(client, fields)
    prior = ids_by_day(predecessor)
    ordinary = await make_todo(db, 1, fields["categoryId"])
    # Any occurrence selects its series, not just that particular day.
    result = await create(client, {**fields, "dependencyTodoIds": [prior["2026-11-05"], ordinary.id]})
    await assert_dependencies(client, result, {day: [prior[day], ordinary.id] for day in prior})
    for day, todo_id in ids_by_day(result).items():
        listed = (await client.get("/api/v1/todos", params={"date": day}, headers=auth_headers(1))).json()
        ids = [item["todoId"] for item in listed]
        assert ids.index(prior[day]) < ids.index(todo_id)


async def test_missing_weekdays_range_and_deleted_occurrence_are_skipped(client, db):
    fields = await setup(db)
    predecessor = await create(client, {**fields, "weekdays": [1, 3, 5]})
    prior = ids_by_day(predecessor)
    assert (await client.delete(f"/api/v1/todos/{prior.pop('2026-11-04')}", headers=auth_headers(1))).status_code == 200
    result = await create(
        client,
        {
            **fields,
            "startDate": "2026-11-01",
            "endDate": "2026-11-10",
            "dependencyTodoIds": [prior["2026-11-02"], prior["2026-11-06"]],
        },
    )
    await assert_dependencies(client, result, {day: [prior[day]] if day in prior else [] for day in ids_by_day(result)})


@pytest.mark.parametrize(
    "start,end,frequency",
    [
        ("2026-01-31", "2026-03-31", "MONTHLY"),
        ("2028-02-29", "2032-02-29", "YEARLY"),
    ],
)
async def test_calendar_recurrences_map_existing_occurrences(client, db, start, end, frequency):
    fields = await setup(db)
    fields.update(startDate=start, endDate=end, recurrence={"frequency": frequency})
    predecessor = await create(client, fields)
    prior = ids_by_day(predecessor)
    result = await create(client, {**fields, "dependencyTodoIds": [next(iter(prior.values()))]})
    await assert_dependencies(client, result, {day: [prior[day]] for day in prior})


@pytest.mark.parametrize("override", [None, [], "explicit"])
async def test_conversion_maps_inherited_or_explicit_dependencies_and_preserves_source(client, db, override):
    fields = await setup(db)
    predecessor = await create(client, {**fields, "weekdays": [3, 5]})
    prior = ids_by_day(predecessor)
    source = await make_todo(db, 1, fields["categoryId"])
    ordinary = await make_todo(db, 1, fields["categoryId"])
    source.dependencies = [next(iter(prior.values())), ordinary.id]
    source.is_completed = True
    await db.commit()
    payload = {"requestId": str(uuid4()), "startDate": fields["startDate"], "endDate": fields["endDate"]}
    if override is not None:
        payload["dependencyTodoIds"] = [next(iter(prior.values()))] if override == "explicit" else []
    response = await client.post(f"/api/v1/todos/{source.id}/routine", json=payload, headers=auth_headers(1))
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["occurrences"][0]["todoId"] == source.id
    expected = {}
    for day in ids_by_day(result):
        expected[day] = [] if override == [] else ([prior[day]] if day in prior else [])
        if override is None:
            expected[day].append(ordinary.id)
    await assert_dependencies(client, result, expected)
    await db.refresh(source)
    assert source.is_completed is True


async def test_conversion_rejects_cycle_introduced_by_same_day_remapping_atomically(client, db):
    fields = await setup(db)
    predecessor = await create(client, fields)
    prior = ids_by_day(predecessor)
    source = await make_todo(db, 1, fields["categoryId"])
    source.dependencies = [prior["2026-11-03"]]
    first = await db.get(Todo, prior["2026-11-02"])
    first.dependencies = [source.id]
    await db.commit()
    response = await client.post(
        f"/api/v1/todos/{source.id}/routine",
        headers=auth_headers(1),
        json={
            "requestId": str(uuid4()),
            "startDate": fields["startDate"],
            "endDate": fields["endDate"],
        },
    )
    assert response.status_code == 422
    await db.refresh(source)
    assert source.routine_id is None and source.dependencies == [prior["2026-11-03"]]
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 1
    assert await db.scalar(select(func.count(Todo.id))) == 8


@pytest.mark.parametrize("dependency", ["foreign", "missing", "self"])
async def test_rejects_unauthorized_missing_and_self_dependencies(client, db, dependency):
    fields = await setup(db)
    source = await make_todo(db, 1, fields["categoryId"])
    await make_user(db, 2)
    category = await make_category(db, 2)
    other = await make_todo(db, 2, category.id)
    selected = {"foreign": other.id, "missing": 99999, "self": source.id}[dependency]
    response = await client.post(
        f"/api/v1/todos/{source.id}/routine",
        headers=auth_headers(1),
        json={
            "requestId": str(uuid4()),
            "startDate": fields["startDate"],
            "endDate": fields["endDate"],
            "dependencyTodoIds": [selected],
        },
    )
    assert response.status_code == (422 if dependency == "self" else 404)
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 0
    if dependency != "self":
        response = await client.post(
            URL,
            headers=auth_headers(1),
            json={
                **fields,
                "requestId": str(uuid4()),
                "dependencyTodoIds": [selected],
            },
        )
        assert response.status_code == 404
        assert await db.scalar(select(func.count(TodoRoutine.id))) == 0


@pytest.mark.parametrize("value", [None, [True], ["1"], [0], [-1], [1] * 101])
async def test_dependency_input_validation(client, db, value):
    fields = await setup(db)
    response = await client.post(
        URL,
        headers=auth_headers(1),
        json={
            **fields,
            "requestId": str(uuid4()),
            "dependencyTodoIds": value,
        },
    )
    assert response.status_code == 422
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 0


async def test_replay_normalization_and_deletion_do_not_relink_or_resurrect(client, db):
    fields = await setup(db)
    predecessor = await create(client, fields)
    prior = list(ids_by_day(predecessor).values())
    payload = {**fields, "requestId": str(uuid4()), "dependencyTodoIds": [prior[1], prior[0], prior[1]]}
    result = await create(client, payload)
    payload["dependencyTodoIds"] = [prior[0], prior[1]]
    assert (await client.post(URL, headers=auth_headers(1), json=payload)).json() == result
    conflict = await client.post(URL, headers=auth_headers(1), json={**payload, "dependencyTodoIds": []})
    assert conflict.status_code == 409
    await client.delete(f"{URL}/{predecessor['routineId']}", headers=auth_headers(1))
    await assert_dependencies(client, result, {day: [] for day in ids_by_day(result)})
    assert (await client.post(URL, headers=auth_headers(1), json=payload)).json() == result
    await assert_dependencies(client, result, {day: [] for day in ids_by_day(result)})


async def test_old_definitions_without_dependencies_still_replay(client, db):
    fields = await setup(db)
    payload = {**fields, "requestId": str(uuid4())}
    result = await create(client, payload)
    row = await db.get(TodoRoutine, result["routineId"])
    assert "dependencyTodoIds" not in row.definition
    assert (await client.post(URL, headers=auth_headers(1), json={**payload, "dependencyTodoIds": []})).json() == result


async def test_conversion_retry_after_source_deletion_keeps_original_response(client, db):
    fields = await setup(db)
    predecessor = await create(client, fields)
    source = await make_todo(db, 1, fields["categoryId"])
    source.dependencies = [predecessor["occurrences"][0]["todoId"]]
    await db.commit()
    payload = {"requestId": str(uuid4()), "startDate": fields["startDate"], "endDate": fields["endDate"]}
    endpoint = f"/api/v1/todos/{source.id}/routine"
    response = await client.post(endpoint, json=payload, headers=auth_headers(1))
    assert response.status_code == 201
    assert (await client.delete(f"/api/v1/todos/{source.id}", headers=auth_headers(1))).status_code == 200
    assert (await client.post(endpoint, json=payload, headers=auth_headers(1))).json() == response.json()


async def test_dependency_creation_rolls_back_on_commit_failure(client, db, monkeypatch):
    from app.application.routines_service import create_routine
    from app.presentation.v1.todos.routines_controller import RoutineCreateRequest

    fields = await setup(db)
    predecessor = await create(client, fields)
    payload = RoutineCreateRequest(
        **{
            **fields,
            "requestId": str(uuid4()),
            "dependencyTodoIds": [predecessor["occurrences"][0]["todoId"]],
        }
    )

    async def fail_commit():
        raise RuntimeError("commit failed")

    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="commit failed"):
            await create_routine(db, payload, 1)
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 1
    assert await db.scalar(select(func.count(Todo.id))) == 7
    assert (await create_routine(db, payload, 1))["createdCount"] == 7


async def test_matching_uses_original_occurrence_date_not_edited_display_date(client, db):
    fields = await setup(db)
    predecessor = await create(client, fields)
    prior = ids_by_day(predecessor)
    response = await client.patch(
        f"/api/v1/todos/{prior['2026-11-02']}",
        headers=auth_headers(1),
        json={
            "startDate": "2026-12-02",
            "dueDate": "2026-12-02",
        },
    )
    assert response.status_code == 200
    result = await create(client, {**fields, "dependencyTodoIds": [prior["2026-11-02"]]})
    await assert_dependencies(client, result, {day: [prior[day]] for day in prior})
