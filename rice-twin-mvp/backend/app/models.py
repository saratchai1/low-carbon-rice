from datetime import datetime, timezone
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Plot(Base):
    __tablename__ = "plots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    geometry: Mapped[object] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=True), nullable=False
    )
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lon: Mapped[float] = mapped_column(Float, nullable=False)
    area_rai: Mapped[float] = mapped_column(Float, nullable=False)
    boundary_source: Mapped[str] = mapped_column(String(80), default="synthetic_demo")
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    farmer_id: Mapped[str | None] = mapped_column(
        ForeignKey("farmers.id", ondelete="SET NULL"), index=True
    )

    crop_stage: Mapped[str] = mapped_column(String(80), default="แตกกอ")
    water_state: Mapped[str] = mapped_column(String(80), default="ช่วงปล่อยแห้ง")
    water_level_cm: Mapped[float] = mapped_column(Float, default=-8.0)
    awd_cycle: Mapped[int] = mapped_column(Integer, default=2)
    dry_days: Mapped[int] = mapped_column(Integer, default=4)
    recommendation: Mapped[str] = mapped_column(
        Text, default="ชะลอการให้น้ำและตรวจพยากรณ์ฝน"
    )
    yield_risk: Mapped[str] = mapped_column(String(30), default="ต่ำ")
    mrv_confidence: Mapped[str] = mapped_column(String(30), default="สูง")
    data_confidence_score: Mapped[int] = mapped_column(Integer, default=86)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    activities: Mapped[list["Activity"]] = relationship(
        back_populates="plot", cascade="all, delete-orphan"
    )
    crop_seasons: Mapped[list["CropSeason"]] = relationship(
        back_populates="plot", cascade="all, delete-orphan"
    )
    imagery: Mapped[list["Imagery"]] = relationship(
        back_populates="plot", cascade="all, delete-orphan"
    )


class CropSeason(Base):
    __tablename__ = "crop_seasons"
    __table_args__ = (UniqueConstraint("plot_id", "season_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), index=True)
    season_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="active")
    methodology_version: Mapped[str | None] = mapped_column(String(80))
    crop_year: Mapped[int | None] = mapped_column(Integer)
    rice_variety: Mapped[str | None] = mapped_column(String(120))
    planting_method: Mapped[str | None] = mapped_column(String(80))
    planting_date: Mapped[datetime | None] = mapped_column(Date)
    expected_harvest_date: Mapped[datetime | None] = mapped_column(Date)
    actual_harvest_date: Mapped[datetime | None] = mapped_column(Date)
    baseline_scenario: Mapped[str | None] = mapped_column(Text)
    project_scenario: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plot: Mapped[Plot] = relationship(back_populates="crop_seasons")
    activities: Mapped[list["Activity"]] = relationship(back_populates="crop_season")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    plot_id: Mapped[str] = mapped_column(
        ForeignKey("plots.id", ondelete="CASCADE"), index=True
    )
    crop_season_id: Mapped[str | None] = mapped_column(
        ForeignKey("crop_seasons.id", ondelete="RESTRICT"), index=True
    )
    activity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    water_level_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="field_app")
    recorded_by: Mapped[str] = mapped_column(String(120), default="local-demo-user")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plot: Mapped[Plot] = relationship(back_populates="activities")
    crop_season: Mapped[CropSeason | None] = relationship(back_populates="activities")


class Imagery(Base):
    __tablename__ = "imagery"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    plot_id: Mapped[str] = mapped_column(
        ForeignKey("plots.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    preview_path: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    crs: Mapped[str] = mapped_column(String(120), nullable=False)
    bounds_wgs84: Mapped[list] = mapped_column(JSONB, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    band_count: Mapped[int] = mapped_column(Integer, nullable=False)
    render_bands: Mapped[list] = mapped_column(JSONB, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    footprint_intersects_plot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready")
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="user_upload")
    source_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plot: Mapped[Plot] = relationship(back_populates="imagery")


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), index=True)
    crop_season_id: Mapped[str | None] = mapped_column(ForeignKey("crop_seasons.id"))
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_used: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    old_value: Mapped[dict] = mapped_column(JSONB, default=dict)
    new_value: Mapped[dict] = mapped_column(JSONB, default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    source_type: Mapped[str] = mapped_column(String(20), default="REFERENCE")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FarmerGroup(Base):
    __tablename__ = "farmer_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    province: Mapped[str | None] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(20), default="SIMULATED")


class Farmer(Base):
    __tablename__ = "farmers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("farmer_groups.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone_masked: Mapped[str | None] = mapped_column(String(40))
    source_type: Mapped[str] = mapped_column(String(20), default="SIMULATED")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class IoTGateway(Base):
    __tablename__ = "iot_gateways"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    plot_id: Mapped[str | None] = mapped_column(ForeignKey("plots.id"), index=True)
    protocol: Mapped[str] = mapped_column(String(40), default="SIMULATOR")
    status: Mapped[str] = mapped_column(String(30), default="ONLINE")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(80))
    source_type: Mapped[str] = mapped_column(String(20), default="SIMULATED")
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)


