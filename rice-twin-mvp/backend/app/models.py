from datetime import datetime, timezone
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
