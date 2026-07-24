import json
import re
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, get_db, init_database
from .models import Activity, AuditEvent, CropSeason, Imagery, Plot, RuleEvaluation
from .schemas import ActivityCreate, ActivityOut, ImageryOut, PlotCreate, PlotUpdate
from .seed import DEMO_CENTER_LAT, DEMO_CENTER_LON, seed_demo_data
from .services.raster import create_preview
from .services.catalog import bounds_intersect, import_satellite_catalog, sha256_file
from .services.data_quality import evaluate_data_quality
from .services.rules import DEMO_RULE_VERSION, evaluate_awd


STATIC_DIR = Path(__file__).resolve().parent / "static"
ALLOWED_RASTER_EXTENSIONS = {".tif", ".tiff"}
RENDER_MODES = {"auto", "rgb_123", "sentinel2_true_color", "grayscale", "custom"}


def infer_capture_datetime(filename: str) -> datetime | None:
    match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", filename)
    if not match:
        return None
    try:
        return datetime(
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.imagery_dir.mkdir(parents=True, exist_ok=True)
    init_database()
    with SessionLocal() as db:
        seed_demo_data(db)
        plot = db.get(Plot, "DEMO-PLOT-001")
        if plot is not None:
            import_satellite_catalog(db, plot)
    yield


app = FastAPI(
    title="Low-Carbon Rice Digital Twin MVP",
    version="0.1.0",
    description="Operational digital twin prototype for AWD and carbon-MRV workflows.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def plot_properties(plot: Plot) -> dict:
    return {
        "id": plot.id,
        "name": plot.name,
        "center_lat": plot.center_lat,
        "center_lon": plot.center_lon,
        "area_rai": plot.area_rai,
        "boundary_source": plot.boundary_source,
        "crop_stage": plot.crop_stage,
        "water_state": plot.water_state,
        "water_level_cm": plot.water_level_cm,
        "awd_cycle": plot.awd_cycle,
        "dry_days": plot.dry_days,
        "recommendation": plot.recommendation,
        "yield_risk": plot.yield_risk,
        "mrv_confidence": plot.mrv_confidence,
        "data_confidence_score": plot.data_confidence_score,
        "updated_at": plot.updated_at.isoformat(),
    }


def imagery_out(item: Imagery) -> ImageryOut:
    return ImageryOut(
        id=item.id,
        plot_id=item.plot_id,
        original_filename=item.original_filename,
        captured_at=item.captured_at,
        crs=item.crs,
        bounds_wgs84=item.bounds_wgs84,
        width=item.width,
        height=item.height,
        band_count=item.band_count,
        render_bands=item.render_bands,
        sha256=item.sha256,
        footprint_intersects_plot=item.footprint_intersects_plot,
        processing_status=item.processing_status,
        source=item.source,
        source_metadata=item.source_metadata or {},
        uploaded_at=item.uploaded_at,
        preview_url=f"/api/imagery/{item.id}/preview.png",
    )


def add_audit(
    db: Session, *, entity_type: str, entity_id: str, action: str,
    old_value: dict | None = None, new_value: dict | None = None,
    actor: str = "local-demo-user", reason: str | None = None,
) -> None:
    db.add(AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason,
        request_id=str(uuid4()),
    ))


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict:
    return {
        "map_center": [DEMO_CENTER_LON, DEMO_CENTER_LAT],
        "map_zoom": 16,
        "accepted_imagery": ["GeoTIFF", "COG"],
        "max_upload_mb": settings.max_upload_mb,
        "awd_rule_version": DEMO_RULE_VERSION,
        "satellite_catalog_enabled": settings.satellite_output_dir.exists(),
        "boundary_warning": "Demonstration boundary only; not a cadastral, surveyed, or legal parcel boundary.",
    }


@app.get("/api/plots")
def list_plots(db: Session = Depends(get_db)) -> dict:
    statement = select(Plot, func.ST_AsGeoJSON(Plot.geometry)).order_by(Plot.id)
    features = []
    for plot, geometry_json in db.execute(statement).all():
        features.append(
            {
                "type": "Feature",
                "id": plot.id,
                "geometry": json.loads(geometry_json),
                "properties": plot_properties(plot),
            }
        )
    return {"type": "FeatureCollection", "features": features}


@app.post("/api/plots", status_code=status.HTTP_201_CREATED)
def create_plot(payload: PlotCreate, db: Session = Depends(get_db)) -> dict:
    if db.get(Plot, payload.id) is not None:
        raise HTTPException(status_code=409, detail="Plot ID already exists")
    geometry_json = json.dumps(payload.geometry)
    geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_json), 4326)
    valid, geometry_type = db.execute(
        select(func.ST_IsValid(geometry), func.GeometryType(geometry))
    ).one()
    if not valid or geometry_type != "POLYGON":
        raise HTTPException(status_code=400, detail="Geometry must be a valid GeoJSON Polygon")
    center_lon, center_lat = db.execute(
        select(func.ST_X(func.ST_Centroid(geometry)), func.ST_Y(func.ST_Centroid(geometry)))
    ).one()
    plot = Plot(
        id=payload.id,
        name=payload.name,
        geometry=geometry,
        center_lon=center_lon,
        center_lat=center_lat,
        area_rai=payload.area_rai,
        boundary_source=payload.boundary_source,
    )
    db.add(plot)
    add_audit(
        db, entity_type="plot", entity_id=plot.id, action="create",
        new_value={"name": plot.name, "boundary_source": plot.boundary_source},
    )
    db.commit()
    return get_plot(plot.id, db)


