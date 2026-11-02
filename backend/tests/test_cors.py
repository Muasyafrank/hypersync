"""What a browser needs from CORS for the cookie session and the X-Timezone header."""

ORIGIN = "http://localhost:5173"


def test_preflight_allows_the_custom_timezone_header(client):
    response = client.options(
        "/readings/me/trend",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-timezone",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "x-timezone" in response.headers["access-control-allow-headers"].lower()


def test_credentialed_responses_name_the_origin_never_a_wildcard(client):
    """Browsers refuse to send/accept cookies if allow-origin is '*'."""
    response = client.post(
        "/auth/refresh",
        headers={"Origin": ORIGIN},
    )
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unknown_origins_get_no_cors_headers(client):
    response = client.post("/auth/refresh", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
