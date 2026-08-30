from app.shared.fonts import DEFAULT_FONT
from tests.conftest import auth_headers, make_user


async def test_get_me_returns_default_font(client, db):
    await make_user(db, 1, "user")

    response = await client.get("/api/v1/users/me", headers=auth_headers(1))

    assert response.status_code == 200
    assert response.json()["font"] == DEFAULT_FONT


async def test_update_font_saves_supported_font(client, db):
    user = await make_user(db, 1, "user")

    response = await client.patch(
        "/api/v1/users/me/font",
        json={"font": "PRETENDARD"},
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "font": "PRETENDARD"}
    await db.refresh(user)
    assert user.font == "PRETENDARD"


async def test_update_font_rejects_unsupported_font(client, db):
    user = await make_user(db, 1, "user")

    response = await client.patch(
        "/api/v1/users/me/font",
        json={"font": "UNKNOWN_FONT"},
        headers=auth_headers(1),
    )

    assert response.status_code == 422
    await db.refresh(user)
    assert user.font == DEFAULT_FONT
