from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlotCreate(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
    name: str = Field(min_length=1, max_length=200)
    geometry: dict
    area_rai: float = Field(gt=0)
    boundary_source: str = Field(default="user_supplied", max_length=80)


class PlotUpdate(BaseModel):
    crop_stage: str | None = None
    water_state: str | None = None
    water_level_cm: float | None = Field(default=None, ge=-1000, le=1000)
    awd_cycle: int | None = Field(default=None, ge=0, le=30)
    dry_days: int | None = Field(default=None, ge=0, le=100)
    recommendation: str | None = None
    yield_risk: str | None = None
    mrv_confidence: str | None = None
    data_confidence_score: int | None = Field(default=None, ge=0, le=100)


class ActivityCreate(BaseModel):
    activity_type: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=2000)
    water_level_cm: float | None = Field(default=None, ge=-1000, le=1000)
    source: str = Field(default="field_app", max_length=40)
    crop_season_id: str | None = None
    recorded_by: str = Field(default="local-demo-user", max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    verification_status: str = Field(default="unverified", max_length=30)
    evidence: dict = Field(default_factory=dict)


class ActivityOut(BaseModel):
    id: str
    plot_id: str
    crop_season_id: str | None
    activity_type: str
    occurred_at: datetime
    note: str | None
    water_level_cm: float | None
    source: str
    recorded_by: str
    latitude: float | None
    longitude: float | None
    quantity: float | None
    unit: str | None
    verification_status: str
    evidence: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageryOut(BaseModel):
    id: str
    plot_id: str
    original_filename: str
    captured_at: datetime | None
    crs: str
    bounds_wgs84: list[float]
    width: int
    height: int
    band_count: int
    render_bands: list[int]
    sha256: str
    footprint_intersects_plot: bool
    processing_status: str
    source: str
    source_metadata: dict
    uploaded_at: datetime
    preview_url: str

    model_config = ConfigDict(from_attributes=True)
