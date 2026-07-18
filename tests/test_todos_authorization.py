from tests.conftest import add_member, auth_headers, make_category, make_group, make_todo, make_user


async def test_list_todos_defaults_to_own_todos_when_no_user_id(client, db):
    await make_user(db, 1, "requester")
    category = await make_category(db, 1)
    await make_todo(db, 1, category.id, visibility="PRIVATE", title="mine")

    response = await client.get("/api/v1/todos", headers=auth_headers(1))

    assert response.status_code == 200
    titles = [todo["title"] for todo in response.json()]
    assert titles == ["mine"]


async def test_list_todos_other_user_without_group_id_returns_400(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")

    response = await client.get("/api/v1/todos", params={"userId": 2}, headers=auth_headers(1))

    assert response.status_code == 400


async def test_list_todos_other_user_requester_not_group_member_returns_403(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 2)  # only the target user belongs to the group

    response = await client.get("/api/v1/todos", params={"userId": 2, "groupId": 10}, headers=auth_headers(1))

    assert response.status_code == 403


async def test_list_todos_other_user_target_not_group_member_returns_403(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1)  # only the requester belongs to the group

    response = await client.get("/api/v1/todos", params={"userId": 2, "groupId": 10}, headers=auth_headers(1))

    assert response.status_code == 403


async def test_list_todos_other_user_shared_group_excludes_private(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1)
    await add_member(db, 10, 2)
    category = await make_category(db, 2)
    await make_todo(db, 2, category.id, visibility="PRIVATE", group_id=10, title="secret")
    await make_todo(db, 2, category.id, visibility="GROUP", group_id=10, title="group-visible")
    await make_todo(db, 2, category.id, visibility="PUBLIC", group_id=10, title="public-visible")

    response = await client.get("/api/v1/todos", params={"userId": 2, "groupId": 10}, headers=auth_headers(1))

    assert response.status_code == 200
    titles = {todo["title"] for todo in response.json()}
    assert titles == {"group-visible", "public-visible"}


async def test_list_todos_other_user_filters_by_requested_group(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")
    await make_group(db, 10, "shared-a")
    await make_group(db, 20, "shared-b")
    await add_member(db, 10, 1)
    await add_member(db, 10, 2)
    await add_member(db, 20, 1)
    await add_member(db, 20, 2)
    category = await make_category(db, 2)
    await make_todo(db, 2, category.id, visibility="GROUP", group_id=10, title="in-group-10")
    await make_todo(db, 2, category.id, visibility="GROUP", group_id=20, title="in-group-20")

    response = await client.get("/api/v1/todos", params={"userId": 2, "groupId": 10}, headers=auth_headers(1))

    assert response.status_code == 200
    titles = [todo["title"] for todo in response.json()]
    assert titles == ["in-group-10"]


async def test_list_todos_explicit_own_user_id_does_not_require_group(client, db):
    await make_user(db, 1, "requester")
    category = await make_category(db, 1)
    await make_todo(db, 1, category.id, visibility="PRIVATE", title="mine-private")

    response = await client.get("/api/v1/todos", params={"userId": 1}, headers=auth_headers(1))

    assert response.status_code == 200
    titles = [todo["title"] for todo in response.json()]
    assert titles == ["mine-private"]