@app.get("/api/plots/{plot_id}")
def get_plot(plot_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        select(Plot, func.ST_AsGeoJSON(Plot.geometry)).where(Plot.id == plot_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    plot, geometry_json = row
    return {
        "type": "Feature",
        "id": plot.id,
        "geometry": json.loads(geometry_json),
        "properties": plot_properties(plot),
    }


@app.patch("/api/plots/{plot_id}")
def update_plot(
    plot_id: str, payload: PlotUpdate, db: Session = Depends(get_db)
) -> dict:
    plot = db.get(Plot, plot_id)
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")

    changes = payload.model_dump(exclude_none=True)
    old_value = {field: getattr(plot, field) for field in changes}
    for field, value in changes.items():
        setattr(plot, field, value)
    plot.updated_at = datetime.now(timezone.utc)
    add_audit(
        db, entity_type="plot", entity_id=plot_id, action="update",
        old_value=old_value, new_value=changes,
    )
    db.commit()
    db.refresh(plot)
    return plot_properties(plot)


@app.get("/api/plots/{plot_id}/activities", response_model=list[ActivityOut])
def list_activities(plot_id: str, db: Session = Depends(get_db)) -> list[Activity]:
    if db.get(Plot, plot_id) is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.plot_id == plot_id)
            .order_by(Activity.occurred_at.desc())
        ).all()
    )


@app.post(
    "/api/plots/{plot_id}/activities",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    plot_id: str, payload: ActivityCreate, db: Session = Depends(get_db)
) -> Activity:
    plot = db.get(Plot, plot_id)
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")

    values = payload.model_dump()
    if values["crop_season_id"] is None:
        active_season = db.scalar(
            select(CropSeason).where(
                CropSeason.plot_id == plot_id, CropSeason.status == "active"
            ).order_by(CropSeason.started_at.desc())
        )
        values["crop_season_id"] = active_season.id if active_season else None
    elif db.get(CropSeason, values["crop_season_id"]) is None:
        raise HTTPException(status_code=400, detail="Crop season not found")
    activity = Activity(plot_id=plot_id, **values)
    db.add(activity)
    if payload.water_level_cm is not None:
        plot.water_level_cm = payload.water_level_cm
        plot.updated_at = datetime.now(timezone.utc)
    db.flush()
    add_audit(
        db, entity_type="activity", entity_id=activity.id, action="create",
        new_value={
            "plot_id": plot_id,
            "crop_season_id": activity.crop_season_id,
            "activity_type": activity.activity_type,
            "occurred_at": activity.occurred_at.isoformat(),
            "water_level_cm": activity.water_level_cm,
        },
        actor=activity.recorded_by,
    )
    db.commit()
    db.refresh(activity)
    return activity


@app.get("/api/imagery", response_model=list[ImageryOut])
def list_imagery(
    plot_id: str | None = None, db: Session = Depends(get_db)
) -> list[ImageryOut]:
    statement = select(Imagery).order_by(Imagery.uploaded_at.desc())
    if plot_id:
        statement = statement.where(Imagery.plot_id == plot_id)
    return [imagery_out(item) for item in db.scalars(statement).all()]


