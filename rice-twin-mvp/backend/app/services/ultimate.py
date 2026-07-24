import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Alert,
    AWDRuleConfiguration,
    EvidenceRecord,
    Imagery,
    Plot,
    PublicDataSnapshot,
    ScenarioRun,
    SensorDevice,
    SensorObservation,
    TwinStateSnapshot,
)
from ..seed import DEMO_BOUNDARY_WARNING, DEMO_NOW, DEMO_PLOT_ID


PROVENANCE_TYPES = ("LIVE", "SIMULATED", "PUBLIC", "MANUAL", "DERIVED", "REFERENCE")
TWIN_MODEL_VERSION = "TWIN-DEMO-1.0"

SCENARIOS: dict[str, dict[str, Any]] = {
    "normal_awd": {
        "number": 1, "name_th": "รอบ AWD ปกติ", "name_en": "Normal AWD cycle",
        "summary": "หยุดให้น้ำ ปล่อยระดับน้ำลด สั่งให้น้ำ และปิดรอบ AWD",
        "duration_ticks": 10, "initial": {"water_level_cm": 4.0, "soil_moisture_percent": 68.0},
    },
    "wait_rainfall": {
        "number": 2, "name_th": "รอฝนตามพยากรณ์", "name_en": "Wait for forecast rainfall",
        "summary": "ระดับน้ำ -12 ซม. แต่มีฝน 22 มม. ภายใน 12 ชั่วโมง",
        "duration_ticks": 8, "initial": {"water_level_cm": -12.0, "soil_moisture_percent": 46.0},
    },
    "overdrying": {
        "number": 3, "name_th": "เสี่ยงแห้งเกิน", "name_en": "Over-drying risk",
        "summary": "น้ำและความชื้นดินต่ำโดยไม่มีฝนช่วย",
        "duration_ticks": 7, "initial": {"water_level_cm": -17.0, "soil_moisture_percent": 34.0},
    },
    "flood_risk": {
        "number": 4, "name_th": "ฝนหนักและเสี่ยงน้ำท่วม", "name_en": "Heavy-rain and flood risk",
        "summary": "ฝนเข้มข้นทำให้ระดับน้ำสูงและต้องระบาย",
        "duration_ticks": 7, "initial": {"water_level_cm": 2.0, "soil_moisture_percent": 70.0},
    },
    "sensor_offline": {
        "number": 5, "name_th": "เซนเซอร์ออฟไลน์", "name_en": "Sensor offline",
        "summary": "สลับไปใช้ค่าประมาณสำรองและลดความเชื่อมั่น",
        "duration_ticks": 6, "initial": {"water_level_cm": -8.0, "soil_moisture_percent": 49.0},
    },
    "sensor_drift": {
        "number": 6, "name_th": "เซนเซอร์คลาดเคลื่อน", "name_en": "Sensor drift",
        "summary": "เซนเซอร์ระดับน้ำสองตัวต่างกันเกิน tolerance",
        "duration_ticks": 6, "initial": {"water_level_cm": -8.0, "soil_moisture_percent": 49.0},
    },
    "false_field_report": {
        "number": 7, "name_th": "รายงานภาคสนามไม่ตรงหลักฐาน", "name_en": "False field report",
        "summary": "แจ้งว่าให้น้ำแล้ว แต่ pump/flow/ระดับน้ำไม่ยืนยัน",
        "duration_ticks": 5, "initial": {"water_level_cm": -13.0, "soil_moisture_percent": 42.0},
    },
    "public_disagreement": {
        "number": 8, "name_th": "ข้อมูลสาธารณะไม่ตรงเซนเซอร์", "name_en": "Public-data disagreement",
        "summary": "มาตรวัดที่แปลงพบฝน แต่สถานีภูมิภาคไม่พบ",
        "duration_ticks": 5, "initial": {"water_level_cm": -6.0, "soil_moisture_percent": 55.0},
    },
    "satellite_conflict": {
        "number": 9, "name_th": "ดาวเทียมขัดแย้งรายงานแปลง", "name_en": "Satellite observation conflict",
        "summary": "รายงานว่าแห้งแต่ดัชนีน้ำบ่งชี้ความเปียกชื้น",
        "duration_ticks": 5, "initial": {"water_level_cm": -9.0, "soil_moisture_percent": 51.0},
    },
    "complete_mrv": {
        "number": 10, "name_th": "ฤดูปลูกและ MRV ครบวงจร", "name_en": "Complete MRV season",
        "summary": "เล่นเหตุการณ์ตั้งแต่ขึ้นทะเบียนถึงตรวจความพร้อมการทวนสอบ",
        "duration_ticks": 12, "initial": {"water_level_cm": 3.0, "soil_moisture_percent": 72.0},
    },
}


