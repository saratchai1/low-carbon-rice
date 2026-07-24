from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.seed import DEMO_BOUNDARY_WARNING
from app.services.public_data import ADAPTERS
from app.services.ultimate import (
    PROVENANCE_TYPES,
    SCENARIOS,
    detect_stuck,
    evaluate_awd_transparent,
    serialize_scenario_run,
    validate_observation,
)


PARAMETERS = {
    "irrigation_trigger_cm": -15,
    "critical_lower_threshold_cm": -20,
    "maximum_dry_days": 8,
    "minimum_soil_moisture": 35,
    "rain_forecast_threshold_mm": 10,
    "sensor_confidence_requirement": 70,
    "crop_stage_exclusions": ["FLOWERING"],
}


def evaluate(**overrides):
    inputs = {
        "water_level_cm": -7,
        "dry_period_days": 3,
        "soil_moisture_percent": 55,
        "forecast_rainfall_24h_mm": 0,
        "data_confidence": 90,
        "crop_stage": "TILLERING",
    }
    inputs.update(overrides)
    return evaluate_awd_transparent(inputs, PARAMETERS)


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("water_level_cm", -41),
        ("water_level_cm", 81),
        ("soil_moisture_10cm", 101),
        ("rainfall_mm", -1),
        ("pump_status", 2),
        ("water_ph", 15),
    ],
)
def test_sensor_validation_rejects_physical_outliers(metric, value):
    assert validate_observation(metric, value)


def test_sensor_validation_accepts_expected_value():
    assert validate_observation("water_level_cm", -12.4) == []


def test_sensor_validation_rejects_non_finite_value():
    assert "value must be finite" in validate_observation("water_level_cm", float("nan"))


def test_stuck_detection_requires_minimum_samples():
    assert not detect_stuck([2, 2, 2])
    assert detect_stuck([2, 2, 2, 2, 2, 2])


def test_awd_waits_for_forecast_rainfall():
    result = evaluate(
        water_level_cm=-16,
        soil_moisture_percent=48,
        forecast_rainfall_24h_mm=22,
    )
    assert result["recommendation"] == "WAIT_12_HOURS"
    assert any("Forecast rainfall" in reason for reason in result["reasons"])


def test_awd_orders_irrigation_for_overdrying():
    result = evaluate(
        water_level_cm=-21,
        dry_period_days=9,
        soil_moisture_percent=30,
    )
    assert result["recommendation"] == "IRRIGATE_NOW"
    assert result["severity"] == "CRITICAL"


def test_awd_requires_field_review_when_confidence_is_low():
    assert evaluate(data_confidence=52)["recommendation"] == "FIELD_REVIEW"


def test_awd_does_not_automate_excluded_crop_stage():
    assert evaluate(crop_stage="FLOWERING")["recommendation"] == "FIELD_REVIEW"


def test_awd_input_snapshot_is_not_self_referential():
    inputs = {
        "water_level_cm": -10,
        "dry_period_days": 4,
        "soil_moisture_percent": 50,
        "forecast_rainfall_24h_mm": 0,
        "data_confidence": 90,
        "crop_stage": "TILLERING",
    }
    result = evaluate_awd_transparent(inputs, PARAMETERS)
    inputs["rule_evaluation"] = result
    assert result["inputs_used"] is not inputs
    assert "rule_evaluation" not in result["inputs_used"]


def test_all_required_provenance_types_are_exposed():
    assert PROVENANCE_TYPES == (
        "LIVE", "SIMULATED", "PUBLIC", "MANUAL", "DERIVED", "REFERENCE"
    )


def test_ten_demo_scenarios_have_unique_numbers():
    assert len(SCENARIOS) == 10
    assert sorted(item["number"] for item in SCENARIOS.values()) == list(range(1, 11))


def test_scenarios_are_deterministic_reference_definitions():
    assert deepcopy(SCENARIOS["wait_rainfall"]) == SCENARIOS["wait_rainfall"]
    assert SCENARIOS["wait_rainfall"]["duration_ticks"] == 8


def test_scenario_serializer_preserves_run_state():
    run = SimpleNamespace(
        id="run-1",
        scenario_key="normal_awd",
        status="RUNNING",
        speed=60,
        seed=20260724,
        tick=2,
        simulated_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        state={"water_level_cm": -2, "source_type": "SIMULATED"},
        outcome={},
        updated_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    payload = serialize_scenario_run(run)
    assert payload["definition"]["number"] == 1
    assert payload["state"]["source_type"] == "SIMULATED"


def test_public_adapters_return_provenance_and_non_live_status():
    for adapter in ADAPTERS.values():
        assert adapter.fetch_current()["source_type"] == "PUBLIC"
        assert adapter.report_status()["live_connected"] is False


def test_empty_public_payload_is_invalid():
    valid, errors = ADAPTERS["weather"].validate({})
    assert not valid
    assert errors == ["empty_payload"]


def test_boundary_warning_is_exact_and_legally_unambiguous():
    assert DEMO_BOUNDARY_WARNING == (
        "DEMO-PLOT-001 is a synthetic demonstration boundary. "
        "It is not a cadastral, surveyed, legal, ownership, or officially verified plot boundary."
    )
