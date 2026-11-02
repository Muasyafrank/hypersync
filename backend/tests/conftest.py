"""Shared fixtures for the API tests.

The suite runs against a throw-away SQLite file so it needs neither PostgreSQL
nor a populated ``.env``. Settings are injected through environment variables
*before* ``app`` is imported, because ``app.core.config`` reads them on import.
"""

import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="hypersync-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
os.environ["SECRET_KEY"] = "test-only-secret-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_schema():
    """Give every test an empty database."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


PASSWORD = "correct-horse-battery"


@pytest.fixture()
def register_and_login(client):
    """Create a patient account and return auth headers for it."""

    def _make(email: str = "amina@example.com", full_name: str = "Amina Wanjiru") -> dict[str, str]:
        response = client.post(
            "/auth/register",
            json={"full_name": full_name, "email": email, "password": PASSWORD},
        )
        assert response.status_code == 201, response.text
        # /auth/login is an OAuth2 password flow: form-encoded, email in "username".
        login = client.post("/auth/login", data={"username": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    return _make


@pytest.fixture()
def patient_headers(register_and_login):
    return register_and_login()