METRIC_RANGES = {
    "water_level_cm": (-40.0, 80.0),
    "soil_moisture_10cm": (0.0, 100.0),
    "soil_moisture_30cm": (0.0, 100.0),
    "soil_moisture_50cm": (0.0, 100.0),
    "rainfall_mm": (0.0, 500.0),
    "air_temperature_c": (-20.0, 60.0),
    "relative_humidity_percent": (0.0, 100.0),
    "flow_rate_lps": (0.0, 200.0),
    "pump_status": (0.0, 1.0),
    "pump_energy_kwh": (0.0, 1_000_000.0),
    "water_ph": (0.0, 14.0),
}


def validate_observation(metric: str, value: float) -> list[str]:
    errors: list[str] = []
    limits = METRIC_RANGES.get(metric)
    if limits and not limits[0] <= value <= limits[1]:
        errors.append(f"{metric} must be between {limits[0]} and {limits[1]}")
    if not math.isfinite(value):
        errors.append("value must be finite")
    return errors


def detect_stuck(values: list[float], tolerance: float = 0.0001, minimum: int = 6) -> bool:
    return len(values) >= minimum and max(values[-minimum:]) - min(values[-minimum:]) <= tolerance


def evaluate_awd_transparent(inputs: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    water = float(inputs.get("water_level_cm", 0))
    dry_days = float(inputs.get("dry_period_days", 0))
    soil = float(inputs.get("soil_moisture_percent", 50))
    forecast = float(inputs.get("forecast_rainfall_24h_mm", 0))
    confidence = int(inputs.get("data_confidence", 0))
    crop_stage = inputs.get("crop_stage", "TILLERING")
    reasons: list[str] = []
    missing = [key for key in (
        "water_level_cm", "soil_moisture_percent", "forecast_rainfall_24h_mm"
    ) if inputs.get(key) is None]

    if crop_stage in parameters.get("crop_stage_exclusions", []):
        recommendation, severity = "FIELD_REVIEW", "HIGH"
        reasons.append("Crop stage is excluded from the demonstration AWD automation rule")
    elif confidence < parameters["sensor_confidence_requirement"]:
        recommendation, severity = "FIELD_REVIEW", "HIGH"
        reasons.append("Data confidence is below the configured requirement")
    elif water <= parameters["critical_lower_threshold_cm"] or (
        dry_days >= parameters["maximum_dry_days"] and soil < parameters["minimum_soil_moisture"]
    ):
        recommendation, severity = "IRRIGATE_NOW", "CRITICAL"
        reasons.append("Water level or dry duration crossed the configured critical threshold")
        reasons.append("Soil moisture is below the configured minimum")
    elif water <= parameters["irrigation_trigger_cm"] and forecast < parameters["rain_forecast_threshold_mm"]:
        recommendation, severity = "IRRIGATE", "HIGH"
        reasons.append("Water level crossed the irrigation review threshold")
        reasons.append("No significant forecast rainfall offsets the irrigation need")
    elif forecast >= parameters["rain_forecast_threshold_mm"] and soil >= parameters["minimum_soil_moisture"]:
        recommendation, severity = "WAIT_12_HOURS", "INFO"
        reasons.append(
            f"Forecast rainfall {forecast:.1f} mm exceeds the configured "
            f"{parameters['rain_forecast_threshold_mm']} mm threshold"
        )
        reasons.append("Soil moisture remains acceptable")
        reasons.append("Review again after the forecast window before operating the pump")
    else:
        recommendation, severity = "MONITOR", "INFO"
        reasons.append("Water level has not crossed the configured irrigation threshold")
        reasons.append("Continue monitoring the field and forecast")

    return {
        "recommendation": recommendation,
        "severity": severity,
        "rule_version": "AWD-DEMO-1.0",
        # Copy the inputs because build_twin_state attaches this evaluation back
        # onto the state dictionary. Keeping the original object here would make
        # the API payload self-referential and impossible to serialize as JSON.
        "inputs_used": dict(inputs),
        "reasons": reasons,
        "missing_inputs": missing,
        "confidence": confidence,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "next_review_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        "source_type": "DERIVED",
        "disclaimer": "Demonstration decision support; agronomist approval is not configured.",
    }


def latest_metric(db: Session, plot_id: str, metric: str) -> SensorObservation | None:
    return db.scalar(
        select(SensorObservation)
        .where(SensorObservation.plot_id == plot_id, SensorObservation.metric == metric)
        .order_by(SensorObservation.observed_at.desc())
        .limit(1)
    )


def build_twin_state(db: Session, plot_id: str = DEMO_PLOT_ID) -> dict[str, Any]:
    plot = db.get(Plot, plot_id)
    if plot is None:
        raise ValueError("Plot not found")
    water_obs = latest_metric(db, plot_id, "water_level_cm")
    soil_obs = latest_metric(db, plot_id, "soil_moisture_10cm")
    rain_obs = latest_metric(db, plot_id, "rainfall_mm")
    pump_obs = latest_metric(db, plot_id, "pump_status")
    public_forecast = db.scalar(
        select(PublicDataSnapshot)
        .where(PublicDataSnapshot.plot_id == plot_id, PublicDataSnapshot.category == "weather_forecast")
        .order_by(PublicDataSnapshot.observed_at.desc()).limit(1)
    )
    water = float(water_obs.value if water_obs else plot.water_level_cm)
    soil = float(soil_obs.value if soil_obs else 48)
    rain = float(rain_obs.value if rain_obs else 0)
    forecast = float((public_forecast.payload or {}).get("value", 0)) if public_forecast else 0
    pump = "ON" if pump_obs and pump_obs.value >= 0.5 else "OFF"
    offline = db.scalar(
        select(func.count()).select_from(SensorDevice)
        .where(SensorDevice.plot_id == plot_id, SensorDevice.status == "OFFLINE")
    ) or 0
    confidence = max(45, plot.data_confidence_score - int(offline) * 18)
    active_season = next((season for season in plot.crop_seasons if season.status == "active"), None)
    state = {
        "plot_id": plot_id,
        "crop_season_id": active_season.id if active_season else None,
        "crop_stage": "TILLERING",
        "crop_age_days": 65,
        "water_state": "DRYING" if water < 0 else "WET",
        "water_level_cm": round(water, 2),
        "soil_moisture_status": "ACCEPTABLE" if soil >= 35 else "LOW",
        "soil_moisture_percent": round(soil, 2),
        "awd_cycle_number": plot.awd_cycle,
        "dry_period_days": float(plot.dry_days),
        "rainfall_24h_mm": round(rain, 2),
        "forecast_rainfall_24h_mm": round(forecast, 2),
        "pump_status": pump,
        "yield_risk": "LOW" if soil >= 35 else "HIGH",
        "flood_risk": "HIGH" if water > 10 else "LOW",
        "data_confidence": confidence,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": TWIN_MODEL_VERSION,
        "source_type": "DERIVED",
        "provenance": {
            "water_level_cm": water_obs.source_type if water_obs else "MANUAL",
            "soil_moisture_percent": soil_obs.source_type if soil_obs else "DERIVED",
            "rainfall_24h_mm": rain_obs.source_type if rain_obs else "DERIVED",
            "forecast_rainfall_24h_mm": "PUBLIC",
            "data_confidence": "DERIVED",
        },
    }
    config = db.scalar(
        select(AWDRuleConfiguration).where(AWDRuleConfiguration.status == "ACTIVE")
        .order_by(AWDRuleConfiguration.effective_at.desc()).limit(1)
    )
    if config:
        evaluation = evaluate_awd_transparent(state, config.parameters)
        state["irrigation_recommendation"] = evaluation["recommendation"]
        state["rule_evaluation"] = evaluation
    return state


def quality_breakdown(db: Session, plot_id: str = DEMO_PLOT_ID) -> dict[str, Any]:
    devices = list(db.scalars(select(SensorDevice).where(SensorDevice.plot_id == plot_id)))
    observations = list(db.scalars(
        select(SensorObservation).where(SensorObservation.plot_id == plot_id)
        .order_by(SensorObservation.observed_at.desc()).limit(200)
    ))
    imagery = list(db.scalars(select(Imagery).where(Imagery.plot_id == plot_id)))
    evidence = list(db.scalars(select(EvidenceRecord).where(EvidenceRecord.plot_id == plot_id)))
    online = sum(device.status in {"ONLINE", "SIMULATED", "WARNING"} for device in devices)
    sensor_reliability = round(100 * online / max(1, len(devices)))
    data_completeness = min(100, round(len(observations) / 2.1))
    evidence_quality = round(100 * sum(item.review_status == "ACCEPTED" for item in evidence) / max(1, len(evidence)))
    spatial = 100 if imagery and all(item.footprint_intersects_plot for item in imagery) else (75 if not imagery else 45)
    out_of_range = sum(bool(validate_observation(item.metric, item.value)) for item in observations)
    temporal = max(40, 100 - out_of_range * 6)
    total = round(
        data_completeness * 0.25 + sensor_reliability * 0.25 +
        evidence_quality * 0.20 + spatial * 0.15 + temporal * 0.15
    )
    return {
        "plot_id": plot_id,
        "data_quality_score": total,
        "components": {
            "data_completeness_score": data_completeness,
            "sensor_reliability_score": sensor_reliability,
            "evidence_quality_score": evidence_quality,
            "spatial_consistency_score": spatial,
            "temporal_consistency_score": temporal,
        },
        "checks": {
            "sensor_offline": sum(device.status == "OFFLINE" for device in devices),
            "battery_low": sum((device.battery_percent or 100) < 20 for device in devices),
            "signal_weak": sum((device.signal_rssi or 0) < -95 for device in devices),
            "calibration_overdue": sum(
                bool(device.calibration_due_at and device.calibration_due_at < datetime.now(timezone.utc))
                for device in devices
            ),
            "out_of_range_observations": out_of_range,
            "imagery_not_intersecting": sum(not item.footprint_intersects_plot for item in imagery),
        },
        "source_type": "DERIVED",
        "disclaimer": "Transparent demonstration score; not an MRV verification result.",
    }


def start_scenario(db: Session, scenario_key: str, speed: int = 60, seed: int = 20260724) -> ScenarioRun:
    definition = SCENARIOS.get(scenario_key)
    if definition is None:
        raise ValueError("Unknown scenario")
    for existing in db.scalars(
        select(ScenarioRun).where(ScenarioRun.plot_id == DEMO_PLOT_ID, ScenarioRun.status.in_(["RUNNING", "PAUSED"]))
    ):
        existing.status = "CLOSED"
    state = {
        **definition["initial"],
        "rainfall_mm": 0.0,
        "forecast_rainfall_mm": 22.0 if scenario_key == "wait_rainfall" else 0.0,
        "pump_status": "OFF",
        "flow_rate_lps": 0.0,
        "recommendation": "MONITOR",
        "confidence": 87,
        "alert": None,
        "evidence_event": "Scenario initialized",
        "progress_percent": 0,
        "source_type": "SIMULATED",
    }
    run = ScenarioRun(
        scenario_key=scenario_key, plot_id=DEMO_PLOT_ID,
        status="RUNNING", speed=speed, seed=seed, tick=0,
        simulated_at=DEMO_NOW, state=state, outcome={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def tick_scenario(db: Session, run: ScenarioRun) -> ScenarioRun:
    if run.status != "RUNNING":
        return run
    definition = SCENARIOS[run.scenario_key]
    tick = run.tick + 1
    rng = random.Random(run.seed + tick)
    state = dict(run.state)
    outcome = dict(run.outcome)
    key = run.scenario_key
    progress = min(100, round(100 * tick / definition["duration_ticks"]))

    if key == "normal_awd":
        state["water_level_cm"] = round(4 - tick * 2.4, 1) if tick < 7 else round(-12 + (tick - 6) * 6.5, 1)
        state["soil_moisture_percent"] = round(68 - min(tick, 7) * 3.0 + max(0, tick - 7) * 5, 1)
        state["recommendation"] = "IRRIGATE" if tick == 7 else ("ACTION_COMPLETED" if tick >= 9 else "MONITOR")
        state["pump_status"] = "ON" if tick in {8, 9} else "OFF"
        state["flow_rate_lps"] = 12.4 if state["pump_status"] == "ON" else 0.0
        outcome.update({"awd_cycles_completed": 1 if tick >= 10 else 0})
    elif key == "wait_rainfall":
        if tick < 5:
            state["water_level_cm"] = round(-12 - tick * 0.4, 1)
            state["recommendation"] = "WAIT_12_HOURS"
        else:
            rain = round(16.5 + rng.random(), 1)
            state.update({
                "rainfall_mm": rain, "water_level_cm": round(-13.6 + (tick - 4) * 4.2, 1),
                "soil_moisture_percent": min(78, state["soil_moisture_percent"] + 5),
                "recommendation": "PUMP_AVOIDED", "evidence_event": "Rain gauge observation received",
            })
            outcome.update({
                "pumping_hours_avoided": 3.2, "water_saved_m3": 142.0,
                "electricity_avoided_kwh": 12.8, "cost_avoided_thb": 58.0,
                "source_type": "DERIVED",
            })
    elif key == "overdrying":
        state["water_level_cm"] = round(-17 - tick * 1.1, 1)
        state["soil_moisture_percent"] = round(34 - tick * 1.4, 1)
        state["recommendation"] = "IRRIGATE_NOW"
        state["alert"] = "CRITICAL: Over-drying risk"
    elif key == "flood_risk":
        state["rainfall_mm"] = round(tick * 9.5, 1)
        state["water_level_cm"] = round(2 + tick * 3.1, 1)
        state["recommendation"] = "DRAIN"
        state["alert"] = "HIGH: Flood candidate layer activated"
    elif key == "sensor_offline":
        state["confidence"] = max(48, 87 - tick * 7)
        state["recommendation"] = "FALLBACK_ESTIMATE"
        state["alert"] = "HIGH: Primary water-level sensor offline"
        state["evidence_event"] = "Maintenance task created"
    elif key == "sensor_drift":
        state["sensor_a_cm"] = round(-8 - tick * 0.4, 1)
        state["sensor_b_cm"] = round(-8 + tick * 1.1, 1)
        state["confidence"] = max(55, 87 - tick * 5)
        state["alert"] = "MEDIUM: Sensor disagreement exceeds tolerance"
        state["recommendation"] = "CALIBRATION_REVIEW"
    elif key == "false_field_report":
        state.update({
            "manual_report": "IRRIGATION_COMPLETED", "pump_status": "OFF",
            "flow_rate_lps": 0.0, "recommendation": "FIELD_VERIFICATION_REQUIRED",
            "alert": "HIGH: DATA CONFLICT", "evidence_event": "Manual evidence rejected",
        })
    elif key == "public_disagreement":
        state.update({
            "local_rainfall_mm": 8.4, "public_station_rainfall_mm": 0.0,
            "recommendation": "REVIEW_SPATIAL_CONTEXT",
            "alert": "MEDIUM: Public-data disagreement",
            "evidence_event": "Point sensor and regional station retained with limitations",
        })
    elif key == "satellite_conflict":
        state.update({
            "manual_water_state": "DRY", "satellite_water_indicator": "WET_CANDIDATE",
            "recommendation": "SATELLITE_REVIEW_REQUIRED",
            "alert": "MEDIUM: Satellite observation conflict",
            "evidence_event": "Review item created; neither source auto-overrides the other",
        })
    elif key == "complete_mrv":
        stages = ["REGISTERED", "PLANTED", "AWD_1", "FERTILIZED", "AWD_2", "SATELLITE_REVIEW",
                  "AWD_3", "FIELD_EVIDENCE", "HARVESTED", "YIELD_RECORDED", "MRV_REVIEW", "PACKAGE_READY"]
        state["season_stage"] = stages[min(tick - 1, len(stages) - 1)]
        state["recommendation"] = "CONTINUE_SEASON_WORKFLOW"
        outcome.update({
            "evidence_completeness_percent": min(94, 40 + tick * 5),
            "mrv_readiness_percent": min(88, 28 + tick * 5),
            "methodology_status": "NOT_CONFIGURED",
            "verified_amount": None,
        })

    state["progress_percent"] = progress
    state["simulation_tick"] = tick
    run.tick = tick
    run.simulated_at = run.simulated_at + timedelta(minutes=max(1, run.speed))
    run.state = state
    run.outcome = outcome
    if tick >= definition["duration_ticks"]:
        run.status = "COMPLETED"
    db.add(TwinStateSnapshot(
        plot_id=run.plot_id, state={
            **state, "scenario_key": key, "updated_at": run.simulated_at.isoformat(),
            "source_type": "DERIVED",
        },
        model_version=TWIN_MODEL_VERSION, source_type="DERIVED",
        simulated_at=run.simulated_at,
    ))
    db.commit()
    db.refresh(run)
    return run


def executive_overview(db: Session) -> dict[str, Any]:
    state = build_twin_state(db)
    quality = quality_breakdown(db)
    plots = list(db.scalars(select(Plot)))
    devices = list(db.scalars(select(SensorDevice)))
    evidence = list(db.scalars(select(EvidenceRecord)))
    alerts = list(db.scalars(select(Alert).where(Alert.status == "OPEN")))
    imagery_count = db.scalar(select(func.count()).select_from(Imagery)) or 0
    accepted_evidence = sum(item.review_status == "ACCEPTED" for item in evidence)
    active_run = db.scalar(
        select(ScenarioRun).where(ScenarioRun.status.in_(["RUNNING", "PAUSED"]))
        .order_by(ScenarioRun.updated_at.desc()).limit(1)
    )
    kpis = [
        ("total_area", "พื้นที่ติดตาม", round(sum(plot.area_rai for plot in plots), 1), "ไร่", "REFERENCE"),
        ("active_plots", "แปลงใช้งาน", len(plots), "แปลง", "DERIVED"),
        ("drying_plots", "แปลงช่วงปล่อยแห้ง", sum("แห้ง" in plot.water_state or "DRY" in plot.water_state for plot in plots), "แปลง", "DERIVED"),
        ("sensors_online", "เซนเซอร์พร้อมใช้", sum(device.status in {"ONLINE", "WARNING", "SIMULATED"} for device in devices), f"/ {len(devices)}", "DERIVED"),
        ("water_saved", "น้ำที่ประหยัดโดยประมาณ", 428, "m³/30 วัน", "DERIVED"),
        ("energy_saved", "พลังงานที่หลีกเลี่ยง", 38.4, "kWh/30 วัน", "DERIVED"),
        ("cost_saved", "ต้นทุนที่หลีกเลี่ยง", 176, "บาท/30 วัน", "DERIVED"),
        ("ghg_estimate", "GHG reduction estimate", 0.0, "ไม่คำนวณ", "DERIVED"),
        ("data_confidence", "ความเชื่อมั่นข้อมูล", quality["data_quality_score"], "%", "DERIVED"),
        ("mrv_readiness", "ความพร้อม MRV", 68, "%", "DERIVED"),
        ("evidence_complete", "หลักฐานผ่านการทบทวน", round(100 * accepted_evidence / max(1, len(evidence))), "%", "DERIVED"),
        ("active_alerts", "Alerts ที่เปิดอยู่", len(alerts), "รายการ", "DERIVED"),
    ]
    return {
        "project": {
            "id": "PROJECT-RICE-DEMO",
            "name": "Ultimate Low-Carbon Rice Digital Twin",
            "is_demo": True,
            "boundary_warning": DEMO_BOUNDARY_WARNING,
        },
        "kpis": [
            {
                "key": key, "label": label, "value": value, "unit": unit,
                "source_type": source_type, "period": "ล่าสุด / 30 วันตามที่ระบุ",
                "last_updated": DEMO_NOW.isoformat(),
                "tooltip": "ค่าจากข้อมูลสาธิตและสูตรที่อธิบายได้",
            }
            for key, label, value, unit, source_type in kpis
        ],
        "twin_state": state,
        "quality": quality,
        "sensor_health": {
            "online": sum(device.status in {"ONLINE", "WARNING", "SIMULATED"} for device in devices),
            "total": len(devices),
            "source_type": "DERIVED",
        },
        "satellite_coverage": {"items": imagery_count, "source_type": "PUBLIC"},
        "active_alerts": len(alerts),
        "active_scenario": serialize_scenario_run(active_run) if active_run else None,
        "methodology_status": "NOT_CONFIGURED",
        "carbon_credit_claim": False,
        "provenance_types": PROVENANCE_TYPES,
    }


def serialize_scenario_run(run: ScenarioRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id, "scenario_key": run.scenario_key,
        "definition": SCENARIOS.get(run.scenario_key),
        "status": run.status, "speed": run.speed, "seed": run.seed,
        "tick": run.tick, "simulated_at": run.simulated_at,
        "state": run.state, "outcome": run.outcome,
        "updated_at": run.updated_at,
    }
