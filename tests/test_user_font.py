import pytest

from app.shared.fonts import DEFAULT_FONT, SUPPORTED_FONTS
from tests.conftest import auth_headers, make_user


async def test_get_me_returns_default_font(client, db):
    await make_user(db, 1, "user")

    response = await client.get("/api/v1/users/me", headers=auth_headers(1))

    assert response.status_code == 200
    assert response.json()["font"] == DEFAULT_FONT


@pytest.mark.parametrize("font", sorted(SUPPORTED_FONTS))
async def test_update_font_saves_supported_font(client, db, font):
    user = await make_user(db, 1, "user")

    response = await client.patch(
        "/api/v1/users/me/font",
        json={"font": font},
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "font": font}
    await db.refresh(user)
    assert user.font == font


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