@app.post(
    "/api/imagery",
    response_model=ImageryOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_imagery(
    plot_id: str = Form(...),
    captured_at: datetime | None = Form(default=None),
    render_mode: str = Form(default="auto"),
    red_band: int | None = Form(default=None),
    green_band: int | None = Form(default=None),
    blue_band: int | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImageryOut:
    if db.get(Plot, plot_id) is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    if render_mode not in RENDER_MODES:
        raise HTTPException(status_code=400, detail="Unknown render mode")

    original_name = Path(file.filename or "imagery.tif").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_RASTER_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="MVP accepts georeferenced .tif or .tiff files only",
        )

    if render_mode == "rgb_123":
        requested_bands = [1, 2, 3]
    elif render_mode == "sentinel2_true_color":
        requested_bands = [3, 2, 1]
    elif render_mode == "grayscale":
        requested_bands = [1, 1, 1]
    elif render_mode == "custom":
        if None in (red_band, green_band, blue_band):
            raise HTTPException(status_code=400, detail="Custom mode requires all three band numbers")
        requested_bands = [red_band, green_band, blue_band]
    else:
        requested_bands = []

    imagery_id = str(uuid4())
    imagery_folder = settings.imagery_dir / imagery_id
    imagery_folder.mkdir(parents=True, exist_ok=False)
    source_path = imagery_folder / f"source{extension}"
    preview_path = imagery_folder / "preview.png"

    max_bytes = settings.max_upload_mb * 1024 * 1024
    bytes_written = 0
    try:
        with source_path.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.max_upload_mb} MB upload limit",
                    )
                output.write(chunk)

        metadata = create_preview(
            source_path,
            preview_path,
            requested_bands=requested_bands,
        )
        digest = sha256_file(source_path)
    except HTTPException:
        shutil.rmtree(imagery_folder, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(imagery_folder, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Raster processing failed: {exc}") from exc
    finally:
        file.file.close()

    item = Imagery(
        id=imagery_id,
        plot_id=plot_id,
        original_filename=original_name,
        stored_path=str(source_path),
        preview_path=str(preview_path),
        captured_at=captured_at or infer_capture_datetime(original_name),
        crs=metadata.crs,
        bounds_wgs84=metadata.bounds_wgs84,
        width=metadata.width,
        height=metadata.height,
        band_count=metadata.band_count,
        render_bands=metadata.render_bands,
        sha256=digest,
        footprint_intersects_plot=bounds_intersect(metadata.bounds_wgs84, db.get(Plot, plot_id)),
        processing_status="ready",
        source="user_upload",
        source_metadata={
            "render_mode": render_mode,
            "capture_date_source": "user" if captured_at else (
                "filename" if infer_capture_datetime(original_name) else "not_provided"
            ),
            "band_descriptions": metadata.band_descriptions,
        },
    )
    db.add(item)
    db.flush()
    add_audit(
        db, entity_type="imagery", entity_id=item.id, action="create",
        new_value={"plot_id": plot_id, "sha256": digest, "source": "user_upload"},
    )
    db.commit()
    db.refresh(item)
    return imagery_out(item)


def imagery_variant(item: Imagery, render_mode: str) -> tuple[Path, list[int], str | None]:
    source_path = Path(item.stored_path)
    satellite = (item.source_metadata or {}).get("satellite")
    sentinel2_modes = {
        "rice_true_color": ([3, 2, 1], None),
        "rice_false_color": ([4, 3, 2], None),
        "rice_ndvi": ([7, 7, 7], "vegetation"),
        "rice_lswi": ([8, 8, 8], "water"),
        "rice_ndwi": ([9, 9, 9], "water"),
        "rice_evi": ([10, 10, 10], "vegetation"),
    }
    sentinel1_modes = {
        "rice_sar_vv": ("VV_dB.tif", [1, 1, 1]),
        "rice_sar_vh": ("VH_dB.tif", [1, 1, 1]),
        "rice_sar_diff": ("VH_VV_diff_dB.tif", [1, 1, 1]),
    }
    if render_mode in sentinel2_modes and satellite == "Sentinel-2":
        bands, scheme = sentinel2_modes[render_mode]
        return source_path, bands, scheme
    if render_mode in sentinel1_modes and satellite == "Sentinel-1":
        filename, bands = sentinel1_modes[render_mode]
        return source_path.with_name(filename), bands, None
    raise HTTPException(
        status_code=400,
        detail="This rice display mode is not available for the selected imagery",
    )


@app.get("/api/imagery/{imagery_id}/preview.png", include_in_schema=False)
def imagery_preview(
    imagery_id: str,
    render_mode: str = "stored",
    db: Session = Depends(get_db),
) -> FileResponse:
    item = db.get(Imagery, imagery_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Imagery not found")
    if render_mode == "stored":
        preview_path = Path(item.preview_path)
    else:
        source_path, bands, color_scheme = imagery_variant(item, render_mode)
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source band file not found")
        preview_path = settings.imagery_dir / item.id / f"preview-{render_mode}.png"
        if not preview_path.exists():
            try:
                create_preview(
                    source_path,
                    preview_path,
                    requested_bands=bands,
                    color_scheme=color_scheme,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot render this rice display mode: {exc}",
                ) from exc
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview file not found")
    return FileResponse(preview_path, media_type="image/png")


@app.get("/api/imagery/{imagery_id}", response_model=ImageryOut)
def get_imagery(imagery_id: str, db: Session = Depends(get_db)) -> ImageryOut:
    item = db.get(Imagery, imagery_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Imagery not found")
    return imagery_out(item)


@app.get("/api/plots/{plot_id}/crop-seasons")
def list_crop_seasons(plot_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(Plot, plot_id) is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    return [{
        "id": item.id,
        "plot_id": item.plot_id,
        "season_code": item.season_code,
        "name": item.name,
        "started_at": item.started_at,
        "ended_at": item.ended_at,
        "status": item.status,
        "methodology_version": item.methodology_version,
    } for item in db.scalars(
        select(CropSeason).where(CropSeason.plot_id == plot_id).order_by(CropSeason.started_at.desc())
    )]


@app.post("/api/plots/{plot_id}/evaluate")
def evaluate_plot(plot_id: str, db: Session = Depends(get_db)) -> dict:
    plot = db.get(Plot, plot_id)
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    season = db.scalar(select(CropSeason).where(
        CropSeason.plot_id == plot_id, CropSeason.status == "active"
    ).order_by(CropSeason.started_at.desc()))
    results = evaluate_awd(
        water_level_cm=plot.water_level_cm,
        crop_stage=plot.crop_stage,
        dry_days=plot.dry_days,
    )
    for result in results:
        db.add(RuleEvaluation(
            plot_id=plot_id,
            crop_season_id=season.id if season else None,
            rule_id=result["rule_id"],
            rule_version=result["rule_version"],
            severity=result["severity"],
            explanation=result["explanation"],
            inputs_used=result["inputs_used"],
            recommended_action=result["recommended_action"],
        ))
    plot.recommendation = results[0]["recommended_action"]
    add_audit(
        db, entity_type="rule_evaluation", entity_id=plot_id, action="evaluate",
        new_value={"rule_version": DEMO_RULE_VERSION, "result_count": len(results)},
        actor="system",
    )
    db.commit()
    return {
        "plot_id": plot_id,
        "rules_are_demonstrative": True,
        "agronomist_approval": "not_configured",
        "evaluations": results,
    }


@app.get("/api/plots/{plot_id}/alerts")
def list_alerts(plot_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(Plot, plot_id) is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    rows = db.scalars(
        select(RuleEvaluation).where(
            RuleEvaluation.plot_id == plot_id,
            RuleEvaluation.severity.in_(["warning", "high"]),
        ).order_by(RuleEvaluation.evaluated_at.desc()).limit(50)
    )
    return [{
        "id": row.id, "rule_id": row.rule_id, "rule_version": row.rule_version,
        "severity": row.severity, "explanation": row.explanation,
        "recommended_action": row.recommended_action, "evaluated_at": row.evaluated_at,
    } for row in rows]


@app.get("/api/plots/{plot_id}/data-quality")
def data_quality(plot_id: str, db: Session = Depends(get_db)) -> dict:
    plot = db.get(Plot, plot_id)
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    result = evaluate_data_quality(db, plot)
    plot.data_confidence_score = result["score"]
    db.commit()
    return result


@app.get("/api/plots/{plot_id}/carbon")
def carbon_status(plot_id: str, db: Session = Depends(get_db)) -> dict:
    if db.get(Plot, plot_id) is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    return {
        "plot_id": plot_id,
        "status": "not_configured",
        "message": "GHG calculation not configured — no carbon-credit claim can be made.",
        "methodology_version": None,
        "baseline_scenario": None,
        "project_activity": None,
        "emission_sources": [],
        "activity_data": [],
        "emission_factors": [],
        "calculation_version": None,
        "uncertainty": None,
        "exclusions": [],
        "verification_status": "not_started",
        "creditable_amount": None,
        "issued_amount": None,
        "retired_amount": None,
    }


@app.get("/api/audit-events")
def audit_events(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    limit = min(max(limit, 1), 500)
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit))
    return [{
        "id": row.id, "entity_type": row.entity_type, "entity_id": row.entity_id,
        "action": row.action, "actor": row.actor, "old_value": row.old_value,
        "new_value": row.new_value, "reason": row.reason,
        "request_id": row.request_id, "created_at": row.created_at,
    } for row in rows]
