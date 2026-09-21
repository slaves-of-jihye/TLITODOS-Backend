import pytest

from tests.conftest import auth_headers, make_user

URL = "/api/v1/users/me/time-format"


async def test_default_and_round_trip_only_change_own_display_setting(client, db):
    user = await make_user(db, 1)
    other = await make_user(db, 2)
    assert user.time_format == "12H"
    assert (await client.get("/api/v1/users/me", headers=auth_headers(1))).json()["timeFormat"] == "12H"
    for value in ("24H", "24H", "12H"):
        response = await client.patch(URL, json={"timeFormat": value}, headers=auth_headers(1))
        assert response.status_code == 200
        assert response.json() == {"success": True, "timeFormat": value}
        await db.refresh(user)
        await db.refresh(other)
        assert user.time_format == value
        assert other.time_format == "12H"
        assert (await client.get("/api/v1/users/me", headers=auth_headers(1))).json()["timeFormat"] == value


async def test_profile_edits_preserve_time_format(client, db):
    await make_user(db, 1)
    await client.patch(URL, json={"timeFormat": "24H"}, headers=auth_headers(1))
    response = await client.patch("/api/v1/users/me", json={"name": "새 이름"}, headers=auth_headers(1))
    assert response.status_code == 200
    assert response.json()["timeFormat"] == "24H"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"timeFormat": None},
        {"timeFormat": 12},
        {"timeFormat": "12h"},
        {"timeFormat": ""},
        {"timeFormat": "48H"},
        {"timeFormat": "24H", "userId": 2},
        {"time_format": "24H"},
    ],
)
async def test_invalid_settings_do_not_mutate_user(client, db, payload):
    user = await make_user(db, 1)
    response = await client.patch(URL, json=payload, headers=auth_headers(1))
    assert response.status_code == 422
    await db.refresh(user)
    assert user.time_format == "12H"


@pytest.mark.parametrize("authorization", [None, "Bearer invalid"])
async def test_requires_bearer_authentication(client, authorization):
    from app.main import app
    from app.shared.auth import require_access_token

    app.dependency_overrides.pop(require_access_token)
    headers = {"Authorization": authorization} if authorization else {}
    assert (await client.patch(URL, json={"timeFormat": "24H"}, headers=headers)).status_code == 401
