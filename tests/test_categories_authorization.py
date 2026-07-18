from tests.conftest import add_member, auth_headers, make_category, make_group, make_user


async def test_list_categories_defaults_to_own_categories(client, db):
    await make_user(db, 1, "requester")
    await make_category(db, 1, name="mine")

    response = await client.get("/api/v1/categories", headers=auth_headers(1))

    assert response.status_code == 200
    names = [category["name"] for category in response.json()]
    assert names == ["mine"]


async def test_list_categories_other_user_without_group_id_returns_400(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")

    response = await client.get("/api/v1/categories", params={"userId": 2}, headers=auth_headers(1))

    assert response.status_code == 400


async def test_list_categories_other_user_not_shared_group_returns_403(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 2)  # requester is not a member

    response = await client.get("/api/v1/categories", params={"userId": 2, "groupId": 10}, headers=auth_headers(1))

    assert response.status_code == 403


async def test_list_categories_other_user_shared_group_returns_target_categories(client, db):
    await make_user(db, 1, "requester")
    await make_user(db, 2, "target")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1)
    await add_member(db, 10, 2)
    await make_category(db, 2, name="target-category")
    await make_category(db, 1, name="requester-category")

    response = await client.get("/api/v1/categories", params={"userId": 2, "groupId": 10}, headers=auth_headers(1))

    assert response.status_code == 200
    names = [category["name"] for category in response.json()]
    assert names == ["target-category"]


async def test_list_categories_explicit_own_user_id_does_not_require_group(client, db):
    await make_user(db, 1, "requester")
    await make_category(db, 1, name="mine")

    response = await client.get("/api/v1/categories", params={"userId": 1}, headers=auth_headers(1))

    assert response.status_code == 200
    names = [category["name"] for category in response.json()]
    assert names == ["mine"]
