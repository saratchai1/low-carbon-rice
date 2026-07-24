import hashlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Imagery, Plot
from .raster import create_preview


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounds_intersect(bounds: list[float], plot: Plot) -> bool:
    west, south, east, north = bounds
    return not (
        east < plot.center_lon - 0.02 or west > plot.center_lon + 0.02
        or north < plot.center_lat - 0.02 or south > plot.center_lat + 0.02
    )


def import_satellite_catalog(db: Session, plot: Plot) -> int:
    inventory_path = settings.satellite_output_dir / "summary_inventory.json"
    if not inventory_path.exists():
        return 0
    imported = 0
    for record in json.loads(inventory_path.read_text()):
        source_dir = settings.satellite_output_dir / Path(record["output_dir"]).relative_to(
            "/Users/kong/low-carbon-rice/output"
        )
        if record["satellite"] == "Sentinel-2":
            source_path = source_dir / "sentinel2_rice_bands.tif"
            bands = [3, 2, 1]
        else:
            source_path = source_dir / "VV_dB.tif"
            bands = [1, 1, 1]
        if not source_path.exists():
            continue
        digest = sha256_file(source_path)
        if db.scalar(select(Imagery.id).where(Imagery.sha256 == digest)):
            continue
        imagery_id = f"catalog-{digest[:24]}"
        folder = settings.imagery_dir / imagery_id
        preview_path = folder / "preview.png"
        folder.mkdir(parents=True, exist_ok=True)
        metadata = create_preview(source_path, preview_path, bands)
        db.add(Imagery(
            id=imagery_id,
            plot_id=plot.id,
            original_filename=source_path.name,
            stored_path=str(source_path),
            preview_path=str(preview_path),
            captured_at=datetime.fromisoformat(record["datetime"].replace("Z", "+00:00")),
            crs=metadata.crs,
            bounds_wgs84=metadata.bounds_wgs84,
            width=metadata.width,
            height=metadata.height,
            band_count=metadata.band_count,
            render_bands=metadata.render_bands,
            sha256=digest,
            footprint_intersects_plot=bounds_intersect(metadata.bounds_wgs84, plot),
            processing_status="ready",
            source="downloaded_catalog",
            source_metadata={
                "satellite": record["satellite"],
                "scene_id": record["scene_id"],
                "scene_ids": record.get("scene_ids", [record["scene_id"]]),
                "mgrs_tiles": record.get("mgrs_tiles", []),
                "cloud_cover_percent": record["cloud_cover_%"],
                "metrics": {
                    key: record.get(key) for key in
                    ("mean_ndvi", "mean_lswi", "mean_ndwi", "mean_evi", "mean_vv_dB", "mean_vh_dB")
                },
            },
        ))
        imported += 1
    db.commit()
    return imported
