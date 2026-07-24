from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.seed import DEMO_BOUNDARY_WARNING


client = TestClient(app)


def get_data(path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"]["is_demo"] is True
    assert payload["meta"]["boundary_warning"] == DEMO_BOUNDARY_WARNING
    return payload["data"]


def test_root_and_presentation_are_available():
    assert client.get("/").status_code == 200
    assert "Executive Command Center" in client.get("/").text
    assert client.get("/presentation").status_code == 200


def test_overview_contract_and_credit_guardrail():
    data = get_data("/api/v1/overview")
    assert len(data["kpis"]) == 12
    assert data["carbon_credit_claim"] is False
    assert data["methodology_status"] == "NOT_CONFIGURED"


def test_seeded_platform_counts():
    assert len(get_data("/api/v1/plots")) == 6
    assert len(get_data("/api/v1/devices")) >= 10
    assert len(get_data("/api/v1/scenarios")) == 10
    assert len(get_data("/api/v1/observations?limit=2000")) >= 210


def test_twin_state_is_explainable_and_serializable():
    twin = get_data("/api/v1/twin-states/current")
    assert twin["rule_evaluation"]["rule_version"] == "AWD-DEMO-1.0"
    assert twin["rule_evaluation"]["inputs_used"]["plot_id"] == "DEMO-PLOT-001"
    assert twin["source_type"] == "DERIVED"


def test_carbon_api_never_claims_credit_amount():
    carbon = get_data("/api/v1/carbon")
    assert carbon["status"] == "METHODOLOGY_NOT_CONFIGURED"
    assert carbon["calculated_estimate"] is None
    assert carbon["verified_amount"] is None
    assert carbon["issued_credits"] is None


def test_sensor_ingestion_rejects_out_of_range_value():
    response = client.post(
        "/api/v1/observations",
        json={
            "device_id": "WATER-LEVEL-01",
            "plot_id": "DEMO-PLOT-001",
            "metric": "water_level_cm",
            "value": -99,
            "unit": "cm",
            "observed_at": "2026-07-24T03:30:00Z",
            "source_type": "LIVE",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["quality_flag"] == "out_of_range"


def test_sensor_ingestion_is_idempotent_by_external_id():
    external_id = f"pytest-{uuid4()}"
    payload = {
        "device_id": "WATER-LEVEL-01",
        "plot_id": "DEMO-PLOT-001",
        "metric": "water_level_cm",
        "value": -9.4,
        "unit": "cm",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_type": "SIMULATED",
        "external_id": external_id,
    }
    assert client.post("/api/v1/observations", json=payload).status_code == 201
    assert client.post("/api/v1/observations", json=payload).status_code == 409


def test_scenario_start_tick_pause_resume_reset_cycle():
    start = client.post(
        "/api/v1/scenarios/start",
        json={"scenario_key": "wait_rainfall", "speed": 60, "seed": 20260724},
    )
    assert start.status_code == 200
    run = start.json()["data"]
    run_id = run["id"]
    tick = client.post(f"/api/v1/scenarios/{run_id}/control", json={"action": "tick"})
    assert tick.json()["data"]["tick"] == 1
    paused = client.post(f"/api/v1/scenarios/{run_id}/control", json={"action": "pause"})
    assert paused.json()["data"]["status"] == "PAUSED"
    resumed = client.post(f"/api/v1/scenarios/{run_id}/control", json={"action": "resume"})
    assert resumed.json()["data"]["status"] == "RUNNING"
    reset = client.post(f"/api/v1/scenarios/{run_id}/control", json={"action": "reset"})
    assert reset.json()["data"]["tick"] == 0


def test_unknown_scenario_returns_clear_404():
    response = client.post(
        "/api/v1/scenarios/start",
        json={"scenario_key": "missing", "speed": 60, "seed": 1},
    )
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Unknown scenario"
    assert response.json()["meta"]["is_demo"] is True


def test_reports_have_html_json_and_csv_formats():
    reports = get_data("/api/v1/reports")
    assert len(reports) == 10
    assert client.get(reports[0]["html_url"]).status_code == 200
    assert client.get(reports[0]["json_url"]).status_code == 200
    csv_response = client.get(reports[0]["csv_url"])
    assert csv_response.status_code == 200
    assert "source_type" in csv_response.text


def test_request_id_is_returned_in_header_and_envelope():
    request_id = f"test-{uuid4()}"
    response = client.get("/api/v1/overview", headers={"X-Request-ID": request_id})
    assert response.headers["X-Request-ID"] == request_id
    assert response.json()["meta"]["request_id"] == request_id


def test_device_not_found_is_a_clear_error():
    response = client.get("/api/v1/devices/DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "HTTP_404",
        "message": "Device not found",
        "details": "Device not found",
    }
