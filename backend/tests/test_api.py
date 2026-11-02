"""End-to-end checks of the HTTP API (auth, readings, role guards, alerts)."""

from datetime import UTC, datetime, timedelta

import pytest


def _reading(**overrides):
    payload = {"systolic": 120, "diastolic": 80, "heart_rate": 72}
    payload.update(overrides)
    return payload


class TestAuth:
    def test_register_login_and_me(self, client, patient_headers):
        me = client.get("/auth/me", headers=patient_headers)
        assert me.status_code == 200
        assert me.json()["role"] == "patient"

    def test_duplicate_email_is_rejected(self, client, register_and_login):
        register_and_login("dup@example.com")
        again = client.post(
            "/auth/register",
            json={"full_name": "Someone Else", "email": "dup@example.com", "password": "another-password"},
        )
        assert again.status_code == 400

    def test_wrong_password_is_rejected(self, client, register_and_login):
        register_and_login("amina@example.com")
        response = client.post("/auth/login", data={"username": "amina@example.com", "password": "nope-nope-nope"})
        assert response.status_code == 401

    def test_protected_route_requires_a_token(self, client):
        assert client.get("/readings/me").status_code == 401

    def test_blank_name_is_rejected(self, client):
        response = client.post(
            "/auth/register",
            json={"full_name": "   ", "email": "blank@example.com", "password": "long-enough-pw"},
        )
        assert response.status_code == 422

    def test_malformed_refresh_token_is_a_401_not_a_500(self, client):
        response = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert response.status_code == 401


class TestReadings:
    def test_pulse_is_optional(self, client, patient_headers):
        """The form marks pulse optional, so a reading without one must save."""
        response = client.post("/readings", json=_reading(heart_rate=None), headers=patient_headers)
        assert response.status_code == 201, response.text
        assert response.json()["heart_rate"] is None

    def test_reading_is_classified_and_listed(self, client, patient_headers):
        created = client.post("/readings", json=_reading(systolic=155, diastolic=95), headers=patient_headers)
        assert created.status_code == 201
        assert created.json()["status"] == "high"

        listed = client.get("/readings/me", headers=patient_headers).json()
        assert [r["status"] for r in listed] == ["high"]

    def test_trend_averages_pulse_only_where_logged(self, client, patient_headers):
        client.post("/readings", json=_reading(heart_rate=60), headers=patient_headers)
        client.post("/readings", json=_reading(heart_rate=None), headers=patient_headers)
        trend = client.get("/readings/me/trend?period_days=7", headers=patient_headers).json()
        assert trend["reading_count"] == 2
        assert trend["avg_heart_rate"] == 60

    def test_diastolic_must_be_lower_than_systolic(self, client, patient_headers):
        response = client.post("/readings", json=_reading(systolic=110, diastolic=120), headers=patient_headers)
        assert response.status_code == 422

    def test_high_trend_raises_a_single_alert(self, client, patient_headers):
        for _ in range(2):
            client.post("/readings", json=_reading(systolic=170, diastolic=100), headers=patient_headers)
        alerts = client.get("/alerts/me", headers=patient_headers).json()
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "high_trend"

    def test_a_patient_cannot_delete_someone_elses_reading(self, client, register_and_login):
        owner = register_and_login("owner@example.com")
        other = register_and_login("other@example.com")
        reading_id = client.post("/readings", json=_reading(), headers=owner).json()["reading_id"]

        assert client.delete(f"/readings/{reading_id}", headers=other).status_code == 403
        assert client.delete(f"/readings/{reading_id}", headers=owner).status_code == 204


class TestReadingSummary:
    def test_counts_every_reading_by_status_without_listing_them(self, client, register_and_login):
        mine = register_and_login("mine@example.com")
        other = register_and_login("other@example.com")
        for systolic, diastolic in [(120, 80), (160, 100), (170, 105), (85, 55)]:
            client.post("/readings", json=_reading(systolic=systolic, diastolic=diastolic), headers=mine)
        client.post("/readings", json=_reading(systolic=160, diastolic=100), headers=other)  # not mine

        summary = client.get("/readings/me/summary", headers=mine).json()
        assert summary == {"total": 4, "status_counts": {"controlled": 1, "elevated": 0, "high": 2, "low": 1}}

    def test_empty_history(self, client, patient_headers):
        summary = client.get("/readings/me/summary", headers=patient_headers).json()
        assert summary["total"] == 0
        assert set(summary["status_counts"]) == {"controlled", "elevated", "high", "low"}


class TestTimezone:
    @staticmethod
    def _first_day(client, headers):
        return client.get("/readings/me/trend?period_days=7", headers=headers).json()["daily_breakdown"][0]["date"]

    def test_days_follow_the_callers_timezone(self, client, patient_headers):
        # 22:30 UTC is 01:30 the *next* day in Nairobi (UTC+3).
        moment = (datetime.now(UTC) - timedelta(days=2)).replace(hour=22, minute=30, second=0, microsecond=0)
        client.post("/readings", json=_reading(recorded_at=moment.isoformat()), headers=patient_headers)

        assert self._first_day(client, patient_headers) == moment.date().isoformat()
        nairobi = {**patient_headers, "X-Timezone": "Africa/Nairobi"}
        assert self._first_day(client, nairobi) == (moment.date() + timedelta(days=1)).isoformat()

    @pytest.mark.parametrize("bogus", ["Not/AZone", "", "../etc/passwd"])
    def test_an_unusable_timezone_falls_back_to_utc(self, client, patient_headers, bogus):
        moment = (datetime.now(UTC) - timedelta(days=2)).replace(hour=22, minute=30, second=0, microsecond=0)
        client.post("/readings", json=_reading(recorded_at=moment.isoformat()), headers=patient_headers)
        headers = {**patient_headers, "X-Timezone": bogus}
        assert self._first_day(client, headers) == moment.date().isoformat()


class TestRoleGuards:
    def test_patient_cannot_use_clinician_or_admin_endpoints(self, client, patient_headers):
        assert client.get("/alerts", headers=patient_headers).status_code == 403
        assert client.get("/users", headers=patient_headers).status_code == 403
        assert client.get("/users/patients/summary", headers=patient_headers).status_code == 403