class SensorDevice(Base):
    __tablename__ = "sensor_devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_name: Mapped[str] = mapped_column(String(180), nullable=False)
    device_type: Mapped[str] = mapped_column(String(80), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    firmware_version: Mapped[str | None] = mapped_column(String(80))
    plot_id: Mapped[str | None] = mapped_column(ForeignKey("plots.id"), index=True)
    gateway_id: Mapped[str | None] = mapped_column(ForeignKey("iot_gateways.id"), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    installation_date: Mapped[datetime | None] = mapped_column(Date)
    installation_depth_cm: Mapped[float | None] = mapped_column(Float)
    installation_elevation_m: Mapped[float | None] = mapped_column(Float)
    communication_protocol: Mapped[str] = mapped_column(String(40), default="SIMULATOR")
    battery_percent: Mapped[float | None] = mapped_column(Float)
    signal_rssi: Mapped[float | None] = mapped_column(Float)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calibration_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="SIMULATED")
    source_type: Mapped[str] = mapped_column(String(20), default="SIMULATED")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class SensorChannel(Base):
    __tablename__ = "sensor_channels"
    __table_args__ = (UniqueConstraint("device_id", "channel_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("sensor_devices.id"), index=True)
    channel_key: Mapped[str] = mapped_column(String(80), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    minimum_value: Mapped[float | None] = mapped_column(Float)
    maximum_value: Mapped[float | None] = mapped_column(Float)
    depth_cm: Mapped[float | None] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class CalibrationRecord(Base):
    __tablename__ = "calibration_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("sensor_devices.id"), index=True)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calibrated_by: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(40), default="PASS")
    notes: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), default="MANUAL")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("sensor_devices.id"), index=True)
    maintenance_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)


