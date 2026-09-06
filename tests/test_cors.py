import pytest


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://localhost:7659"])
async def test_local_development_origins_are_allowed_by_cors(client, origin):
    response = await client.options(
        "/ping",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
