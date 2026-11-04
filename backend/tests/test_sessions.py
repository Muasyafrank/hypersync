"""Session handling: the refresh token lives in an httpOnly cookie, not in JS."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app

PASSWORD = "correct-horse-battery"  # same as conftest.PASSWORD

COOKIE = "hs_refresh"


def _login(client, email="amina@example.com"):
    client.post("/auth/register", json={"full_name": "Amina Wanjiru", "email": email, "password": PASSWORD})
    return client.post("/auth/login", data={"username": email, "password": PASSWORD})


def test_login_returns_only_an_access_token_and_sets_the_cookie(client):
    response = _login(client)
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}  # no refresh token in the body

    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_refresh_uses_the_cookie(client):
    _login(client)
    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"})
    assert me.status_code == 200


def test_refresh_without_a_session_is_rejected(client):
    assert client.post("/auth/refresh").status_code == 401


def test_refresh_token_in_the_body_still_works_for_api_clients(client):
    _login(client)
    token = client.cookies.get(COOKIE)
    with TestClient(app) as cookieless:
        assert cookieless.post("/auth/refresh", json={"refresh_token": token}).status_code == 200


def test_logout_revokes_the_refresh_token_and_clears_the_cookie(client):
    access = _login(client).json()["access_token"]
    token = client.cookies.get(COOKIE)

    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {access}"})
    assert logout.status_code == 204
    assert f'{COOKIE}="";' in logout.headers["set-cookie"] or f"{COOKIE}=;" in logout.headers["set-cookie"]
    assert client.cookies.get(COOKIE) is None

    # Even someone who copied the token earlier cannot use it any more.
    with TestClient(app) as cookieless:
        assert cookieless.post("/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_an_access_token_is_not_accepted_as_a_refresh_token(client):
    access = _login(client).json()["access_token"]
    with TestClient(app) as cookieless:
        assert cookieless.post("/auth/refresh", json={"refresh_token": access}).status_code == 401


def test_samesite_none_requires_secure():
    with pytest.raises(ValidationError):
        Settings(database_url="x", secret_key="y", cookie_samesite="none", cookie_secure=False)
    assert Settings(database_url="x", secret_key="y", cookie_samesite="none", cookie_secure=True)
