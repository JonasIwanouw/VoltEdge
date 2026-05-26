# tests/test_api.py
# API integration tests for VoltEdge
# Tester at endpoints returnerer korrekte svar

import pytest
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ==============================================================
# BASIC ROUTES
# ==============================================================

class TestBasicRoutes:
    def test_ping(self, client):
        response = client.get("/ping")
        assert response.status_code == 200
        assert b"pong" in response.data

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"

    def test_index(self, client):
        response = client.get("/")
        assert response.status_code == 200


# ==============================================================
# CHARGERS API
# ==============================================================

class TestChargersApi:
    def test_get_chargers_returns_list(self, client):
        response = client.get("/api/chargers")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_get_charger_not_found(self, client):
        response = client.get("/api/chargers/ikke-eksisterende-id")
        assert response.status_code == 404


# ==============================================================
# TELEMETRI API
# ==============================================================

class TestTelemetriApi:
    def test_telemetry_missing_fields(self, client):
        response = client.post(
            "/api/telemetry",
            json={"id": "test"},
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_telemetry_missing_body(self, client):
        response = client.post("/api/telemetry")
        assert response.status_code in [400, 415]


# ==============================================================
# INCIDENTS API
# ==============================================================

class TestIncidentsApi:
    def test_get_incidents_returns_list(self, client):
        response = client.get("/api/incidents")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_resolve_incident_not_found(self, client):
        response = client.put("/api/incidents/ikke-eksisterende-id/resolve")
        assert response.status_code == 404

    def test_ongoing_incident_not_found(self, client):
        response = client.put("/api/incidents/ikke-eksisterende-id/ongoing")
        assert response.status_code == 404


# ==============================================================
# ASSIGNMENTS API
# ==============================================================

class TestAssignmentsApi:
    def test_get_assignments_returns_list(self, client):
        response = client.get("/api/assignments")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_respond_missing_accept_field(self, client):
        response = client.put(
            "/api/assignments/test-id/respond",
            json={"wrong_field": True},
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_respond_assignment_not_found(self, client):
        response = client.put(
            "/api/assignments/ikke-eksisterende-id/respond",
            json={"accept": True},
            content_type="application/json"
        )
        assert response.status_code == 404


# ==============================================================
# NOTIFICATIONS API
# ==============================================================

class TestNotificationsApi:
    def test_get_notifications_returns_list(self, client):
        response = client.get("/api/notifications")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)


# ==============================================================
# GRID STATUS API
# ==============================================================

class TestGridStatusApi:
    def test_get_grid_status(self, client):
        response = client.get("/api/grid-status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "grid_status" in data
        assert "area" in data