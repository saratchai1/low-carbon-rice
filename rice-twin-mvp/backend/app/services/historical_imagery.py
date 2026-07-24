"""Versioned historical-imagery ingestion and baseline analysis.

The module is deliberately deterministic and local-only.  Source GeoTIFFs are
opened read-only, plot metrics are calculated from pixels inside the synthetic
demonstration boundary, and every analytical result carries provenance,
algorithm version, confidence, and limitations.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform, transform_bounds, transform_geom
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import (
    AlgorithmVersion,
    AnalysisAssumption,
    AnalysisLimitation,
    BaselineEvidenceItem,
    CropStateObservation,
    HistoricalCropSeason,
    ImageryAsset,
    ImageryBandMapping,
    ImageryPlotMetric,
    ImageryProcessingRun,
    ImageryQualityResult,
    Plot,
    RecurringZone,
    SensorLocationProposal,
    SpatialAnalysisGrid,
    TemporalAnalysisRun,
)
from ..seed import DEMO_BOUNDARY_WARNING, DEMO_RING


ALGORITHM_VERSION = "HIST-RICE-1.0.0"
BAND_MAPPING_VERSION = "BAND-MAP-1.0.0"
DEFAULT_PLOT_ID = "DEMO-PLOT-001"
SUPPORTED_STATUS = {
    "UPLOADED",
    "VALIDATING",
    "VALID",
    "PROCESSING",
    "READY",
    "WARNING",
    "FAILED",
    "ARCHIVED",
}
HISTORICAL_DISCLAIMERS = [
    "Historical imagery analysis is an analytical demonstration. It does not independently verify AWD compliance.",
    "Overhead imagery cannot directly measure water depth below the soil surface.",
    "Crop-stage, planting-window, and harvest-window results are estimates unless confirmed by field records.",
    "Fertilizer application, straw management, yield, and greenhouse-gas emissions cannot be determined reliably from imagery alone.",
    "Carbon results shown in the demonstration are not verified carbon credits.",
    "No actual cultivation or field IoT installation has been completed for the demonstration plot.",
]

PLOT_GEOJSON = {"type": "Polygon", "coordinates": [DEMO_RING]}
PLOT_WEST = min(point[0] for point in DEMO_RING)
PLOT_EAST = max(point[0] for point in DEMO_RING)
PLOT_SOUTH = min(point[1] for point in DEMO_RING)
PLOT_NORTH = max(point[1] for point in DEMO_RING)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raster_spatial_metadata(dataset: rasterio.io.DatasetReader) -> dict[str, Any]:
    """Return an envelope for analysis and the four real raster corners for display."""
    bounds_wgs84 = transform_bounds(
        dataset.crs, "EPSG:4326", *dataset.bounds, densify_pts=21
    )
    source_corners = [
        dataset.transform * (0, 0),
        dataset.transform * (dataset.width, 0),
        dataset.transform * (dataset.width, dataset.height),
        dataset.transform * (0, dataset.height),
    ]
    source_x, source_y = zip(*source_corners)
    longitude, latitude = transform(
        dataset.crs, "EPSG:4326", source_x, source_y
    )
    display_coordinates = [
        [float(lon), float(lat)] for lon, lat in zip(longitude, latitude)
    ]
    return {
        "bounds_wgs84": [float(value) for value in bounds_wgs84],
        "display_coordinates_wgs84": display_coordinates,
        "footprint_wgs84": {
            "type": "Polygon",
            "coordinates": [[*display_coordinates, display_coordinates[0]]],
        },
    }


def parse_scene_date(name: str) -> datetime | None:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", name)
    if not match:
        return None
    try:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def validate_band_mapping(sensor: str, mapping: dict[str, Any]) -> None:
    required = {"Sentinel-2": {"BLUE", "GREEN", "RED", "NIR"}, "Sentinel-1": {"VV", "VH"}}
    if sensor not in required:
        raise ValueError(f"Unsupported sensor: {sensor}")
    missing = required[sensor] - set(mapping)
    if missing:
        raise ValueError(f"Missing required band mapping: {', '.join(sorted(missing))}")
    indexes = [value for value in mapping.values() if isinstance(value, int)]
    if any(index < 1 for index in indexes) or len(indexes) != len(set(indexes)):
        raise ValueError("Band indexes must be unique positive integers")


def calculate_multispectral_indices(
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    nir: np.ndarray,
    swir1: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Calculate explicit indices without assuming input band order."""

    def ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
        result = np.full(numerator.shape, np.nan, dtype=np.float32)
        np.divide(
            numerator,
            denominator,
            out=result,
            where=np.isfinite(denominator) & (np.abs(denominator) > 1e-6),
        )
        return result

    red = red.astype(np.float32)
    green = green.astype(np.float32)
    blue = blue.astype(np.float32)
    nir = nir.astype(np.float32)
    indices = {
        "NDVI": ratio(nir - red, nir + red),
        "GNDVI": ratio(nir - green, nir + green),
        "NDWI": ratio(green - nir, green + nir),
        "SAVI": 1.5 * ratio(nir - red, nir + red + 0.5),
        "EVI": 2.5 * ratio(nir - red, nir + 6 * red - 7.5 * blue + 1),
    }
    if swir1 is not None:
        swir1 = swir1.astype(np.float32)
        indices["MNDWI"] = ratio(green - swir1, green + swir1)
        indices["NDMI"] = ratio(nir - swir1, nir + swir1)
    return indices


def calculate_rgb_indices(
    red: np.ndarray, green: np.ndarray, blue: np.ndarray
) -> dict[str, np.ndarray]:
    """Visible-spectrum products; none of these are labelled NDVI."""

    red = red.astype(np.float32)
    green = green.astype(np.float32)
    blue = blue.astype(np.float32)
    total = red + green + blue
    safe_total = np.where(np.abs(total) > 1e-6, total, np.nan)
    safe_vari = np.where(np.abs(green + red - blue) > 1e-6, green + red - blue, np.nan)
    return {
        "EXCESS_GREEN": 2 * green - red - blue,
        "VARI": (green - red) / safe_vari,
        "GLI": (2 * green - red - blue) / safe_total,
        "NORMALIZED_GREEN": green / safe_total,
        "BRIGHTNESS": total / 3,
    }


def rolling_median(values: list[float | None], window: int = 3) -> list[float | None]:
    if window < 1 or window % 2 == 0:
        raise ValueError("window must be a positive odd integer")
    radius = window // 2
    result: list[float | None] = []
    for index in range(len(values)):
        candidates = [
            value
            for value in values[max(0, index - radius) : index + radius + 1]
            if value is not None and math.isfinite(value)
        ]
        result.append(float(median(candidates)) if candidates else None)
    return result


def detect_temporal_gaps(
    dates: Iterable[date | datetime], expected_days: int = 8, multiplier: float = 2.5
) -> list[dict[str, Any]]:
    ordered = sorted(item.date() if isinstance(item, datetime) else item for item in dates)
    gaps = []
    for previous, current in zip(ordered, ordered[1:]):
        days = (current - previous).days
        if days > expected_days * multiplier:
            gaps.append(
                {
                    "start": previous.isoformat(),
                    "end": current.isoformat(),
                    "days": days,
                    "expected_days": expected_days,
                }
            )
    return gaps


def _intersection_percent(bounds_wgs84: tuple[float, float, float, float]) -> float:
    west, south, east, north = bounds_wgs84
    intersection_width = max(0.0, min(east, PLOT_EAST) - max(west, PLOT_WEST))
    intersection_height = max(0.0, min(north, PLOT_NORTH) - max(south, PLOT_SOUTH))
    plot_area = (PLOT_EAST - PLOT_WEST) * (PLOT_NORTH - PLOT_SOUTH)
    return round(100 * intersection_width * intersection_height / plot_area, 3) if plot_area else 0


