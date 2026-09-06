from tests.conftest import auth_headers, make_category, make_todo, make_user


async def test_list_todos_defaults_to_own_todos(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "other")
    requester_category = await make_category(db, 1)
    other_category = await make_category(db, 2)
    await make_todo(db, 1, requester_category.id, title="mine")
    await make_todo(db, 2, other_category.id, title="other")

    response = await client.get("/api/v1/todos", headers=auth_headers(1))

    assert response.status_code == 200
    assert [todo["title"] for todo in response.json()] == ["mine"]


async def test_list_todos_allows_viewing_another_users_todos_without_group(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")
    category = await make_category(db, 2)
    await make_todo(db, 2, category.id, title="public-todo")

    response = await client.get(
        "/api/v1/todos",
        params={"userId": 2},
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    assert [todo["title"] for todo in response.json()] == ["public-todo"]


async def test_list_todos_explicit_own_user_id_returns_own_todos(client, db):
    await make_user(db, 1, "requester")
    category = await make_category(db, 1)
    await make_todo(db, 1, category.id, title="mine")

    response = await client.get(
        "/api/v1/todos",
        params={"userId": 1},
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    assert [todo["title"] for todo in response.json()] == ["mine"]


async def test_create_todo_response_omits_group_and_visibility(client, db):
    await make_user(db, 1, "owner")
    category = await make_category(db, 1)

    response = await client.post(
        "/api/v1/todos",
        json={"title": "public-todo", "categoryId": category.id},
        headers=auth_headers(1),
    )

    assert response.status_code == 201
    assert response.json()["title"] == "public-todo"
    assert "groupId" not in response.json()
    assert "visibility" not in response.json()
