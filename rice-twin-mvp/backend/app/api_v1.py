import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    AlgorithmVersion,
    Alert,
    AWDRuleConfiguration,
    BaselineEvidenceItem,
    CropSeason,
    CropStateObservation,
    DecisionEvent,
    EvidenceRecord,
    Farmer,
    FarmerGroup,
    HistoricalCropSeason,
    Imagery,
    ImageryAsset,
    ImageryBandMapping,
    ImageryPlotMetric,
    ImageryProcessingRun,
    ImageryQualityResult,
    IoTGateway,
    Plot,
    Project,
    PublicDataSnapshot,
    RecurringZone,
    Recommendation,
    ScenarioRun,
    SensorChannel,
    SensorDevice,
    SensorLocationProposal,
    SensorObservation,
    TemporalAnalysisRun,
    TwinStateSnapshot,
)
from .config import settings
from .seed import DEMO_BOUNDARY_WARNING, DEMO_PLOT_ID
from .services.historical_imagery import (
    ALGORITHM_VERSION as HISTORICAL_ALGORITHM_VERSION,
    HISTORICAL_DISCLAIMERS,
    historical_baseline_payload,
    import_historical_archive,
    latest_analysis_run,
    timeline_payload,
)
from .services.raster import create_preview
from .services.public_data import ADAPTERS
from .services.ultimate import (
    PROVENANCE_TYPES,
    SCENARIOS,
    build_twin_state,
    evaluate_awd_transparent,
    executive_overview,
    quality_breakdown,
    serialize_scenario_run,
    start_scenario,
    tick_scenario,
    validate_observation,
)


router = APIRouter(prefix="/api/v1", tags=["Ultimate Digital Twin v1"])


def envelope(request: Request, data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "request_id": getattr(request.state, "request_id", str(uuid4())),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": True,
            "boundary_warning": DEMO_BOUNDARY_WARNING,
            **(meta or {}),
        },
    }


def device_dict(item: SensorDevice) -> dict[str, Any]:
    return {
        "device_id": item.id,
        "device_name": item.device_name,
        "device_type": item.device_type,
        "manufacturer": item.manufacturer,
        "model": item.model,
        "serial_number": item.serial_number,
        "firmware_version": item.firmware_version,
        "plot_id": item.plot_id,
        "gateway_id": item.gateway_id,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "installation_date": item.installation_date,
        "installation_depth_cm": item.installation_depth_cm,
        "installation_elevation_m": item.installation_elevation_m,
        "communication_protocol": item.communication_protocol,
        "battery_percent": item.battery_percent,
        "signal_rssi": item.signal_rssi,
        "last_seen_at": item.last_seen_at,
        "calibration_due_at": item.calibration_due_at,
        "status": item.status,
        "source_type": item.source_type,
        "is_simulated": item.is_simulated,
        "metadata": item.metadata_json,
    }


def observation_dict(item: SensorObservation) -> dict[str, Any]:
    return {
        "id": item.id,
        "device_id": item.device_id,
        "plot_id": item.plot_id,
        "crop_season_id": item.crop_season_id,
        "metric": item.metric,
        "value": item.value,
        "unit": item.unit,
        "source_type": item.source_type,
        "source_name": item.source_name,
        "observed_at": item.observed_at,
        "retrieved_at": item.retrieved_at,
        "quality_flag": item.quality_flag,
        "is_demo": item.is_demo,
        "ingestion_protocol": item.ingestion_protocol,
        "external_id": item.external_id,
    }


class ObservationCreate(BaseModel):
    device_id: str
    plot_id: str = DEMO_PLOT_ID
    crop_season_id: str | None = None
    metric: str
    value: float
    unit: str
    observed_at: datetime
    source_type: str = Field(default="LIVE")
    source_name: str = Field(default="HTTP webhook")
    ingestion_protocol: str = Field(default="HTTP")
    external_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ScenarioStart(BaseModel):
    scenario_key: str
    speed: int = Field(default=60, ge=1, le=1440)
    seed: int = 20260724


class ScenarioControl(BaseModel):
    action: str = Field(pattern="^(pause|resume|reset|tick)$")


class DecisionCreate(BaseModel):
    lifecycle_status: str
    actor: str
    reason: str | None = None
    outcome: dict[str, Any] = Field(default_factory=dict)


@router.get("/overview")
def get_overview(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    return envelope(request, executive_overview(db), {"provenance_types": PROVENANCE_TYPES})


@router.get("/projects")
def list_projects(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Project).order_by(Project.id)).all()
    return envelope(request, [{
        "id": row.id, "name": row.name, "description": row.description,
        "status": row.status, "source_type": row.source_type, "is_demo": row.is_demo,
    } for row in rows])


@router.get("/farmer-groups")
def list_farmer_groups(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(FarmerGroup).order_by(FarmerGroup.id)).all()
    return envelope(request, [{
        "id": row.id, "project_id": row.project_id, "name": row.name,
        "province": row.province, "source_type": row.source_type,
    } for row in rows])


@router.get("/farmers")
def list_farmers(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Farmer).order_by(Farmer.id)).all()
    return envelope(request, [{
        "id": row.id, "group_id": row.group_id, "display_name": row.display_name,
        "phone_masked": row.phone_masked, "source_type": row.source_type, "is_demo": row.is_demo,
    } for row in rows])


@router.get("/plots")
def list_plots_v1(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Plot).order_by(Plot.id)).all()
    return envelope(request, [{
        "id": row.id, "project_id": row.project_id, "farmer_id": row.farmer_id,
        "name": row.name, "center": [row.center_lon, row.center_lat],
        "area_rai": row.area_rai, "boundary_source": row.boundary_source,
        "boundary_warning": DEMO_BOUNDARY_WARNING if row.boundary_source == "synthetic_demo" else None,
        "crop_stage": row.crop_stage, "water_state": row.water_state,
        "water_level_cm": row.water_level_cm, "data_confidence_score": row.data_confidence_score,
        "source_type": "REFERENCE", "is_demo": row.boundary_source == "synthetic_demo",
    } for row in rows])