def _masked_values(dataset: rasterio.io.DatasetReader, indexes: list[int]) -> tuple[np.ndarray, np.ndarray]:
    projected_plot = transform_geom("EPSG:4326", dataset.crs, PLOT_GEOJSON)
    inside = geometry_mask(
        [projected_plot],
        out_shape=(dataset.height, dataset.width),
        transform=dataset.transform,
        invert=True,
    )
    arrays = dataset.read(indexes).astype(np.float32)
    valid = inside.copy()
    for array in arrays:
        valid &= np.isfinite(array)
        if dataset.nodata is not None and math.isfinite(dataset.nodata):
            valid &= array != dataset.nodata
    return arrays, valid


def _safe_fraction(condition: np.ndarray, valid: np.ndarray) -> float:
    denominator = int(valid.sum())
    if denominator == 0:
        return 0.0
    return round(float((condition & valid).sum()) / denominator, 6)


def _safe_mean(values: np.ndarray, valid: np.ndarray) -> float | None:
    selected = values[valid]
    return round(float(np.mean(selected)), 6) if selected.size else None


def _safe_std(values: np.ndarray, valid: np.ndarray) -> float | None:
    selected = values[valid]
    return round(float(np.std(selected)), 6) if selected.size else None


def _s2_metrics(path: Path, plot_area_rai: float) -> dict[str, Any]:
    with rasterio.open(path) as dataset:
        if dataset.crs is None:
            raise ValueError("GeoTIFF has no CRS")
        if dataset.transform.is_identity:
            raise ValueError("GeoTIFF has an invalid identity geotransform")
        if dataset.count < 10:
            raise ValueError("Sentinel-2 rice stack requires 10 explicit bands")
        arrays, valid = _masked_values(dataset, [7, 8, 9, 10])
        ndvi, lswi, ndwi, evi = arrays
        spatial = raster_spatial_metadata(dataset)
        bounds_wgs84 = spatial["bounds_wgs84"]
        coverage = _intersection_percent(bounds_wgs84)
        inside_count = max(
            1,
            int(
                geometry_mask(
                    [transform_geom("EPSG:4326", dataset.crs, PLOT_GEOJSON)],
                    out_shape=(dataset.height, dataset.width),
                    transform=dataset.transform,
                    invert=True,
                ).sum()
            ),
        )
        valid_fraction = min(1.0, float(valid.sum()) / inside_count)
        vegetation = _safe_mean(ndvi, valid)
        dense_fraction = _safe_fraction(ndvi >= 0.5, valid)
        water_fraction = _safe_fraction(ndwi >= 0.1, valid)
        wet_soil_fraction = _safe_fraction((lswi >= 0) & (ndvi < 0.45), valid)
        bare_fraction = _safe_fraction((ndvi < 0.2) & (ndwi < 0.1), valid)
        uncertain_fraction = round(max(0.0, 1 - valid_fraction), 6)
        cultivated_fraction = _safe_fraction(ndvi >= 0.22, valid)
        uniformity = _safe_std(ndvi, valid)
        uniformity_score = (
            round(max(0.0, 100 * (1 - min(1.0, uniformity / 0.35))), 2)
            if uniformity is not None
            else None
        )
        quality = round(min(85.0, 55 * valid_fraction + 30 * coverage / 100), 2)
        return {
            "metadata": {
                "crs": str(dataset.crs),
                "resolution": [abs(dataset.res[0]), abs(dataset.res[1])],
                "width": dataset.width,
                "height": dataset.height,
                "band_count": dataset.count,
                "band_names": list(dataset.descriptions),
                **spatial,
                "bounds_source_crs": list(dataset.bounds),
                "dtype": dataset.dtypes[0],
            },
            "quality": {
                "image_quality_score": quality,
                "spatial_coverage_score": coverage,
                "valid_pixel_fraction": round(valid_fraction, 6),
                "cloud_or_quality_status": "NO_CLOUD_MASK_METADATA",
                "usable": coverage >= 80 and valid_fraction >= 0.8,
                "components": {
                    "valid_pixels": round(valid_fraction * 100, 2),
                    "plot_coverage": coverage,
                    "cloud_mask": None,
                    "optical_quality_cap": 85,
                },
                "limitations": [
                    "No cloud probability or scene-classification layer was supplied.",
                    *(
                        ["Source raster covers less than 80% of the synthetic plot."]
                        if coverage < 80
                        else []
                    ),
                ],
            },
            "metric": {
                "vegetation_score": vegetation,
                "water_candidate_fraction": water_fraction,
                "wet_soil_fraction": wet_soil_fraction,
                "bare_soil_fraction": bare_fraction,
                "dense_vegetation_fraction": dense_fraction,
                "uncertain_fraction": uncertain_fraction,
                "cultivated_area_estimate_rai": round(plot_area_rai * cultivated_fraction, 3),
                "possible_harvested_area_rai": round(plot_area_rai * bare_fraction, 3),
                "uniformity_score": uniformity_score,
                "raw_metrics": {
                    "mean_ndvi": vegetation,
                    "mean_lswi": _safe_mean(lswi, valid),
                    "mean_ndwi": _safe_mean(ndwi, valid),
                    "mean_evi": _safe_mean(evi, valid),
                    "ndvi_std": uniformity,
                    "cultivated_fraction": cultivated_fraction,
                    "classification": "MULTISPECTRAL_CANDIDATE_CLASSES",
                },
            },
        }


