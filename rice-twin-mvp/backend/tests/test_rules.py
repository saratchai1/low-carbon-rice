from app.services.rules import DEMO_RULE_VERSION, evaluate_awd


def test_demo_rule_exposes_version_inputs_and_disclaimer_state() -> None:
    result = evaluate_awd(water_level_cm=-16, crop_stage="แตกกอ", dry_days=8)[0]
    assert result["rule_version"] == DEMO_RULE_VERSION
    assert result["severity"] == "high"
    assert result["inputs_used"]["weather_forecast"] == "not_connected"
    assert "นักวิชาการ" in result["recommended_action"]


def test_sensitive_stage_does_not_apply_demo_threshold() -> None:
    result = evaluate_awd(water_level_cm=-20, crop_stage="ออกดอก", dry_days=9)[0]
    assert result["rule_id"] == "AWD-SENSITIVE-STAGE"
    assert result["severity"] == "warning"