@router.get("/crop-seasons")
def list_crop_seasons_v1(
    request: Request, plot_id: str | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    statement = select(CropSeason).order_by(CropSeason.started_at.desc())
    if plot_id:
        statement = statement.where(CropSeason.plot_id == plot_id)
    rows = db.scalars(statement).all()
    return envelope(request, [{
        "id": row.id, "plot_id": row.plot_id, "season_name": row.name,
        "crop_year": row.crop_year, "rice_variety": row.rice_variety,
        "planting_method": row.planting_method, "planting_date": row.planting_date,
        "expected_harvest_date": row.expected_harvest_date,
        "actual_harvest_date": row.actual_harvest_date,
        "season_status": row.status.upper(), "baseline_scenario": row.baseline_scenario,
        "project_scenario": row.project_scenario,
        "methodology_version": row.methodology_version,
        "source_type": "MANUAL", "is_demo": True,
    } for row in rows])


@router.get("/gateways")
def list_gateways(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(IoTGateway).order_by(IoTGateway.id)).all()
    return envelope(request, [{
        "gateway_id": row.id, "name": row.name, "plot_id": row.plot_id,
        "protocol": row.protocol, "status": row.status, "last_seen_at": row.last_seen_at,
        "source_type": row.source_type, "configuration": row.configuration,
    } for row in rows])


@router.get("/devices")
def list_devices(
    request: Request, plot_id: str | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    statement = select(SensorDevice).order_by(SensorDevice.id)
    if plot_id:
        statement = statement.where(SensorDevice.plot_id == plot_id)
    return envelope(request, [device_dict(item) for item in db.scalars(statement).all()])


@router.get("/devices/{device_id}")
def get_device(device_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SensorDevice, device_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found")
    channels = db.scalars(
        select(SensorChannel).where(SensorChannel.device_id == device_id)
    ).all()
    return envelope(request, {
        **device_dict(item),
        "channels": [{
            "id": row.id, "channel_key": row.channel_key, "metric": row.metric,
            "unit": row.unit, "minimum_value": row.minimum_value,
            "maximum_value": row.maximum_value, "depth_cm": row.depth_cm,
            "enabled": row.enabled,
        } for row in channels],
    })


@router.get("/observations")
def list_observations(
    request: Request,
    plot_id: str = DEMO_PLOT_ID,
    metric: str | None = None,
    limit: int = Query(default=240, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = (
        select(SensorObservation)
        .where(SensorObservation.plot_id == plot_id)
        .order_by(SensorObservation.observed_at.desc())
        .limit(limit)
    )
    if metric:
        statement = statement.where(SensorObservation.metric == metric)
    return envelope(request, [observation_dict(item) for item in db.scalars(statement).all()])


@router.post("/observations", status_code=status.HTTP_201_CREATED)
def ingest_observation(
    payload: ObservationCreate, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    if payload.source_type not in PROVENANCE_TYPES:
        raise HTTPException(status_code=422, detail="Unknown source_type")
    if db.get(SensorDevice, payload.device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    errors = validate_observation(payload.metric, payload.value)
    if errors:
        raise HTTPException(status_code=422, detail={"quality_flag": "out_of_range", "errors": errors})
    season_id = payload.crop_season_id
    if season_id is None:
        season = db.scalar(
            select(CropSeason).where(CropSeason.plot_id == payload.plot_id, CropSeason.status == "active")
            .order_by(CropSeason.started_at.desc()).limit(1)
        )
        season_id = season.id if season else None
    item = SensorObservation(
        device_id=payload.device_id, plot_id=payload.plot_id,
        crop_season_id=season_id, metric=payload.metric, value=payload.value,
        unit=payload.unit, observed_at=payload.observed_at,
        retrieved_at=datetime.now(timezone.utc), source_type=payload.source_type,
        source_name=payload.source_name, quality_flag="valid",
        is_demo=payload.source_type != "LIVE", ingestion_protocol=payload.ingestion_protocol,
        external_id=payload.external_id, payload=payload.payload,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate observation") from exc
    db.refresh(item)
    return envelope(request, observation_dict(item))


@router.get("/twin-states/current")
def current_twin_state(
    request: Request, plot_id: str = DEMO_PLOT_ID, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return envelope(request, build_twin_state(db, plot_id))


@router.get("/twin-states/history")
def twin_state_history(
    request: Request, plot_id: str = DEMO_PLOT_ID, limit: int = 100,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = db.scalars(
        select(TwinStateSnapshot).where(TwinStateSnapshot.plot_id == plot_id)
        .order_by(TwinStateSnapshot.created_at.desc()).limit(min(max(limit, 1), 500))
    ).all()
    return envelope(request, [{
        "id": row.id, "plot_id": row.plot_id, "crop_season_id": row.crop_season_id,
        "state": row.state, "model_version": row.model_version,
        "source_type": row.source_type, "simulated_at": row.simulated_at,
        "created_at": row.created_at,
    } for row in rows])


@router.get("/rules/evaluate")
def evaluate_rules_v1(
    request: Request, plot_id: str = DEMO_PLOT_ID, db: Session = Depends(get_db)
) -> dict[str, Any]:
    twin = build_twin_state(db, plot_id)
    config = db.scalar(
        select(AWDRuleConfiguration).where(AWDRuleConfiguration.status == "ACTIVE")
        .order_by(AWDRuleConfiguration.effective_at.desc()).limit(1)
    )
    if config is None:
        raise HTTPException(status_code=503, detail="AWD rule configuration unavailable")
    result = evaluate_awd_transparent(twin, config.parameters)
    recommendation = Recommendation(
        plot_id=plot_id, crop_season_id=twin.get("crop_season_id"),
        recommendation=result["recommendation"], severity=result["severity"],
        rule_version=result["rule_version"], reasons=result["reasons"],
        inputs_used=result["inputs_used"], confidence=result["confidence"],
        next_review_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    db.add(recommendation)
    db.commit()
    result["recommendation_id"] = recommendation.id
    return envelope(request, result)


@router.get("/recommendations")
def list_recommendations(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Recommendation).order_by(Recommendation.created_at.desc()).limit(100)).all()
    return envelope(request, [{
        "id": row.id, "plot_id": row.plot_id, "recommendation": row.recommendation,
        "severity": row.severity, "status": row.status, "rule_version": row.rule_version,
        "reasons": row.reasons, "inputs_used": row.inputs_used,
        "confidence": row.confidence, "created_at": row.created_at,
    } for row in rows])


@router.post("/recommendations/{recommendation_id}/decisions")
def create_decision(
    recommendation_id: str, payload: DecisionCreate, request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    recommendation = db.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    recommendation.status = payload.lifecycle_status
    event = DecisionEvent(
        recommendation_id=recommendation_id, lifecycle_status=payload.lifecycle_status,
        actor=payload.actor, reason=payload.reason, outcome=payload.outcome,
    )
    db.add(event)
    db.commit()
    return envelope(request, {
        "id": event.id, "recommendation_id": recommendation_id,
        "lifecycle_status": event.lifecycle_status, "actor": event.actor,
        "reason": event.reason, "outcome": event.outcome, "created_at": event.created_at,
    })


@router.get("/data-quality")
def get_data_quality(
    request: Request, plot_id: str = DEMO_PLOT_ID, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return envelope(request, quality_breakdown(db, plot_id))


@router.get("/alerts")
def list_alerts_v1(
    request: Request, status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = select(Alert).order_by(Alert.created_at.desc())
    if status_filter:
        statement = statement.where(Alert.status == status_filter)
    rows = db.scalars(statement).all()
    return envelope(request, [{
        "id": row.id, "alert_type": row.alert_type, "title": row.title,
        "severity": row.severity, "status": row.status, "plot_id": row.plot_id,
        "device_id": row.device_id, "assigned_to": row.assigned_to,
        "detail": row.detail, "source_type": row.source_type,
        "created_at": row.created_at, "due_at": row.due_at,
    } for row in rows])


@router.get("/evidence")
def list_evidence(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(EvidenceRecord).order_by(EvidenceRecord.uploaded_at.desc())).all()
    return envelope(request, [{
        "evidence_id": row.id, "evidence_type": row.evidence_type,
        "plot_id": row.plot_id, "crop_season_id": row.crop_season_id,
        "activity_id": row.activity_id, "title": row.title,
        "captured_at": row.captured_at, "uploaded_at": row.uploaded_at,
        "captured_by": row.captured_by, "latitude": row.latitude,
        "longitude": row.longitude, "file_hash": row.file_hash,
        "source_type": row.source_type, "review_status": row.review_status,
        "reviewed_by": row.reviewed_by, "review_note": row.review_note,
        "metadata": row.metadata_json,
    } for row in rows])


@router.get("/public-data")
def list_public_data(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    snapshots = db.scalars(
        select(PublicDataSnapshot).order_by(PublicDataSnapshot.observed_at.desc())
    ).all()
    return envelope(request, {
        "snapshots": [{
            "id": row.id, "category": row.category, "provider": row.provider,
            "station_name": row.station_name, "plot_id": row.plot_id,
            "observed_at": row.observed_at, "retrieved_at": row.retrieved_at,
            "latitude": row.latitude, "longitude": row.longitude,
            "distance_km": row.distance_km, "quality_flag": row.quality_flag,
            "licence_status": row.licence_status, "source_type": row.source_type,
            "payload": row.payload, "limitations": row.limitations,
        } for row in snapshots],
        "adapters": {
            key: {
                "status": adapter.report_status(),
                "current": adapter.fetch_current(),
                "forecast": adapter.fetch_forecast(),
            }
            for key, adapter in ADAPTERS.items()
        },
    })


@router.get("/imagery")
def list_imagery_v1(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Imagery).order_by(Imagery.captured_at.desc().nullslast())).all()
    legacy = [{
        "id": row.id, "plot_id": row.plot_id, "filename": row.original_filename,
        "acquired_at": row.captured_at, "sensor": (row.source_metadata or {}).get("satellite", "Uploaded"),
        "crs": row.crs, "bounds": row.bounds_wgs84,
        "width": row.width, "height": row.height, "band_count": row.band_count,
        "sha256": row.sha256, "plot_intersection": row.footprint_intersects_plot,
        "processing_status": row.processing_status,
        "source_type": "PUBLIC" if row.source == "downloaded_catalog" else "MANUAL",
        "metadata": row.source_metadata, "preview_url": f"/api/imagery/{row.id}/preview.png",
        "limitations": "Analytical indicator; not direct verification of AWD compliance.",
    } for row in rows]
    historical_rows = db.scalars(
        select(ImageryAsset).order_by(ImageryAsset.acquisition_datetime.desc().nullslast())
    ).all()
    historical = [{
        "id": row.id,
        "plot_id": row.plot_id,
        "filename": row.original_filename,
        "acquired_at": row.acquisition_datetime,
        "sensor": row.source_name,
        "crs": row.crs,
        "bounds": row.bounds,
        "width": row.width,
        "height": row.height,
        "band_count": row.band_count,
        "sha256": row.sha256,
        "plot_intersection_percent": row.plot_intersection_percent,
        "processing_status": row.processing_status,
        "processing_error": row.processing_error,
        "source_type": row.source_type,
        "quality_score": row.quality_score,
        "metadata": row.metadata_json,
        "preview_url": f"/api/v1/imagery/{row.id}/preview.png",
        "limitations": "Historical analytical evidence; not direct verification of AWD compliance.",
    } for row in historical_rows]
    return envelope(request, legacy + historical)


@router.get("/scenarios")
def list_scenarios(request: Request) -> dict[str, Any]:
    return envelope(request, [
        {"key": key, **definition, "source_type": "REFERENCE"}
        for key, definition in sorted(SCENARIOS.items(), key=lambda item: item[1]["number"])
    ])


@router.post("/scenarios/start")
def start_scenario_v1(
    payload: ScenarioStart, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        run = start_scenario(db, payload.scenario_key, payload.speed, payload.seed)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return envelope(request, serialize_scenario_run(run))


@router.get("/scenarios/current")
def current_scenario(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.scalar(
        select(ScenarioRun).where(ScenarioRun.status.in_(["RUNNING", "PAUSED"]))
        .order_by(ScenarioRun.updated_at.desc()).limit(1)
    )
    return envelope(request, serialize_scenario_run(run))


@router.post("/scenarios/{run_id}/control")
def control_scenario(
    run_id: str, payload: ScenarioControl, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    run = db.get(ScenarioRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    if payload.action == "tick":
        run = tick_scenario(db, run)
    elif payload.action == "pause":
        run.status = "PAUSED"
        db.commit()
    elif payload.action == "resume":
        run.status = "RUNNING"
        db.commit()
    elif payload.action == "reset":
        run.tick = 0
        run.status = "RUNNING"
        run.state = {**SCENARIOS[run.scenario_key]["initial"], "progress_percent": 0, "source_type": "SIMULATED"}
        run.outcome = {}
        db.commit()
    db.refresh(run)
    return envelope(request, serialize_scenario_run(run))


@router.get("/carbon")
def carbon_v1(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    evidence_count = len(db.scalars(select(EvidenceRecord)).all())
    return envelope(request, {
        "status": "METHODOLOGY_NOT_CONFIGURED",
        "message": "Carbon-credit issuance cannot be claimed. Displayed values are demonstration estimates only.",
        "monitoring_data": {"water_management": "available", "fertilizer": "partial", "energy": "available"},
        "calculated_estimate": None,
        "eligible_estimate": None,
        "verified_amount": None,
        "issued_credits": None,
        "baseline_emission_estimate": None,
        "project_emission_estimate": None,
        "estimated_reduction": None,
        "calculation_version": "placeholder-1.0",
        "methodology_version": None,
        "emission_factor_version": None,
        "evidence_records": evidence_count,
        "readiness_percent": 68,
        "source_type": "DERIVED",
        "limitations": [
            "No approved methodology is configured",
            "No verified emission factors are configured",
            "No carbon-credit amount is calculated or claimed",
        ],
    })


@router.get("/roles")
def demo_roles(request: Request) -> dict[str, Any]:
    roles = [
        "FARMER", "FIELD_OFFICER", "FARM_MANAGER", "WATER_MANAGER", "AGRONOMIST",
        "CARBON_SPECIALIST", "PROJECT_MANAGER", "VERIFIER", "EXECUTIVE",
        "PUBLIC_VIEWER", "ADMIN",
    ]
    return envelope(request, {
        "roles": roles,
        "demo_switcher": True,
        "security_warning": "Role switching is demonstration UI, not production authentication.",
    })


@router.get("/assistant")
def assistant_answer(
    request: Request, question: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    q = question.lower()
    state = build_twin_state(db)
    quality = quality_breakdown(db)
    if "why" in q or "ทำไม" in q or "irrigation" in q or "ให้น้ำ" in q:
        answer = state["rule_evaluation"]["reasons"]
        topic = "irrigation_recommendation"
    elif "sensor" in q or "เซนเซอร์" in q or "confidence" in q:
        answer = [
            f"Sensor reliability score is {quality['components']['sensor_reliability_score']}%",
            f"Offline devices: {quality['checks']['sensor_offline']}",
            f"Weak-signal devices: {quality['checks']['signal_weak']}",
        ]
        topic = "data_confidence"
    elif "evidence" in q or "หลักฐาน" in q or "mrv" in q:
        answer = [
            f"Evidence quality score is {quality['components']['evidence_quality_score']}%",
            "Pending or rejected evidence must be reviewed before verification readiness can improve",
            "Carbon methodology is not configured",
        ]
        topic = "mrv_evidence"
    else:
        answer = [
            f"Current water level: {state['water_level_cm']} cm",
            f"Recommendation: {state['irrigation_recommendation']}",
            f"Data confidence: {state['data_confidence']}%",
        ]
        topic = "current_state"
    return envelope(request, {
        "question": question, "topic": topic, "answer": answer,
        "supported_by": ["Twin state", "AWD-DEMO-1.0", "Data-quality engine"],
        "source_type": "DERIVED",
        "external_llm_used": False,
    })


REPORT_TYPES = {
    "executive-summary": "Executive Summary",
    "plot-digital-twin": "Plot Digital Twin Report",
    "iot-health": "IoT Health Report",
    "awd-cycle": "AWD Cycle Report",
    "water-use": "Water-use Report",
    "data-quality": "Data-quality Report",
    "mrv-readiness": "MRV Readiness Report",
    "evidence-index": "Evidence Index",
    "verification-package": "Verification Package",
    "scenario-outcome": "Scenario Outcome Report",
}


@router.get("/reports")
def list_reports(request: Request) -> dict[str, Any]:
    return envelope(request, [{
        "key": key, "title": title,
        "html_url": f"/api/v1/reports/{key}.html",
        "json_url": f"/api/v1/reports/{key}.json",
        "csv_url": f"/api/v1/reports/{key}.csv",
    } for key, title in REPORT_TYPES.items()])


def report_payload(db: Session, report_key: str) -> dict[str, Any]:
    if report_key not in REPORT_TYPES:
        raise HTTPException(status_code=404, detail="Report type not found")
    return {
        "report": REPORT_TYPES[report_key],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_period": "2026-06-25 to 2026-07-24 demonstration period",
        "overview": executive_overview(db),
        "provenance_summary": list(PROVENANCE_TYPES),
        "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
        "methodology_warning": "METHODOLOGY NOT CONFIGURED — no carbon-credit claim can be made.",
        "limitations": [
            "All device readings in this package are simulated",
            "Public-data records are sample snapshots",
            "The plot boundary is synthetic",
        ],
    }


@router.get("/reports/{report_key}.json")
def report_json(report_key: str, db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(jsonable_encoder(report_payload(db, report_key)))


@router.get("/reports/{report_key}.csv")
def report_csv(report_key: str, db: Session = Depends(get_db)) -> StreamingResponse:
    payload = report_payload(db, report_key)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["field", "value", "source_type"])
    writer.writerow(["report", payload["report"], "REFERENCE"])
    writer.writerow(["generated_at", payload["generated_at"], "DERIVED"])
    writer.writerow(["boundary_warning", payload["synthetic_boundary_warning"], "REFERENCE"])
    for kpi in payload["overview"]["kpis"]:
        writer.writerow([kpi["key"], f"{kpi['value']} {kpi['unit']}", kpi["source_type"]])
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{report_key}.csv"'},
    )


@router.get("/reports/{report_key}.html", response_class=HTMLResponse)
def report_html(report_key: str, db: Session = Depends(get_db)) -> str:
    payload = report_payload(db, report_key)
    kpis = "".join(
        f"<tr><td>{item['label']}</td><td>{item['value']} {item['unit']}</td>"
        f"<td>{item['source_type']}</td></tr>"
        for item in payload["overview"]["kpis"]
    )
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
    <title>{payload['report']}</title><style>
    body{{font-family:system-ui;max-width:960px;margin:40px auto;color:#173328}}
    h1{{color:#115b3b}}.warning{{padding:16px;background:#fff4d8;border:1px solid #d99c22}}
    table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}
    @media print{{button{{display:none}}}}</style></head><body>
    <button onclick="window.print()">Print / Save as PDF</button>
    <h1>{payload['report']}</h1><p>Generated: {payload['generated_at']}</p>
    <div class="warning"><strong>DEMO</strong><p>{DEMO_BOUNDARY_WARNING}</p>
    <p>{payload['methodology_warning']}</p></div>
    <h2>Executive indicators</h2><table><thead><tr><th>Metric</th><th>Value</th><th>Provenance</th></tr></thead>
    <tbody>{kpis}</tbody></table><h2>Limitations</h2>
    <ul>{''.join(f'<li>{item}</li>' for item in payload['limitations'])}</ul></body></html>"""


# ---------------------------------------------------------------------------
# Historical imagery and baseline API


class HistoricalImportRequest(BaseModel):
    force_analysis: bool = False


def _historical_asset_dict(asset: ImageryAsset) -> dict[str, Any]:
    return {
        "image_id": asset.id,
        "plot_id": asset.plot_id,
        "source_name": asset.source_name,
        "source_type": asset.source_type,
        "acquisition_datetime": asset.acquisition_datetime,
        "uploaded_at": asset.uploaded_at,
        "original_filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "crs": asset.crs,
        "resolution_x": asset.resolution_x,
        "resolution_y": asset.resolution_y,
        "width": asset.width,
        "height": asset.height,
        "band_count": asset.band_count,
        "band_names": asset.band_names,
        "cloud_cover_percent": asset.cloud_cover_percent,
        "quality_score": asset.quality_score,
        "bounds": asset.bounds,
        "footprint": asset.footprint,
        "plot_intersection_percent": asset.plot_intersection_percent,
        "sha256": asset.sha256,
        "license_status": asset.license_status,
        "processing_status": asset.processing_status,
        "processing_error": asset.processing_error,
        "is_demo": asset.is_demo,
        "metadata": asset.metadata_json,
        "preview_url": f"/api/v1/imagery/{asset.id}/preview.png",
    }


def _require_plot(db: Session, plot_id: str) -> Plot:
    plot = db.get(Plot, plot_id)
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    return plot


def _require_historical_run(db: Session, plot_id: str) -> TemporalAnalysisRun:
    run = latest_analysis_run(db, plot_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Historical analysis has not been run for this plot",
        )
    return run


@router.post("/imagery/bulk-import")
def bulk_import_historical_imagery(
    payload: HistoricalImportRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    plot = _require_plot(db, DEMO_PLOT_ID)
    result = import_historical_archive(
        db,
        plot,
        settings.historical_output_dir,
        force_analysis=payload.force_analysis,
    )
    return envelope(
        request,
        result,
        {
            "algorithm_version": HISTORICAL_ALGORITHM_VERSION,
            "source_archive": str(settings.historical_output_dir),
            "source_archive_mode": "READ_ONLY",
        },
    )


@router.get("/imagery/{image_id}")
def get_historical_image(
    image_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    asset = db.get(ImageryAsset, image_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Historical image not found")
    mapping = db.scalar(
        select(ImageryBandMapping)
        .where(ImageryBandMapping.imagery_asset_id == image_id)
        .order_by(ImageryBandMapping.created_at.desc())
        .limit(1)
    )
    quality = db.scalar(
        select(ImageryQualityResult)
        .where(ImageryQualityResult.imagery_asset_id == image_id)
        .order_by(ImageryQualityResult.processed_at.desc())
        .limit(1)
    )
    runs = list(
        db.scalars(
            select(ImageryProcessingRun)
            .where(ImageryProcessingRun.imagery_asset_id == image_id)
            .order_by(ImageryProcessingRun.started_at.desc())
        )
    )
    return envelope(
        request,
        {
            **_historical_asset_dict(asset),
            "band_mapping": mapping.mapping if mapping else None,
            "band_mapping_version": mapping.version if mapping else None,
            "quality_result": {
                "image_quality_score": quality.image_quality_score,
                "spatial_coverage_score": quality.spatial_coverage_score,
                "valid_pixel_fraction": quality.valid_pixel_fraction,
                "cloud_or_quality_status": quality.cloud_or_quality_status,
                "usable": quality.usable,
                "components": quality.components,
                "limitations": quality.limitations,
            }
            if quality
            else None,
            "processing_runs": [
                {
                    "run_id": item.id,
                    "algorithm_name": item.algorithm_name,
                    "algorithm_version": item.algorithm_version,
                    "status": item.status,
                    "started_at": item.started_at,
                    "completed_at": item.completed_at,
                    "parameters": item.parameters,
                    "processing_log": item.processing_log,
                    "error": item.error,
                }
                for item in runs
            ],
        },
    )


@router.post("/imagery/{image_id}/process")
def process_historical_image(
    image_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    asset = db.get(ImageryAsset, image_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Historical image not found")
    if asset.processing_status == "FAILED":
        raise HTTPException(
            status_code=422,
            detail=asset.processing_error or "Source scene failed validation",
        )
    plot = _require_plot(db, asset.plot_id)
    result = import_historical_archive(
        db, plot, settings.historical_output_dir, force_analysis=True
    )
    return envelope(
        request,
        {
            "image_id": image_id,
            "processing_status": asset.processing_status,
            "analysis": result,
        },
    )


@router.get("/imagery/{image_id}/metrics")
def get_historical_image_metrics(
    image_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    asset = db.get(ImageryAsset, image_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Historical image not found")
    metric = db.scalar(
        select(ImageryPlotMetric)
        .where(ImageryPlotMetric.imagery_asset_id == image_id)
        .order_by(ImageryPlotMetric.processed_at.desc())
        .limit(1)
    )
    if metric is None:
        raise HTTPException(status_code=404, detail="No metrics for this image")
    return envelope(
        request,
        {
            "image_id": image_id,
            "plot_id": metric.plot_id,
            "acquisition_datetime": metric.acquisition_datetime,
            "sensor": metric.sensor,
            "vegetation_score": metric.vegetation_score,
            "water_candidate_fraction": metric.water_candidate_fraction,
            "wet_soil_fraction": metric.wet_soil_fraction,
            "bare_soil_fraction": metric.bare_soil_fraction,
            "dense_vegetation_fraction": metric.dense_vegetation_fraction,
            "uncertain_fraction": metric.uncertain_fraction,
            "cultivated_area_estimate_rai": metric.cultivated_area_estimate_rai,
            "possible_harvested_area_rai": metric.possible_harvested_area_rai,
            "uniformity_score": metric.uniformity_score,
            "image_quality_score": metric.image_quality_score,
            "usable_plot_coverage": metric.usable_plot_coverage,
            "raw_metrics": metric.raw_metrics,
            "provenance": metric.provenance,
            "confidence": metric.confidence,
            "limitations": metric.limitations,
            "algorithm_version": metric.algorithm_version,
            "processed_at": metric.processed_at,
        },
    )


@router.get("/imagery/{image_id}/preview.png")
def historical_image_preview(
    image_id: str,
    mode: str = Query(default="auto"),
    db: Session = Depends(get_db),
) -> FileResponse:
    asset = db.get(ImageryAsset, image_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Historical image not found")
    if asset.processing_status == "FAILED":
        raise HTTPException(status_code=422, detail=asset.processing_error or "Image failed")
    allowed = {
        "auto",
        "true_color",
        "false_color",
        "ndvi",
        "lswi",
        "ndwi",
        "evi",
        "vv",
        "vh",
        "vh_vv_diff",
    }
    if mode not in allowed:
        raise HTTPException(status_code=422, detail=f"Unsupported preview mode: {mode}")
    if mode == "auto":
        mode = "true_color" if asset.source_name == "Sentinel-2" else "vv"
    optical = {
        "true_color": ([3, 2, 1], None),
        "false_color": ([4, 3, 2], None),
        "ndvi": ([7], "vegetation"),
        "lswi": ([8], "water"),
        "ndwi": ([9], "water"),
        "evi": ([10], "vegetation"),
    }
    radar = {
        "vv": ("VV_dB.tif", None),
        "vh": ("VH_dB.tif", None),
        "vh_vv_diff": ("VH_VV_diff_dB.tif", "water"),
    }
    if asset.source_name == "Sentinel-2" and mode not in optical:
        raise HTTPException(status_code=422, detail="Mode is not valid for Sentinel-2")
    if asset.source_name == "Sentinel-1" and mode not in radar:
        raise HTTPException(status_code=422, detail="Mode is not valid for Sentinel-1")
    source_path = Path(asset.source_path)
    bands: list[int]
    color_scheme: str | None
    if asset.source_name == "Sentinel-2":
        bands, color_scheme = optical[mode]
    else:
        radar_filename, color_scheme = radar[mode]
        source_path = source_path.parent / radar_filename
        bands = [1]
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source raster is unavailable")
    preview_path = settings.imagery_dir / "historical-previews" / f"{image_id}-{mode}.png"
    if not preview_path.exists():
        create_preview(
            source_path,
            preview_path,
            requested_bands=bands,
            max_dimension=1000,
            color_scheme=color_scheme,
        )
    return FileResponse(
        preview_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/plots/{plot_id}/imagery-timeline")
def get_imagery_timeline(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_plot(db, plot_id)
    run = _require_historical_run(db, plot_id)
    states = {
        item.imagery_asset_id: {
            "state": item.state,
            "confidence": item.confidence,
            "explanation": item.explanation,
        }
        for item in db.scalars(
            select(CropStateObservation).where(
                CropStateObservation.temporal_analysis_run_id == run.id
            )
        )
    }
    timeline = timeline_payload(db, plot_id)
    for item in timeline:
        item["derived_field_state"] = states.get(item["image_id"])
        item["preview_url"] = f"/api/v1/imagery/{item['image_id']}/preview.png"
        item["public_rainfall_context"] = {
            "status": "CONTEXT_NOT_MATCHED_TO_SCENE",
            "provenance": "UNKNOWN",
            "causal_claim": None,
        }
    return envelope(
        request,
        {
            "plot_id": plot_id,
            "analysis_run_id": run.id,
            "raw_observations": timeline,
            "smoothing": run.parameters,
            "temporal_gaps": run.result_summary.get("temporal_gaps", []),
        },
    )


@router.post("/plots/{plot_id}/temporal-analysis")
def run_temporal_analysis(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    plot = _require_plot(db, plot_id)
    result = import_historical_archive(
        db, plot, settings.historical_output_dir, force_analysis=True
    )
    return envelope(request, result)


@router.get("/plots/{plot_id}/crop-cycles")
def get_historical_crop_cycles(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    run = _require_historical_run(db, plot_id)
    rows = list(
        db.scalars(
            select(HistoricalCropSeason)
            .where(HistoricalCropSeason.temporal_analysis_run_id == run.id)
            .order_by(HistoricalCropSeason.probable_start_date)
        )
    )
    return envelope(
        request,
        [
            {
                "season_id": row.id,
                "probable_start_date": row.probable_start_date,
                "probable_planting_window": [
                    row.probable_planting_window_start,
                    row.probable_planting_window_end,
                ],
                "probable_peak_date": row.probable_peak_date,
                "probable_harvest_window": [
                    row.probable_harvest_window_start,
                    row.probable_harvest_window_end,
                ],
                "estimated_crop_duration_days": row.estimated_crop_duration_days,
                "estimated_cultivated_area_rai": row.estimated_cultivated_area_rai,
                "estimated_harvested_area_rai": row.estimated_harvested_area_rai,
                "number_of_supporting_images": row.number_of_supporting_images,
                "confidence": row.confidence,
                "evidence_image_ids": row.evidence_image_ids,
                "limitations": row.limitations,
                "provenance": "ESTIMATED",
                "algorithm_version": row.algorithm_version,
            }
            for row in rows
        ],
    )


@router.get("/plots/{plot_id}/historical-baseline")
def get_historical_baseline(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_plot(db, plot_id)
    payload = historical_baseline_payload(db, plot_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Historical baseline is not available")
    return envelope(request, payload)


def _zone_dict(row: RecurringZone) -> dict[str, Any]:
    return {
        "zone_id": row.id,
        "plot_id": row.plot_id,
        "geometry": row.geometry_json,
        "zone_type": row.zone_type,
        "number_of_occurrences": row.number_of_occurrences,
        "number_of_usable_images": row.number_of_usable_images,
        "years_detected": row.years_detected,
        "season_ids": row.season_ids,
        "confidence": row.confidence,
        "supporting_images": row.supporting_images,
        "recommended_field_check": row.recommended_field_check,
        "limitations": row.limitations,
        "provenance": "DERIVED",
    }


@router.get("/plots/{plot_id}/recurring-zones")
def get_recurring_zones(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    run = _require_historical_run(db, plot_id)
    rows = list(
        db.scalars(
            select(RecurringZone).where(RecurringZone.temporal_analysis_run_id == run.id)
        )
    )
    return envelope(request, [_zone_dict(row) for row in rows])


@router.get("/plots/{plot_id}/baseline-evidence")
def get_baseline_evidence(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    run = _require_historical_run(db, plot_id)
    rows = list(
        db.scalars(
            select(BaselineEvidenceItem)
            .where(BaselineEvidenceItem.temporal_analysis_run_id == run.id)
            .order_by(BaselineEvidenceItem.claim_key)
        )
    )
    return envelope(
        request,
        [
            {
                "item_id": row.id,
                "claim_key": row.claim_key,
                "claim_label": row.claim_label,
                "support_level": row.support_level,
                "provenance": row.provenance,
                "conclusion": row.conclusion,
                "evidence_image_ids": row.evidence_image_ids,
                "limitations": row.limitations,
            }
            for row in rows
        ],
    )


@router.post("/plots/{plot_id}/sensor-location-analysis")
def run_sensor_location_analysis(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    plot = _require_plot(db, plot_id)
    result = import_historical_archive(
        db, plot, settings.historical_output_dir, force_analysis=True
    )
    proposals = list(
        db.scalars(
            select(SensorLocationProposal).where(
                SensorLocationProposal.temporal_analysis_run_id == result["analysis_run_id"]
            )
        )
    )
    return envelope(
        request,
        {
            "analysis_run_id": result["analysis_run_id"],
            "proposal_count": len(proposals),
            "status": "PROPOSED",
            "field_verification_status": "NOT_FIELD_VERIFIED",
        },
    )


def _proposal_dict(row: SensorLocationProposal) -> dict[str, Any]:
    return {
        "proposal_id": row.id,
        "plot_id": row.plot_id,
        "sensor_type": row.sensor_type,
        "geometry": {
            "type": "Point",
            "coordinates": [row.longitude, row.latitude],
        },
        "latitude": row.latitude,
        "longitude": row.longitude,
        "status": row.status,
        "field_verification_status": row.field_verification_status,
        "rationale": row.rationale,
        "confidence": row.confidence,
        "supporting_zone_ids": row.supporting_zone_ids,
        "assumptions": row.assumptions,
        "provenance": "DERIVED",
    }


@router.get("/plots/{plot_id}/sensor-location-proposals")
def get_sensor_location_proposals(
    plot_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    run = _require_historical_run(db, plot_id)
    rows = list(
        db.scalars(
            select(SensorLocationProposal).where(
                SensorLocationProposal.temporal_analysis_run_id == run.id
            )
        )
    )
    return envelope(request, [_proposal_dict(row) for row in rows])


@router.get("/analysis-runs/{run_id}")
def get_analysis_run(
    run_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    run = db.get(TemporalAnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return envelope(
        request,
        {
            "run_id": run.id,
            "plot_id": run.plot_id,
            "algorithm_version": run.algorithm_version,
            "status": run.status,
            "period": [run.period_start, run.period_end],
            "image_count": run.image_count,
            "usable_image_count": run.usable_image_count,
            "parameters": run.parameters,
            "quality_scores": run.quality_scores,
            "result_summary": run.result_summary,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        },
    )


@router.get("/algorithm-versions")
def get_algorithm_versions(
    request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    rows = list(
        db.scalars(select(AlgorithmVersion).order_by(AlgorithmVersion.algorithm_name))
    )
    return envelope(
        request,
        [
            {
                "algorithm_id": row.id,
                "algorithm_name": row.algorithm_name,
                "version": row.version,
                "description": row.description,
                "parameters": row.parameters,
                "source_type": row.source_type,
                "active": row.active,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    )


def _export_metadata(run: TemporalAnalysisRun) -> dict[str, Any]:
    return {
        "plot_id": run.plot_id,
        "analysis_period": [run.period_start, run.period_end],
        "image_count": run.image_count,
        "source_list": ["Sentinel-2", "Sentinel-1"],
        "algorithm_versions": [run.algorithm_version],
        "processing_date": run.completed_at,
        "provenance": "DERIVED",
        "confidence": (
            "HIGH"
            if run.quality_scores.get("historical_baseline_completeness", 0) >= 80
            else "MODERATE"
        ),
        "limitations": HISTORICAL_DISCLAIMERS,
        "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
        "demo_disclaimer": "Historical baseline analytical demonstration; no verified AWD or carbon-credit claim.",
    }


@router.get("/plots/{plot_id}/exports/timeline.csv")
def export_timeline_csv(
    plot_id: str, db: Session = Depends(get_db)
) -> StreamingResponse:
    run = _require_historical_run(db, plot_id)
    metadata = _export_metadata(run)
    output = io.StringIO()
    writer = csv.writer(output)
    for key, value in jsonable_encoder(metadata).items():
        writer.writerow([f"# {key}", jsonable_encoder(value)])
    fields = [
        "image_id",
        "date",
        "sensor",
        "status",
        "quality",
        "plot_coverage_percent",
        "vegetation_score",
        "smoothed_vegetation_score",
        "water_candidate_fraction",
        "cultivated_area_estimate_rai",
        "possible_harvested_area_rai",
        "confidence",
        "provenance",
    ]
    writer.writerow(fields)
    for item in timeline_payload(db, plot_id):
        writer.writerow([item.get(field) for field in fields])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{plot_id}-historical-timeline.csv"'},
    )


@router.get("/plots/{plot_id}/exports/historical-baseline.json")
def export_historical_baseline_json(
    plot_id: str, db: Session = Depends(get_db)
) -> JSONResponse:
    run = _require_historical_run(db, plot_id)
    payload = historical_baseline_payload(db, plot_id)
    return JSONResponse(
        jsonable_encoder({"metadata": _export_metadata(run), "historical_baseline": payload})
    )


@router.get("/plots/{plot_id}/exports/recurring-zones.geojson")
def export_recurring_zones_geojson(
    plot_id: str, db: Session = Depends(get_db)
) -> JSONResponse:
    run = _require_historical_run(db, plot_id)
    rows = list(
        db.scalars(
            select(RecurringZone).where(RecurringZone.temporal_analysis_run_id == run.id)
        )
    )
    return JSONResponse(
        jsonable_encoder(
            {
                "type": "FeatureCollection",
                "metadata": _export_metadata(run),
                "features": [
                    {
                        "type": "Feature",
                        "id": row.id,
                        "geometry": row.geometry_json,
                        "properties": {
                            key: value
                            for key, value in _zone_dict(row).items()
                            if key != "geometry"
                        },
                    }
                    for row in rows
                ],
            }
        )
    )


@router.get("/plots/{plot_id}/exports/sensor-proposals.geojson")
def export_sensor_proposals_geojson(
    plot_id: str, db: Session = Depends(get_db)
) -> JSONResponse:
    run = _require_historical_run(db, plot_id)
    rows = list(
        db.scalars(
            select(SensorLocationProposal).where(
                SensorLocationProposal.temporal_analysis_run_id == run.id
            )
        )
    )
    return JSONResponse(
        jsonable_encoder(
            {
                "type": "FeatureCollection",
                "metadata": _export_metadata(run),
                "features": [
                    {
                        "type": "Feature",
                        "id": row.id,
                        "geometry": _proposal_dict(row)["geometry"],
                        "properties": {
                            key: value
                            for key, value in _proposal_dict(row).items()
                            if key != "geometry"
                        },
                    }
                    for row in rows
                ],
            }
        )
    )


@router.get(
    "/plots/{plot_id}/exports/executive-report.html",
    response_class=HTMLResponse,
)
def export_historical_executive_report(
    plot_id: str, db: Session = Depends(get_db)
) -> str:
    run = _require_historical_run(db, plot_id)
    baseline = historical_baseline_payload(db, plot_id) or {}
    metadata = _export_metadata(run)
    year_rows = "".join(
        "<tr>"
        f"<td>{year['year']}</td><td>{year['probable_crop_cycles']}</td>"
        f"<td>{year['cultivated_area_range_rai']}</td>"
        f"<td>{year['harvested_area_range_rai']}</td><td>{year['confidence']}</td>"
        "</tr>"
        for year in baseline.get("years", [])
    )
    limitation_rows = "".join(f"<li>{item}</li>" for item in HISTORICAL_DISCLAIMERS)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <title>Historical Baseline — {plot_id}</title><style>
    body{{font-family:system-ui;max-width:1050px;margin:32px auto;color:#173328;line-height:1.5}}
    h1,h2{{color:#115b3b}}.warning{{background:#fff4d8;border-left:5px solid #d99c22;padding:14px}}
    .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.kpis div{{padding:14px;background:#eef5f1}}
    table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}
    @media print{{button{{display:none}}body{{margin:0}}}}</style></head><body>
    <button onclick="window.print()">Print / Save as PDF</button>
    <h1>Historical Imagery Baseline</h1><p>Plot: {plot_id} · Period: {metadata['analysis_period']}</p>
    <div class="warning"><strong>Analytical demonstration</strong><p>{DEMO_BOUNDARY_WARNING}</p></div>
    <div class="kpis"><div><b>Images</b><br>{run.image_count}</div>
    <div><b>Usable images</b><br>{run.usable_image_count}</div>
    <div><b>Probable cycles</b><br>{baseline.get('probable_crop_cycles', 0)}</div>
    <div><b>Completeness</b><br>{run.quality_scores.get('historical_baseline_completeness')}%</div></div>
    <h2>Three-year comparison</h2><table><thead><tr><th>Year</th><th>Probable cycles</th>
    <th>Cultivated area range (rai)</th><th>Harvest candidate range (rai)</th><th>Confidence</th></tr></thead>
    <tbody>{year_rows}</tbody></table><h2>Required limitations</h2><ul>{limitation_rows}</ul>
    <p>Algorithm: {run.algorithm_version} · Processed: {run.completed_at}</p></body></html>"""