def _s1_metrics(scene_dir: Path, plot_area_rai: float) -> dict[str, Any]:
    paths = {
        "VV": scene_dir / "VV_dB.tif",
        "VH": scene_dir / "VH_dB.tif",
        "VH_MINUS_VV": scene_dir / "VH_VV_diff_dB.tif",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise ValueError(f"Missing Sentinel-1 files: {', '.join(missing)}")
    with rasterio.open(paths["VV"]) as vv_source, rasterio.open(paths["VH"]) as vh_source, rasterio.open(
        paths["VH_MINUS_VV"]
    ) as diff_source:
        if vv_source.crs is None:
            raise ValueError("GeoTIFF has no CRS")
        if vv_source.transform.is_identity:
            raise ValueError("GeoTIFF has an invalid identity geotransform")
        vv_arrays, vv_valid = _masked_values(vv_source, [1])
        vh_arrays, vh_valid = _masked_values(vh_source, [1])
        diff_arrays, diff_valid = _masked_values(diff_source, [1])
        vv = vv_arrays[0]
        vh = vh_arrays[0]
        difference = diff_arrays[0]
        valid = vv_valid & vh_valid & diff_valid
        spatial = raster_spatial_metadata(vv_source)
        bounds_wgs84 = spatial["bounds_wgs84"]
        coverage = _intersection_percent(bounds_wgs84)
        inside = geometry_mask(
            [transform_geom("EPSG:4326", vv_source.crs, PLOT_GEOJSON)],
            out_shape=(vv_source.height, vv_source.width),
            transform=vv_source.transform,
            invert=True,
        )
        valid_fraction = min(1.0, float(valid.sum()) / max(1, int(inside.sum())))
        # These are candidates, not field-observed inundation.  Lower VV and a
        # strongly negative VH−VV difference are treated as smoother/wetter.
        water_fraction = _safe_fraction((vv < -13.0) & (difference < -5.0), valid)
        structure_fraction = _safe_fraction(vh > -20.0, valid)
        bare_fraction = _safe_fraction((vv > -10.5) & (vh < -18.0), valid)
        quality = round(min(95.0, 65 * valid_fraction + 30 * coverage / 100), 2)
        return {
            "metadata": {
                "crs": str(vv_source.crs),
                "resolution": [abs(vv_source.res[0]), abs(vv_source.res[1])],
                "width": vv_source.width,
                "height": vv_source.height,
                "band_count": 3,
                "band_names": ["VV_dB", "VH_dB", "VH_minus_VV_dB"],
                **spatial,
                "bounds_source_crs": list(vv_source.bounds),
                "dtype": vv_source.dtypes[0],
            },
            "quality": {
                "image_quality_score": quality,
                "spatial_coverage_score": coverage,
                "valid_pixel_fraction": round(valid_fraction, 6),
                "cloud_or_quality_status": "RADAR_CLOUD_INDEPENDENT",
                "usable": coverage >= 80 and valid_fraction >= 0.8,
                "components": {
                    "valid_pixels": round(valid_fraction * 100, 2),
                    "plot_coverage": coverage,
                    "radiometric_products_present": 100,
                },
                "limitations": [
                    "Radar thresholds identify surface-condition candidates, not measured water depth.",
                    "No orbit-normalization or field calibration record was supplied.",
                ],
            },
            "metric": {
                "vegetation_score": structure_fraction,
                "water_candidate_fraction": water_fraction,
                "wet_soil_fraction": water_fraction,
                "bare_soil_fraction": bare_fraction,
                "dense_vegetation_fraction": structure_fraction,
                "uncertain_fraction": round(max(0.0, 1 - valid_fraction), 6),
                "cultivated_area_estimate_rai": round(plot_area_rai * structure_fraction, 3),
                "possible_harvested_area_rai": None,
                "uniformity_score": (
                    round(max(0.0, 100 * (1 - min(1.0, float(np.std(vh[valid])) / 8))), 2)
                    if valid.any()
                    else None
                ),
                "raw_metrics": {
                    "mean_vv_db": _safe_mean(vv, valid),
                    "mean_vh_db": _safe_mean(vh, valid),
                    "mean_vh_minus_vv_db": _safe_mean(difference, valid),
                    "radar_structure_candidate_fraction": structure_fraction,
                    "classification": "SAR_SURFACE_CONDITION_CANDIDATES",
                },
            },
        }


def _asset_id(sensor: str, captured_at: datetime, suffix: str = "") -> str:
    sensor_key = "s2" if sensor == "Sentinel-2" else "s1"
    return f"hist-{sensor_key}-{captured_at.date().isoformat()}{suffix}"


def _band_mapping(sensor: str) -> dict[str, Any]:
    if sensor == "Sentinel-2":
        return {
            "BLUE": 1,
            "GREEN": 2,
            "RED": 3,
            "NIR": 4,
            "SWIR1": 5,
            "SWIR2": 6,
            "NDVI": 7,
            "LSWI": 8,
            "NDWI": 9,
            "EVI": 10,
        }
    return {"VV": "VV_dB.tif", "VH": "VH_dB.tif", "VH_MINUS_VV": "VH_VV_diff_dB.tif"}


def _process_scene(
    db: Session,
    plot: Plot,
    sensor: str,
    scene_dir: Path,
    main_path: Path,
    captured_at: datetime,
) -> ImageryAsset:
    asset_id = _asset_id(sensor, captured_at)
    existing = db.get(ImageryAsset, asset_id)
    if existing is not None:
        digest = sha256_file(main_path)
        if (
            existing.sha256 == digest
            and (existing.metadata_json or {}).get("display_coordinates_wgs84")
        ):
            return existing
        result = (
            _s2_metrics(main_path, plot.area_rai)
            if sensor == "Sentinel-2"
            else _s1_metrics(scene_dir, plot.area_rai)
        )
        metadata = result["metadata"]
        quality = result["quality"]
        metric = result["metric"]
        status = "READY" if quality["usable"] else "WARNING"
        existing.crs = metadata["crs"]
        existing.resolution_x = metadata["resolution"][0]
        existing.resolution_y = metadata["resolution"][1]
        existing.width = metadata["width"]
        existing.height = metadata["height"]
        existing.band_count = metadata["band_count"]
        existing.band_names = metadata["band_names"]
        existing.quality_score = quality["image_quality_score"]
        existing.bounds = metadata["bounds_wgs84"]
        existing.footprint = metadata["footprint_wgs84"]
        existing.plot_intersection_percent = quality["spatial_coverage_score"]
        existing.sha256 = digest
        existing.processing_status = status
        existing.processing_error = None
        existing.metadata_json = {
            **(existing.metadata_json or {}),
            **metadata,
            "scene_directory": str(scene_dir),
            "companion_files": sorted(path.name for path in scene_dir.glob("*") if path.is_file()),
            "original_preserved": True,
            "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
        }

        quality_row = db.get(ImageryQualityResult, f"quality-{asset_id}")
        if quality_row is not None:
            for key, value in quality.items():
                setattr(quality_row, key, value)
            quality_row.processed_at = utcnow()

        metric_row = db.get(ImageryPlotMetric, f"metric-{asset_id}")
        if metric_row is not None:
            confidence = (
                "HIGH"
                if quality["image_quality_score"] >= 85 and quality["usable"]
                else "MODERATE"
                if quality["usable"]
                else "LOW"
            )
            for key, value in metric.items():
                setattr(metric_row, key, value)
            metric_row.image_quality_score = quality["image_quality_score"]
            metric_row.usable_plot_coverage = quality["spatial_coverage_score"]
            metric_row.confidence = confidence
            metric_row.limitations = quality["limitations"]
            metric_row.processed_at = utcnow()

        processing_row = db.get(ImageryProcessingRun, f"process-{asset_id}")
        if processing_row is not None:
            processing_row.status = status
            processing_row.completed_at = utcnow()
            processing_row.processing_log = [
                *(processing_row.processing_log or []),
                "Refreshed metrics and real WGS84 corner coordinates from current source raster",
            ]
        db.flush()
        return existing

    started_at = utcnow()
    try:
        digest = sha256_file(main_path)
        duplicate = db.scalar(
            select(ImageryAsset)
            .where(ImageryAsset.sha256 == digest)
            .order_by(ImageryAsset.uploaded_at)
            .limit(1)
        )
        if duplicate is not None:
            asset = ImageryAsset(
                id=asset_id,
                plot_id=plot.id,
                source_name=sensor,
                source_type="OBSERVED",
                acquisition_datetime=captured_at,
                original_filename=main_path.name,
                source_path=str(main_path),
                sha256=digest,
                processing_status="WARNING",
                processing_error=f"Duplicate SHA-256 of {duplicate.id}; scene excluded from analysis",
                metadata_json={
                    "duplicate_of": duplicate.id,
                    "scene_directory": str(scene_dir),
                    "original_preserved": True,
                    "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
                },
            )
            db.add(asset)
            db.flush()
            return asset
        result = (
            _s2_metrics(main_path, plot.area_rai)
            if sensor == "Sentinel-2"
            else _s1_metrics(scene_dir, plot.area_rai)
        )
        metadata = result["metadata"]
        quality = result["quality"]
        metric = result["metric"]
        status = "READY" if quality["usable"] else "WARNING"
        asset = ImageryAsset(
            id=asset_id,
            plot_id=plot.id,
            source_name=sensor,
            source_type="OBSERVED",
            acquisition_datetime=captured_at,
            original_filename=main_path.name,
            source_path=str(main_path),
            crs=metadata["crs"],
            resolution_x=metadata["resolution"][0],
            resolution_y=metadata["resolution"][1],
            width=metadata["width"],
            height=metadata["height"],
            band_count=metadata["band_count"],
            band_names=metadata["band_names"],
            quality_score=quality["image_quality_score"],
            bounds=metadata["bounds_wgs84"],
            footprint=metadata["footprint_wgs84"],
            plot_intersection_percent=quality["spatial_coverage_score"],
            sha256=digest,
            processing_status=status,
            metadata_json={
                **metadata,
                "scene_directory": str(scene_dir),
                "companion_files": sorted(path.name for path in scene_dir.glob("*") if path.is_file()),
                "original_preserved": True,
                "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
            },
        )
        db.add(asset)
        db.add(
            ImageryBandMapping(
                id=f"map-{asset_id}",
                imagery_asset_id=asset_id,
                version=BAND_MAPPING_VERSION,
                mapping=_band_mapping(sensor),
            )
        )
        db.add(
            ImageryQualityResult(
                id=f"quality-{asset_id}",
                imagery_asset_id=asset_id,
                algorithm_version=ALGORITHM_VERSION,
                **quality,
            )
        )
        confidence = (
            "HIGH"
            if quality["image_quality_score"] >= 85 and quality["usable"]
            else "MODERATE"
            if quality["usable"]
            else "LOW"
        )
        db.add(
            ImageryPlotMetric(
                id=f"metric-{asset_id}",
                imagery_asset_id=asset_id,
                plot_id=plot.id,
                acquisition_datetime=captured_at,
                sensor=sensor,
                algorithm_version=ALGORITHM_VERSION,
                image_quality_score=quality["image_quality_score"],
                usable_plot_coverage=quality["spatial_coverage_score"],
                confidence=confidence,
                limitations=quality["limitations"],
                **metric,
            )
        )
        db.add(
            ImageryProcessingRun(
                id=f"process-{asset_id}",
                imagery_asset_id=asset_id,
                algorithm_name="historical_scene_preprocessing",
                algorithm_version=ALGORITHM_VERSION,
                status=status,
                started_at=started_at,
                completed_at=utcnow(),
                parameters={
                    "analysis_grid": "native_10m",
                    "plot_clip": True,
                    "percentile_stretch": "display_only_2_98",
                },
                processing_log=[
                    "Validated CRS and affine transform",
                    "Calculated SHA-256 without modifying source",
                    "Transformed plot boundary to source CRS",
                    "Calculated plot-mask metrics on native grid",
                    "Stored quality components and limitations",
                ],
                output_metadata={"metric_id": f"metric-{asset_id}", "quality_id": f"quality-{asset_id}"},
            )
        )
        db.flush()
        return asset
    except Exception as exc:
        asset = ImageryAsset(
            id=asset_id,
            plot_id=plot.id,
            source_name=sensor,
            source_type="OBSERVED",
            acquisition_datetime=captured_at,
            original_filename=main_path.name,
            source_path=str(main_path),
            processing_status="FAILED",
            processing_error=str(exc),
            metadata_json={
                "scene_directory": str(scene_dir),
                "original_preserved": True,
                "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
            },
        )
        db.add(asset)
        db.flush()
        return asset


def _record_incomplete_scene(
    db: Session, plot: Plot, scene_dir: Path, sensor: str, captured_at: datetime
) -> ImageryAsset:
    asset_id = _asset_id(sensor, captured_at)
    existing = db.get(ImageryAsset, asset_id)
    if existing is not None:
        return existing
    expected = (
        ["sentinel2_rice_bands.tif", "NDVI.tif", "LSWI.tif", "NDWI.tif", "preview_summary.png"]
        if sensor == "Sentinel-2"
        else ["VV_dB.tif", "VH_dB.tif", "VH_VV_diff_dB.tif", "preview_sar_summary.png"]
    )
    present = {path.name for path in scene_dir.glob("*") if path.is_file()}
    missing = [name for name in expected if name not in present]
    asset = ImageryAsset(
        id=asset_id,
        plot_id=plot.id,
        source_name=sensor,
        source_type="OBSERVED",
        acquisition_datetime=captured_at,
        original_filename=scene_dir.name,
        source_path=str(scene_dir),
        processing_status="FAILED",
        processing_error=f"Incomplete scene; missing: {', '.join(missing)}",
        metadata_json={
            "expected_files": expected,
            "present_files": sorted(present),
            "original_preserved": True,
            "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
        },
    )
    db.add(asset)
    db.flush()
    return asset


def _algorithm_versions(db: Session) -> None:
    versions = [
        (
            "algo-historical-preprocess",
            "historical_scene_preprocessing",
            "Validates georeferencing, clips with a geometry mask, and calculates transparent quality components.",
        ),
        (
            "algo-rice-temporal",
            "rice_temporal_analysis",
            "Three-observation rolling median with explainable peak and transition detection.",
        ),
        (
            "algo-recurring-zone",
            "recurring_zone_analysis",
            "Native 10 m quadrant summaries of recurring wetness and low vegetation candidates.",
        ),
    ]
    for identifier, name, description in versions:
        if db.get(AlgorithmVersion, identifier) is None:
            db.add(
                AlgorithmVersion(
                    id=identifier,
                    algorithm_name=name,
                    version=ALGORITHM_VERSION,
                    description=description,
                    parameters={
                        "provenance": "REFERENCE",
                        "deterministic": True,
                        "paid_api_required": False,
                    },
                )
            )


def _scene_inventory(root: Path) -> list[tuple[str, Path, Path | None, datetime]]:
    inventory: list[tuple[str, Path, Path | None, datetime]] = []
    configurations = [
        ("Sentinel-2", root / "sentinel2", "sentinel2_rice_bands.tif"),
        ("Sentinel-1", root / "sentinel1", "VV_dB.tif"),
    ]
    for sensor, sensor_root, main_name in configurations:
        if not sensor_root.exists():
            continue
        for scene_dir in sorted(path for path in sensor_root.iterdir() if path.is_dir()):
            captured_at = parse_scene_date(scene_dir.name)
            if captured_at is None:
                continue
            main_path = scene_dir / main_name
            inventory.append((sensor, scene_dir, main_path if main_path.exists() else None, captured_at))
    return inventory


def _classify_state(
    vegetation: float | None,
    water: float | None,
    bare: float | None,
    previous_vegetation: float | None,
) -> tuple[str, str]:
    if vegetation is None:
        return "UNCERTAIN", "Vegetation metric is unavailable."
    water = water or 0
    bare = bare or 0
    if previous_vegetation is not None and previous_vegetation - vegetation >= 0.18:
        return "HARVEST_WINDOW", "Vegetation score dropped by at least 0.18 from the previous usable image."
    if water >= 0.35 and vegetation < 0.35:
        return "FLOODED_OR_WET_PREPARATION", "Wetness candidate is high while vegetation is limited."
    if bare >= 0.55 and vegetation < 0.25:
        return "LAND_PREPARATION", "Bare/prepared-soil candidate dominates the plot."
    if vegetation < 0.18:
        return "FALLOW", "Vegetation score is below the fallow candidate threshold."
    if vegetation < 0.32:
        return "EARLY_GROWTH", "Vegetation score is in the early-growth candidate range."
    if vegetation >= 0.58:
        return "PEAK_VEGETATION", "Vegetation score is in the peak candidate range."
    if vegetation >= 0.42:
        return "VEGETATIVE_GROWTH", "Vegetation score is in the vegetative-growth candidate range."
    return "MATURITY_OR_DRYING", "Vegetation score is moderate without a sharp harvest transition."


def detect_crop_cycles(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect explainable candidate seasons from usable optical observations."""

    if len(points) < 5:
        return []
    ordered = sorted(points, key=lambda item: item["date"])
    raw = [item.get("vegetation_score") for item in ordered]
    smooth = rolling_median(raw, window=3)
    candidates: list[int] = []
    for index in range(1, len(smooth) - 1):
        current = smooth[index]
        if current is None or current < 0.38:
            continue
        previous = [value for value in smooth[max(0, index - 5) : index] if value is not None]
        following = [value for value in smooth[index + 1 : index + 6] if value is not None]
        if not previous or not following:
            continue
        prominence = current - min(min(previous), min(following))
        is_local_peak = current >= max(value for value in smooth[max(0, index - 2) : index + 3] if value is not None)
        if prominence >= 0.10 and is_local_peak:
            if not candidates or (ordered[index]["date"] - ordered[candidates[-1]]["date"]).days >= 70:
                candidates.append(index)
            elif current > (smooth[candidates[-1]] or -1):
                candidates[-1] = index

    cycles: list[dict[str, Any]] = []
    for cycle_number, peak_index in enumerate(candidates, start=1):
        peak_date = ordered[peak_index]["date"]
        before_indexes = [
            index
            for index in range(max(0, peak_index - 8), peak_index)
            if smooth[index] is not None and smooth[index] <= 0.32
        ]
        planting_anchor = (
            ordered[before_indexes[-1]]["date"]
            if before_indexes
            else peak_date - timedelta(days=55)
        )
        after_indexes = [
            index
            for index in range(peak_index + 1, min(len(ordered), peak_index + 9))
            if smooth[index] is not None and smooth[index] <= 0.32
        ]
        harvest_anchor = (
            ordered[after_indexes[0]]["date"]
            if after_indexes
            else peak_date + timedelta(days=45)
        )
        support_start = planting_anchor - timedelta(days=14)
        support_end = harvest_anchor + timedelta(days=14)
        supporting = [
            item
            for item in ordered
            if support_start <= item["date"] <= support_end
        ]
        maximum_area = max(
            (item.get("cultivated_area_estimate_rai") or 0 for item in supporting),
            default=0,
        )
        post_peak_harvest = max(
            (
                item.get("possible_harvested_area_rai") or 0
                for item in supporting
                if item["date"] >= peak_date
            ),
            default=0,
        )
        confidence = "HIGH" if len(supporting) >= 8 else "MODERATE" if len(supporting) >= 5 else "LOW"
        cycles.append(
            {
                "season_id": f"cycle-{peak_date.year}-{cycle_number}",
                "probable_start_date": support_start,
                "probable_planting_window_start": planting_anchor - timedelta(days=7),
                "probable_planting_window_end": planting_anchor + timedelta(days=7),
                "probable_peak_date": peak_date,
                "probable_harvest_window_start": harvest_anchor - timedelta(days=7),
                "probable_harvest_window_end": harvest_anchor + timedelta(days=7),
                "estimated_crop_duration_days": (harvest_anchor - planting_anchor).days,
                "estimated_cultivated_area_rai": round(maximum_area, 3),
                "estimated_harvested_area_rai": round(post_peak_harvest, 3),
                "number_of_supporting_images": len(supporting),
                "confidence": confidence,
                "evidence_image_ids": [item["image_id"] for item in supporting],
                "limitations": [
                    "Date windows are inferred from image intervals, not field records.",
                    "Candidate rice cycles require agronomic field confirmation.",
                ],
            }
        )
    return cycles


def _quadrant_geometry(key: str) -> dict[str, Any]:
    middle_lon = (PLOT_WEST + PLOT_EAST) / 2
    middle_lat = (PLOT_SOUTH + PLOT_NORTH) / 2
    bounds = {
        "NW": (PLOT_WEST, middle_lat, middle_lon, PLOT_NORTH),
        "NE": (middle_lon, middle_lat, PLOT_EAST, PLOT_NORTH),
        "SW": (PLOT_WEST, PLOT_SOUTH, middle_lon, middle_lat),
        "SE": (middle_lon, PLOT_SOUTH, PLOT_EAST, middle_lat),
    }[key]
    west, south, east, north = bounds
    return {
        "type": "Polygon",
        "coordinates": [
            [[west, south], [east, south], [east, north], [west, north], [west, south]]
        ],
    }


def _spatial_summaries(assets: list[ImageryAsset]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    quadrants: dict[str, dict[str, Any]] = {
        key: {"wet": [], "low": [], "cultivated": [], "support": []}
        for key in ("NW", "NE", "SW", "SE")
    }
    for asset in assets:
        path = Path(asset.source_path)
        if asset.source_name != "Sentinel-2" or not path.is_file() or asset.plot_intersection_percent < 80:
            continue
        with rasterio.open(path) as dataset:
            arrays, valid = _masked_values(dataset, [7, 9])
            ndvi, ndwi = arrays
            rows, columns = np.where(valid)
            if rows.size == 0:
                continue
            xs, ys = rasterio.transform.xy(dataset.transform, rows, columns)
            plot_in_source = transform_geom("EPSG:4326", dataset.crs, PLOT_GEOJSON)
            ring = plot_in_source["coordinates"][0]
            middle_x = (min(point[0] for point in ring) + max(point[0] for point in ring)) / 2
            middle_y = (min(point[1] for point in ring) + max(point[1] for point in ring)) / 2
            for key in quadrants:
                north = np.asarray(ys) >= middle_y
                east = np.asarray(xs) >= middle_x
                selector = {
                    "NW": north & ~east,
                    "NE": north & east,
                    "SW": ~north & ~east,
                    "SE": ~north & east,
                }[key]
                if not selector.any():
                    continue
                pixel_ndvi = ndvi[rows[selector], columns[selector]]
                pixel_ndwi = ndwi[rows[selector], columns[selector]]
                wet = float(np.mean(pixel_ndwi >= 0.1))
                low = float(np.mean(pixel_ndvi < 0.25))
                cultivated = float(np.mean(pixel_ndvi >= 0.25))
                quadrants[key]["wet"].append(wet)
                quadrants[key]["low"].append(low)
                quadrants[key]["cultivated"].append(cultivated)
                quadrants[key]["support"].append(
                    {
                        "image_id": asset.id,
                        "date": asset.acquisition_datetime.date().isoformat(),
                        "wet": round(wet, 4),
                        "low": round(low, 4),
                    }
                )

    summary = {}
    for key, values in quadrants.items():
        summary[key] = {
            "wetness_frequency": round(float(np.mean(values["wet"])), 4) if values["wet"] else 0,
            "low_growth_frequency": round(float(np.mean(values["low"])), 4) if values["low"] else 0,
            "cultivation_frequency": (
                round(float(np.mean(values["cultivated"])), 4) if values["cultivated"] else 0
            ),
            "usable_images": len(values["wet"]),
        }
    wet_key = max(summary, key=lambda key: summary[key]["wetness_frequency"])
    low_key = max(summary, key=lambda key: summary[key]["low_growth_frequency"])
    zones = []
    for zone_type, key, metric in (
        ("RECURRING_WETNESS_CANDIDATE", wet_key, "wet"),
        ("RECURRING_LOW_GROWTH_CANDIDATE", low_key, "low"),
    ):
        support = [
            item
            for item in quadrants[key]["support"]
            if item[metric] >= 0.35
        ]
        usable = summary[key]["usable_images"]
        years = sorted({int(item["date"][:4]) for item in support})
        zones.append(
            {
                "zone_key": f"{zone_type.lower()}-{key.lower()}",
                "zone_type": zone_type,
                "quadrant": key,
                "geometry": _quadrant_geometry(key),
                "number_of_occurrences": len(support),
                "number_of_usable_images": usable,
                "years_detected": years,
                "confidence": "HIGH" if len(support) >= 12 and len(years) >= 2 else "MODERATE",
                "supporting_images": [item["image_id"] for item in support[:24]],
            }
        )
    return summary, zones


def build_baseline_evidence_matrix(
    usable_image_ids: list[str], cycle_count: int
) -> list[dict[str, Any]]:
    observed_support = usable_image_ids[:24]
    rows = [
        ("rice_continuity", "Rice cultivation continuity", "MODERATE", "ESTIMATED", "Repeated vegetation transitions are consistent with recurring cultivation, subject to field confirmation."),
        ("cultivated_area", "Cultivated area", "STRONG", "DERIVED", "Plot-clipped multispectral cover fractions support an area range."),
        ("harvested_area", "Harvested area", "MODERATE", "ESTIMATED", "Post-peak vegetation decline and bare-surface candidates support an estimated range."),
        ("crop_cycle_count", "Probable crop-cycle count", "MODERATE", "ESTIMATED", f"{cycle_count} candidate cycles were detected from smoothed temporal transitions."),
        ("planting_window", "Probable planting window", "MODERATE", "ESTIMATED", "Planting is represented as date windows between available observations."),
        ("harvest_window", "Probable harvest window", "MODERATE", "ESTIMATED", "Harvest is represented as date windows after vegetation decline."),
        ("preseason_wetness", "Pre-season wetness", "MODERATE", "DERIVED", "Optical and radar wetness candidates provide contextual support."),
        ("flood_anomaly", "Flood anomaly", "WEAK", "ESTIMATED", "Weekly imagery may show wetness anomalies but does not prove cause or field water depth."),
        ("awd_cycles", "AWD cycles", "NOT_SUPPORTED", "UNKNOWN", "Weekly overhead imagery cannot independently verify AWD compliance."),
        ("water_depth", "Water depth", "NOT_SUPPORTED", "UNKNOWN", "Overhead imagery cannot measure water depth below the soil surface."),
        ("fertilizer_use", "Fertilizer use", "NOT_SUPPORTED", "UNKNOWN", "Fertilizer application requires field records or sensor evidence."),
        ("straw_management", "Straw management", "NOT_SUPPORTED", "UNKNOWN", "Straw handling cannot be determined reliably from the supplied imagery."),
        ("yield", "Yield", "NOT_SUPPORTED", "UNKNOWN", "No harvest-weighing or production records were supplied."),
        ("ghg_emissions", "GHG emissions", "NOT_SUPPORTED", "UNKNOWN", "Greenhouse-gas emissions are not directly observed by this imagery."),
    ]
    return [
        {
            "claim_key": key,
            "claim_label": label,
            "support_level": support,
            "provenance": provenance,
            "conclusion": conclusion,
            "evidence_image_ids": observed_support if support != "NOT_SUPPORTED" else [],
            "limitations": HISTORICAL_DISCLAIMERS[:2] if support != "NOT_SUPPORTED" else [conclusion],
        }
        for key, label, support, provenance, conclusion in rows
    ]


def propose_sensor_locations(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wet_zone = next((zone for zone in zones if "WETNESS" in zone["zone_type"]), None)
    low_zone = next((zone for zone in zones if "LOW_GROWTH" in zone["zone_type"]), None)
    middle_lon = (PLOT_WEST + PLOT_EAST) / 2
    middle_lat = (PLOT_SOUTH + PLOT_NORTH) / 2
    span_lon = PLOT_EAST - PLOT_WEST
    span_lat = PLOT_NORTH - PLOT_SOUTH
    configurations = [
        ("PRIMARY_WATER_LEVEL_SENSOR", middle_lon, middle_lat, "Representative central position for the primary AWD water-level record.", []),
        (
            "SECONDARY_WATER_LEVEL_SENSOR",
            PLOT_WEST + 0.25 * span_lon,
            PLOT_SOUTH + 0.25 * span_lat,
            (
                f"Proposed near recurring wetness zone ({wet_zone['number_of_occurrences']} candidate occurrences)."
                if wet_zone
                else "Proposed in the southwestern sector to test within-plot water variability."
            ),
            [wet_zone["zone_key"]] if wet_zone else [],
        ),
        ("RAINFALL_GAUGE", PLOT_EAST - 0.12 * span_lon, PLOT_NORTH - 0.12 * span_lat, "Proposed near the field edge to reduce crop-canopy obstruction.", []),
        (
            "SOIL_MOISTURE_SENSOR",
            PLOT_EAST - 0.25 * span_lon,
            PLOT_SOUTH + 0.25 * span_lat,
            (
                f"Proposed to field-check the recurring low-growth zone ({low_zone['number_of_occurrences']} candidate occurrences)."
                if low_zone
                else "Proposed in a contrasting field sector for paired soil-moisture observations."
            ),
            [low_zone["zone_key"]] if low_zone else [],
        ),
        ("INLET_FLOW_METER", PLOT_WEST + 0.04 * span_lon, middle_lat, "Assumed inlet-side position; hydraulic layout requires field verification.", []),
        ("DRAINAGE_OBSERVATION_POINT", PLOT_EAST - 0.04 * span_lon, middle_lat, "Assumed outlet-side position for drainage observation; not surveyed.", []),
        ("PUMP_ENERGY_METER", PLOT_WEST + 0.08 * span_lon, PLOT_NORTH - 0.08 * span_lat, "Proposed near an assumed pump connection; actual pump location is unknown.", []),
        ("FIELD_PHOTO_POINT", middle_lon, PLOT_SOUTH + 0.08 * span_lat, "Proposed repeat-photo point looking across the longest representative field view.", []),
    ]
    return [
        {
            "sensor_type": sensor_type,
            "longitude": longitude,
            "latitude": latitude,
            "status": "PROPOSED",
            "field_verification_status": "NOT_FIELD_VERIFIED",
            "rationale": rationale,
            "confidence": "MODERATE" if supporting else "LOW",
            "supporting_zone_ids": supporting,
            "assumptions": [
                "Synthetic demonstration boundary",
                "Access, inlet, outlet, pump, and elevation have not been field surveyed",
            ],
        }
        for sensor_type, longitude, latitude, rationale, supporting in configurations
    ]


def _build_temporal_analysis(db: Session, plot: Plot, force: bool = False) -> TemporalAnalysisRun:
    assets = list(
        db.scalars(
            select(ImageryAsset)
            .where(ImageryAsset.plot_id == plot.id)
            .order_by(ImageryAsset.acquisition_datetime)
        )
    )
    ready_assets = [asset for asset in assets if asset.processing_status in {"READY", "WARNING"}]
    image_count = len(assets)
    run_id = f"temporal-{plot.id.lower()}-{ALGORITHM_VERSION.lower()}"
    existing = db.get(TemporalAnalysisRun, run_id)
    if existing is not None and existing.image_count == image_count and not force:
        return existing
    if existing is not None:
        for model in (
            HistoricalCropSeason,
            CropStateObservation,
            SpatialAnalysisGrid,
            RecurringZone,
            BaselineEvidenceItem,
            SensorLocationProposal,
            AnalysisAssumption,
            AnalysisLimitation,
        ):
            db.execute(delete(model).where(model.temporal_analysis_run_id == run_id))
        db.delete(existing)
        db.flush()

    metrics = list(
        db.scalars(
            select(ImageryPlotMetric)
            .where(ImageryPlotMetric.plot_id == plot.id)
            .order_by(ImageryPlotMetric.acquisition_datetime)
        )
    )
    quality_by_asset = {
        item.imagery_asset_id: item
        for item in db.scalars(
            select(ImageryQualityResult).where(
                ImageryQualityResult.imagery_asset_id.in_([asset.id for asset in ready_assets])
            )
        )
    } if ready_assets else {}
    usable_metrics = [
        metric
        for metric in metrics
        if quality_by_asset.get(metric.imagery_asset_id)
        and quality_by_asset[metric.imagery_asset_id].usable
    ]
    optical = [metric for metric in usable_metrics if metric.sensor == "Sentinel-2"]
    points = [
        {
            "image_id": metric.imagery_asset_id,
            "date": metric.acquisition_datetime.date(),
            "vegetation_score": metric.vegetation_score,
            "water_candidate_fraction": metric.water_candidate_fraction,
            "bare_soil_fraction": metric.bare_soil_fraction,
            "cultivated_area_estimate_rai": metric.cultivated_area_estimate_rai,
            "possible_harvested_area_rai": metric.possible_harvested_area_rai,
        }
        for metric in optical
    ]
    cycles = detect_crop_cycles(points)
    dates = [
        asset.acquisition_datetime
        for asset in ready_assets
        if asset.acquisition_datetime is not None
    ]
    period_start = min(dates).date() if dates else None
    period_end = max(dates).date() if dates else None
    temporal_gaps = detect_temporal_gaps([metric.acquisition_datetime for metric in optical])
    spatial_summary, zone_results = _spatial_summaries(ready_assets)
    usable_count = len(usable_metrics)
    expected_months = (
        (period_end.year - period_start.year) * 12 + period_end.month - period_start.month + 1
        if period_start and period_end
        else 0
    )
    monthly_counts: dict[str, int] = defaultdict(int)
    for metric in usable_metrics:
        monthly_counts[metric.acquisition_datetime.strftime("%Y-%m")] += 1
    insufficient_months = sorted(key for key, count in monthly_counts.items() if count < 2)
    availability_score = round(min(100, 100 * image_count / max(1, expected_months * 8)), 2)
    temporal_score = round(max(0, 100 - min(70, len(temporal_gaps) * 4)), 2)
    spatial_score = round(
        sum(metric.usable_plot_coverage for metric in metrics) / max(1, len(metrics)), 2
    )
    image_quality_score = round(
        sum(metric.image_quality_score for metric in metrics) / max(1, len(metrics)), 2
    )
    classification_confidence = round(
        min(90, 45 + len(optical) * 0.25 + len(cycles) * 2), 2
    )
    completeness = round(
        0.2 * availability_score
        + 0.2 * image_quality_score
        + 0.2 * temporal_score
        + 0.2 * spatial_score
        + 0.2 * classification_confidence,
        2,
    )
    quality_scores = {
        "imagery_availability_score": availability_score,
        "image_quality_score": image_quality_score,
        "temporal_coverage_score": temporal_score,
        "spatial_coverage_score": spatial_score,
        "classification_confidence": classification_confidence,
        "crop_cycle_confidence": (
            round(sum({"HIGH": 90, "MODERATE": 70, "LOW": 45}[cycle["confidence"]] for cycle in cycles) / len(cycles), 2)
            if cycles
            else 0
        ),
        "cultivated_area_confidence": round(min(90, 50 + len(optical) * 0.35), 2),
        "historical_baseline_completeness": completeness,
    }
    run = TemporalAnalysisRun(
        id=run_id,
        plot_id=plot.id,
        algorithm_version=ALGORITHM_VERSION,
        status="READY",
        period_start=period_start,
        period_end=period_end,
        image_count=image_count,
        usable_image_count=usable_count,
        parameters={
            "smoothing": "rolling_median",
            "smoothing_window_observations": 3,
            "expected_interval_days": 8,
            "interpolation_enabled": False,
            "analysis_grid": "native_10m",
        },
        quality_scores=quality_scores,
        result_summary={
            "probable_crop_cycles": len(cycles),
            "temporal_gaps": temporal_gaps,
            "insufficient_months": insufficient_months,
            "source_counts": {
                "Sentinel-2": sum(asset.source_name == "Sentinel-2" for asset in assets),
                "Sentinel-1": sum(asset.source_name == "Sentinel-1" for asset in assets),
            },
            "failed_assets": [
                {"image_id": asset.id, "error": asset.processing_error}
                for asset in assets
                if asset.processing_status == "FAILED"
            ],
            "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
            "disclaimers": HISTORICAL_DISCLAIMERS,
        },
        completed_at=utcnow(),
    )
    db.add(run)
    db.flush()

    for cycle in cycles:
        db.add(
            HistoricalCropSeason(
                id=f"{run_id}-{cycle['season_id']}",
                temporal_analysis_run_id=run_id,
                plot_id=plot.id,
                algorithm_version=ALGORITHM_VERSION,
                **{key: value for key, value in cycle.items() if key != "season_id"},
            )
        )

    previous_vegetation: float | None = None
    for metric in optical:
        state, explanation = _classify_state(
            metric.vegetation_score,
            metric.water_candidate_fraction,
            metric.bare_soil_fraction,
            previous_vegetation,
        )
        db.add(
            CropStateObservation(
                id=f"state-{metric.imagery_asset_id}",
                temporal_analysis_run_id=run_id,
                imagery_asset_id=metric.imagery_asset_id,
                plot_id=plot.id,
                observed_on=metric.acquisition_datetime.date(),
                state=state,
                confidence=metric.confidence,
                explanation=explanation,
            )
        )
        previous_vegetation = metric.vegetation_score

    db.add(
        SpatialAnalysisGrid(
            id=f"grid-{run_id}",
            temporal_analysis_run_id=run_id,
            plot_id=plot.id,
            resolution_m=10,
            crs="EPSG:32647",
            width=4,
            height=1,
            summary={
                "aggregation": "four native-grid plot quadrants",
                "quadrants": spatial_summary,
                "no_oversampling": True,
            },
            algorithm_version=ALGORITHM_VERSION,
        )
    )
    zones_for_proposals = []
    for index, zone in enumerate(zone_results, start=1):
        zone_id = f"zone-{run_id}-{index}"
        zones_for_proposals.append({**zone, "zone_key": zone_id})
        db.add(
            RecurringZone(
                id=zone_id,
                temporal_analysis_run_id=run_id,
                plot_id=plot.id,
                zone_type=zone["zone_type"],
                geometry_json=zone["geometry"],
                number_of_occurrences=zone["number_of_occurrences"],
                number_of_usable_images=zone["number_of_usable_images"],
                years_detected=zone["years_detected"],
                season_ids=[f"{run_id}-{cycle['season_id']}" for cycle in cycles],
                confidence=zone["confidence"],
                supporting_images=zone["supporting_images"],
                recommended_field_check=(
                    "Install a temporary field logger and repeat geotagged photos before final sensor placement."
                ),
                limitations=[
                    "Zone is a 10 m imagery candidate summarized to a quadrant.",
                    "Location has not been field surveyed or elevation-corrected.",
                ],
            )
        )

    evidence_rows = build_baseline_evidence_matrix(
        [metric.imagery_asset_id for metric in usable_metrics], len(cycles)
    )
    for row in evidence_rows:
        db.add(
            BaselineEvidenceItem(
                id=f"evidence-{run_id}-{row['claim_key']}",
                temporal_analysis_run_id=run_id,
                plot_id=plot.id,
                **row,
            )
        )

    for index, proposal in enumerate(propose_sensor_locations(zones_for_proposals), start=1):
        db.add(
            SensorLocationProposal(
                id=f"sensor-proposal-{run_id}-{index}",
                temporal_analysis_run_id=run_id,
                plot_id=plot.id,
                **proposal,
            )
        )

    assumptions = {
        "plot_boundary": "The DEMO-PLOT-001 boundary is synthetic and is used only to exercise plot-level analysis.",
        "rice_candidate": "Temporal vegetation and wetness transitions are treated as probable rice-cycle evidence, not crop-species verification.",
        "field_access": "Sensor access, inlet, outlet, pump and elevation locations are assumed for demonstration.",
    }
    for key, statement in assumptions.items():
        db.add(
            AnalysisAssumption(
                id=f"assumption-{run_id}-{key}",
                temporal_analysis_run_id=run_id,
                assumption_key=key,
                statement=statement,
            )
        )
    for index, statement in enumerate(HISTORICAL_DISCLAIMERS, start=1):
        db.add(
            AnalysisLimitation(
                id=f"limitation-{run_id}-{index}",
                temporal_analysis_run_id=run_id,
                limitation_key=f"required_disclaimer_{index}",
                statement=statement,
            )
        )
    db.flush()
    return run


def import_historical_archive(
    db: Session, plot: Plot, root: Path, force_analysis: bool = False
) -> dict[str, Any]:
    """Idempotently import both archives and run the temporal analysis."""

    if not root.exists():
        return {
            "status": "SKIPPED",
            "reason": f"Historical archive not mounted: {root}",
            "imported": 0,
        }
    _algorithm_versions(db)
    imported = 0
    failed = 0
    inventory = _scene_inventory(root)
    for sensor, scene_dir, main_path, captured_at in inventory:
        before = db.get(ImageryAsset, _asset_id(sensor, captured_at))
        if main_path is None:
            asset = _record_incomplete_scene(db, plot, scene_dir, sensor, captured_at)
        else:
            asset = _process_scene(db, plot, sensor, scene_dir, main_path, captured_at)
        if before is None:
            imported += 1
        if asset.processing_status == "FAILED":
            failed += 1
    db.flush()
    run = _build_temporal_analysis(db, plot, force=force_analysis)
    db.commit()
    return {
        "status": "READY",
        "inventory_count": len(inventory),
        "imported": imported,
        "failed": failed,
        "analysis_run_id": run.id,
        "image_count": run.image_count,
        "usable_image_count": run.usable_image_count,
        "quality_scores": run.quality_scores,
    }


def latest_analysis_run(db: Session, plot_id: str) -> TemporalAnalysisRun | None:
    return db.scalar(
        select(TemporalAnalysisRun)
        .where(TemporalAnalysisRun.plot_id == plot_id)
        .order_by(TemporalAnalysisRun.completed_at.desc())
        .limit(1)
    )


def serialize_metric(metric: ImageryPlotMetric, asset: ImageryAsset) -> dict[str, Any]:
    return {
        "image_id": asset.id,
        "date": asset.acquisition_datetime.date().isoformat() if asset.acquisition_datetime else None,
        "sensor": asset.source_name,
        "bounds": asset.bounds,
        "footprint": asset.footprint,
        "coordinates": (asset.metadata_json or {}).get("display_coordinates_wgs84"),
        "status": asset.processing_status,
        "quality": asset.quality_score,
        "plot_coverage_percent": asset.plot_intersection_percent,
        "vegetation_score": metric.vegetation_score,
        "water_candidate_fraction": metric.water_candidate_fraction,
        "wet_soil_fraction": metric.wet_soil_fraction,
        "bare_soil_fraction": metric.bare_soil_fraction,
        "dense_vegetation_fraction": metric.dense_vegetation_fraction,
        "uncertain_fraction": metric.uncertain_fraction,
        "cultivated_area_estimate_rai": metric.cultivated_area_estimate_rai,
        "possible_harvested_area_rai": metric.possible_harvested_area_rai,
        "uniformity_score": metric.uniformity_score,
        "raw_metrics": metric.raw_metrics,
        "provenance": metric.provenance,
        "confidence": metric.confidence,
        "limitations": metric.limitations,
        "algorithm_version": metric.algorithm_version,
        "processed_at": metric.processed_at,
    }


def timeline_payload(db: Session, plot_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        select(ImageryPlotMetric, ImageryAsset)
        .join(ImageryAsset, ImageryAsset.id == ImageryPlotMetric.imagery_asset_id)
        .where(ImageryPlotMetric.plot_id == plot_id)
        .order_by(ImageryPlotMetric.acquisition_datetime)
    ).all()
    raw = [serialize_metric(metric, asset) for metric, asset in rows]
    optical_values = [
        item["vegetation_score"] if item["sensor"] == "Sentinel-2" else None for item in raw
    ]
    smoothed = rolling_median(optical_values, window=3)
    for item, smoothed_value in zip(raw, smoothed):
        item["smoothed_vegetation_score"] = smoothed_value
    return raw


def historical_baseline_payload(db: Session, plot_id: str) -> dict[str, Any] | None:
    run = latest_analysis_run(db, plot_id)
    if run is None:
        return None
    timeline = timeline_payload(db, plot_id)
    cycles = list(
        db.scalars(
            select(HistoricalCropSeason)
            .where(HistoricalCropSeason.temporal_analysis_run_id == run.id)
            .order_by(HistoricalCropSeason.probable_start_date)
        )
    )
    years: dict[int, dict[str, Any]] = {}
    for year in range(run.period_start.year if run.period_start else 0, (run.period_end.year if run.period_end else -1) + 1):
        year_timeline = [item for item in timeline if item["date"] and int(item["date"][:4]) == year]
        year_cycles = [
            cycle
            for cycle in cycles
            if cycle.probable_peak_date and cycle.probable_peak_date.year == year
        ]
        cultivated = [
            item["cultivated_area_estimate_rai"]
            for item in year_timeline
            if item["cultivated_area_estimate_rai"] is not None and item["sensor"] == "Sentinel-2"
        ]
        harvested = [
            item["possible_harvested_area_rai"]
            for item in year_timeline
            if item["possible_harvested_area_rai"] is not None and item["sensor"] == "Sentinel-2"
        ]
        years[year] = {
            "year": year,
            "probable_crop_cycles": len(year_cycles),
            "cultivated_area_range_rai": [
                round(min(cultivated), 2) if cultivated else None,
                round(max(cultivated), 2) if cultivated else None,
            ],
            "harvested_area_range_rai": [
                round(min(harvested), 2) if harvested else None,
                round(max(harvested), 2) if harvested else None,
            ],
            "planting_windows": [
                [cycle.probable_planting_window_start, cycle.probable_planting_window_end]
                for cycle in year_cycles
            ],
            "peak_dates": [cycle.probable_peak_date for cycle in year_cycles],
            "harvest_windows": [
                [cycle.probable_harvest_window_start, cycle.probable_harvest_window_end]
                for cycle in year_cycles
            ],
            "image_count": len(year_timeline),
            "confidence": (
                "HIGH" if len(year_timeline) >= 70 else "MODERATE" if len(year_timeline) >= 35 else "LOW"
            ),
        }
    cultivated_all = [
        item["cultivated_area_estimate_rai"]
        for item in timeline
        if item["cultivated_area_estimate_rai"] is not None and item["sensor"] == "Sentinel-2"
    ]
    harvested_all = [
        item["possible_harvested_area_rai"]
        for item in timeline
        if item["possible_harvested_area_rai"] is not None and item["sensor"] == "Sentinel-2"
    ]
    return {
        "analysis_run_id": run.id,
        "plot_id": plot_id,
        "period": [run.period_start, run.period_end],
        "image_count": run.image_count,
        "usable_image_count": run.usable_image_count,
        "average_images_per_month": round(
            run.image_count
            / max(
                1,
                (run.period_end.year - run.period_start.year) * 12
                + run.period_end.month
                - run.period_start.month
                + 1,
            ),
            2,
        )
        if run.period_start and run.period_end
        else 0,
        "probable_crop_cycles": len(cycles),
        "cultivated_area_range_rai": [
            round(min(cultivated_all), 2) if cultivated_all else None,
            round(max(cultivated_all), 2) if cultivated_all else None,
        ],
        "harvested_area_range_rai": [
            round(min(harvested_all), 2) if harvested_all else None,
            round(max(harvested_all), 2) if harvested_all else None,
        ],
        "years": list(years.values()),
        "quality_scores": run.quality_scores,
        "result_summary": run.result_summary,
        "algorithm": {
            "name": "rice_temporal_analysis",
            "version": run.algorithm_version,
            "processing_timestamp": run.completed_at,
            "input_bands": ["B02", "B03", "B04", "B08", "B11", "B12", "NDVI", "LSWI", "NDWI", "EVI", "VV", "VH"],
            "spatial_resolution_m": 10,
            "smoothing": "3-observation rolling median",
            "interpolation_enabled": False,
        },
        "provenance": "DERIVED",
        "confidence": (
            "HIGH"
            if run.quality_scores.get("historical_baseline_completeness", 0) >= 80
            else "MODERATE"
        ),
        "limitations": HISTORICAL_DISCLAIMERS,
        "synthetic_boundary_warning": DEMO_BOUNDARY_WARNING,
    }