class SensorObservation(Base):
    __tablename__ = "sensor_observations"
    __table_args__ = (
        UniqueConstraint("device_id", "metric", "observed_at", name="uq_observation_identity"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    device_id: Mapped[str] = mapped_column(ForeignKey("sensor_devices.id"), index=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    crop_season_id: Mapped[str | None] = mapped_column(ForeignKey("crop_seasons.id"), index=True)
    metric: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_type: Mapped[str] = mapped_column(String(20), default="SIMULATED")
    source_name: Mapped[str] = mapped_column(String(160), default="Rice Twin Simulator")
    quality_flag: Mapped[str] = mapped_column(String(40), default="valid")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    ingestion_protocol: Mapped[str] = mapped_column(String(40), default="SIMULATOR")
    external_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)


class PublicDataSnapshot(Base):
    __tablename__ = "public_data_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(160), nullable=False)
    station_name: Mapped[str | None] = mapped_column(String(180))
    plot_id: Mapped[str | None] = mapped_column(ForeignKey("plots.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    quality_flag: Mapped[str] = mapped_column(String(40), default="sample")
    licence_status: Mapped[str] = mapped_column(String(80), default="demo_sample")
    source_type: Mapped[str] = mapped_column(String(20), default="PUBLIC")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    limitations: Mapped[str | None] = mapped_column(Text)


class AWDRuleConfiguration(Base):
    __tablename__ = "awd_rule_configurations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    source_type: Mapped[str] = mapped_column(String(20), default="REFERENCE")
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)


class TwinStateSnapshot(Base):
    __tablename__ = "twin_state_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    crop_season_id: Mapped[str | None] = mapped_column(ForeignKey("crop_seasons.id"), index=True)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), default="TWIN-DEMO-1.0")
    source_type: Mapped[str] = mapped_column(String(20), default="DERIVED")
    simulated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    crop_season_id: Mapped[str | None] = mapped_column(ForeignKey("crop_seasons.id"))
    recommendation: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="RECOMMENDATION_CREATED")
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    inputs_used: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DecisionEvent(Base):
    __tablename__ = "decision_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"), index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    plot_id: Mapped[str | None] = mapped_column(ForeignKey("plots.id"), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("sensor_devices.id"), index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), default="DERIVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    crop_season_id: Mapped[str | None] = mapped_column(ForeignKey("crop_seasons.id"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    captured_by: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    review_note: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    scenario_key: Mapped[str] = mapped_column(String(80), index=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="RUNNING")
    speed: Mapped[int] = mapped_column(Integer, default=60)
    seed: Mapped[int] = mapped_column(Integer, default=20260724)
    tick: Mapped[int] = mapped_column(Integer, default=0)
    simulated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    state: Mapped[dict] = mapped_column(JSONB, default=dict)
    outcome: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# Historical imagery entities intentionally use explicit, versioned rows instead
# of extending the legacy ``imagery`` upload table.  This keeps analytical
# outputs append-only and preserves the provenance of every baseline run.
class ImageryAsset(Base):
    __tablename__ = "imagery_assets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="OBSERVED")
    acquisition_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(120), default="image/tiff")
    crs: Mapped[str | None] = mapped_column(String(120))
    resolution_x: Mapped[float | None] = mapped_column(Float)
    resolution_y: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    band_count: Mapped[int | None] = mapped_column(Integer)
    band_names: Mapped[list] = mapped_column(JSONB, default=list)
    cloud_cover_percent: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)
    bounds: Mapped[list] = mapped_column(JSONB, default=list)
    footprint: Mapped[dict] = mapped_column(JSONB, default=dict)
    plot_intersection_percent: Mapped[float] = mapped_column(Float, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    license_status: Mapped[str] = mapped_column(String(80), default="USER_PROVIDED")
    processing_status: Mapped[str] = mapped_column(String(30), default="UPLOADED")
    processing_error: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class ImageryBandMapping(Base):
    __tablename__ = "imagery_band_mappings"
    __table_args__ = (UniqueConstraint("imagery_asset_id", "version"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    imagery_asset_id: Mapped[str] = mapped_column(
        ForeignKey("imagery_assets.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confirmed_by: Mapped[str] = mapped_column(String(120), default="archive_metadata")
    provenance: Mapped[str] = mapped_column(String(30), default="OBSERVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImageryProcessingRun(Base):
    __tablename__ = "imagery_processing_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    imagery_asset_id: Mapped[str] = mapped_column(
        ForeignKey("imagery_assets.id", ondelete="CASCADE"), index=True
    )
    algorithm_name: Mapped[str] = mapped_column(String(120), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    processing_log: Mapped[list] = mapped_column(JSONB, default=list)
    output_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class ImageryQualityResult(Base):
    __tablename__ = "imagery_quality_results"
    __table_args__ = (UniqueConstraint("imagery_asset_id", "algorithm_version"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    imagery_asset_id: Mapped[str] = mapped_column(
        ForeignKey("imagery_assets.id", ondelete="CASCADE"), index=True
    )
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    image_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    spatial_coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    valid_pixel_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    cloud_or_quality_status: Mapped[str] = mapped_column(String(80), nullable=False)
    usable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, default=dict)
    limitations: Mapped[list] = mapped_column(JSONB, default=list)
    provenance: Mapped[str] = mapped_column(String(30), default="DERIVED")
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImageryPlotMetric(Base):
    __tablename__ = "imagery_plot_metrics"
    __table_args__ = (
        UniqueConstraint("imagery_asset_id", "plot_id", "algorithm_version"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    imagery_asset_id: Mapped[str] = mapped_column(
        ForeignKey("imagery_assets.id", ondelete="CASCADE"), index=True
    )
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    acquisition_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    sensor: Mapped[str] = mapped_column(String(40), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    vegetation_score: Mapped[float | None] = mapped_column(Float)
    water_candidate_fraction: Mapped[float | None] = mapped_column(Float)
    wet_soil_fraction: Mapped[float | None] = mapped_column(Float)
    bare_soil_fraction: Mapped[float | None] = mapped_column(Float)
    dense_vegetation_fraction: Mapped[float | None] = mapped_column(Float)
    uncertain_fraction: Mapped[float] = mapped_column(Float, default=0)
    cultivated_area_estimate_rai: Mapped[float | None] = mapped_column(Float)
    possible_harvested_area_rai: Mapped[float | None] = mapped_column(Float)
    uniformity_score: Mapped[float | None] = mapped_column(Float)
    image_quality_score: Mapped[float] = mapped_column(Float)
    usable_plot_coverage: Mapped[float] = mapped_column(Float)
    raw_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    provenance: Mapped[str] = mapped_column(String(30), default="DERIVED")
    confidence: Mapped[str] = mapped_column(String(30), default="MODERATE")
    limitations: Mapped[list] = mapped_column(JSONB, default=list)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HistoricalCropSeason(Base):
    __tablename__ = "historical_crop_seasons"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    probable_start_date: Mapped[datetime | None] = mapped_column(Date)
    probable_planting_window_start: Mapped[datetime | None] = mapped_column(Date)
    probable_planting_window_end: Mapped[datetime | None] = mapped_column(Date)
    probable_peak_date: Mapped[datetime | None] = mapped_column(Date)
    probable_harvest_window_start: Mapped[datetime | None] = mapped_column(Date)
    probable_harvest_window_end: Mapped[datetime | None] = mapped_column(Date)
    estimated_crop_duration_days: Mapped[int | None] = mapped_column(Integer)
    estimated_cultivated_area_rai: Mapped[float | None] = mapped_column(Float)
    estimated_harvested_area_rai: Mapped[float | None] = mapped_column(Float)
    number_of_supporting_images: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(30))
    evidence_image_ids: Mapped[list] = mapped_column(JSONB, default=list)
    limitations: Mapped[list] = mapped_column(JSONB, default=list)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)


class CropStateObservation(Base):
    __tablename__ = "crop_state_observations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    imagery_asset_id: Mapped[str] = mapped_column(ForeignKey("imagery_assets.id"), index=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    observed_on: Mapped[datetime] = mapped_column(Date, index=True)
    state: Mapped[str] = mapped_column(String(60), nullable=False)
    confidence: Mapped[str] = mapped_column(String(30), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), default="ESTIMATED")


class SpatialAnalysisGrid(Base):
    __tablename__ = "spatial_analysis_grids"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    resolution_m: Mapped[float] = mapped_column(Float, nullable=False)
    crs: Mapped[str] = mapped_column(String(120), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)


class RecurringZone(Base):
    __tablename__ = "recurring_zones"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    zone_type: Mapped[str] = mapped_column(String(80), nullable=False)
    geometry_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    number_of_occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    number_of_usable_images: Mapped[int] = mapped_column(Integer, nullable=False)
    years_detected: Mapped[list] = mapped_column(JSONB, default=list)
    season_ids: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[str] = mapped_column(String(30), nullable=False)
    supporting_images: Mapped[list] = mapped_column(JSONB, default=list)
    recommended_field_check: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[list] = mapped_column(JSONB, default=list)


class BaselineEvidenceItem(Base):
    __tablename__ = "baseline_evidence_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    claim_key: Mapped[str] = mapped_column(String(100), nullable=False)
    claim_label: Mapped[str] = mapped_column(String(180), nullable=False)
    support_level: Mapped[str] = mapped_column(String(30), nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_image_ids: Mapped[list] = mapped_column(JSONB, default=list)
    limitations: Mapped[list] = mapped_column(JSONB, default=list)


class SensorLocationProposal(Base):
    __tablename__ = "sensor_location_proposals"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    sensor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PROPOSED")
    field_verification_status: Mapped[str] = mapped_column(
        String(40), default="NOT_FIELD_VERIFIED"
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(30), nullable=False)
    supporting_zone_ids: Mapped[list] = mapped_column(JSONB, default=list)
    assumptions: Mapped[list] = mapped_column(JSONB, default=list)


class TemporalAnalysisRun(Base):
    __tablename__ = "temporal_analysis_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(Date)
    period_end: Mapped[datetime | None] = mapped_column(Date)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    usable_image_count: Mapped[int] = mapped_column(Integer, default=0)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    quality_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AlgorithmVersion(Base):
    __tablename__ = "algorithm_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    algorithm_name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_type: Mapped[str] = mapped_column(String(30), default="REFERENCE")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisAssumption(Base):
    __tablename__ = "analysis_assumptions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    assumption_key: Mapped[str] = mapped_column(String(100), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), default="ASSUMED")


class AnalysisLimitation(Base):
    __tablename__ = "analysis_limitations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    temporal_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("temporal_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    limitation_key: Mapped[str] = mapped_column(String(100), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="MATERIAL")
