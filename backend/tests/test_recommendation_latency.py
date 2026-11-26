"""The deterministic recommendation path must stay responsive without an LLM."""

import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


def _wait_until_ready(process: subprocess.Popen, client: httpx.Client) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Uvicorn exited before becoming ready with code {process.returncode}")
        try:
            if client.get("/health", timeout=0.25).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    pytest.fail("Uvicorn did not become ready within 10 seconds")


def test_real_http_recommendation_latency_stays_under_300_ms():
    """Measure a real Uvicorn socket request, not an in-process ASGI call."""
    port = _free_port()
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "0"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
            "--no-access-log",
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0) as client:
            _wait_until_ready(process, client)

            registration = client.post(
                "/auth/register",
                json={
                    "full_name": "HTTP Latency Patient",
                    "email": "http.latency@example.com",
                    "password": "correct-horse-battery",
                },
            )
            assert registration.status_code == 201, registration.text
            login = client.post(
                "/auth/login",
                data={"username": "http.latency@example.com", "password": "correct-horse-battery"},
            )
            assert login.status_code == 200, login.text
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            for days_ago in range(5):
                when = (datetime.now(UTC) - timedelta(days=days_ago)).replace(microsecond=0)
                reading = client.post(
                    "/readings",
                    json={
                        "systolic": 170,
                        "diastolic": 100,
                        "heart_rate": 70,
                        "recorded_at": when.isoformat(),
                        "rested_before": True,
                        "stimulant_before": False,
                    },
                    headers=headers,
                )
                assert reading.status_code == 201, reading.text

            factors = client.post(
                "/factors",
                json={
                    "logged_date": datetime.now(UTC).date().isoformat(),
                    "smoked": False,
                    "alcohol_consumed": False,
                    "salt_intake": "low",
                    "physical_activity_minutes": 30,
                    "diet_adherence": True,
                    "sleep_hours": 8,
                    "stress_level": "low",
                },
                headers=headers,
            )
            assert factors.status_code == 201, factors.text

            # Model validation happens during application startup, so this
            # first recommendation request does not pay artefact-loading cost.
            durations = []
            for _ in range(20):
                started = perf_counter()
                response = client.get("/recommendations/me", headers=headers)
                durations.append(perf_counter() - started)
                assert response.status_code == 200, response.text

            first = durations[0]
            assert first < 0.300, f"first HTTP recommendation latency was {first * 1000:.1f} ms"
            p95 = sorted(durations)[max(0, int(len(durations) * 0.95) - 1)]
            assert p95 < 0.300, f"p95 HTTP recommendation latency was {p95 * 1000:.1f} ms"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
