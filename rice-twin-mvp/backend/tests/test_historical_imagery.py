from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from app.main import app
from app.services.historical_imagery import (
    ALGORITHM_VERSION,
    HISTORICAL_DISCLAIMERS,
    _s2_metrics,
    build_baseline_evidence_matrix,
    calculate_multispectral_indices,
    calculate_rgb_indices,
    detect_crop_cycles,
    detect_temporal_gaps,
    propose_sensor_locations,
    rolling_median,
    sha256_file,
    validate_band_mapping,
)


client = TestClient(app)


def _write_s2_stack(path: Path, *, crs: str | None = "EPSG:32647", outside: bool = False):
    width, height = 32, 32
    transform = (
        from_origin(1000, 1000, 10, 10)
        if outside
        else from_origin(637220, 1600140, 10, 10)
    )
    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": 10,
        "dtype": "float32",
        "transform": transform,
        "nodata": np.nan,
    }
    if crs is not None:
        profile["crs"] = crs
    stack = np.zeros((10, height, width), dtype=np.float32)
    stack[0:6] = 0.2
    stack[6] = 0.55
    stack[7] = 0.1
    stack[8] = 0.15
    stack[9] = 0.45
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(stack)


def _point(day: int, vegetation: float) -> dict:
    return {
        "image_id": f"image-{day}",
        "date": date(2024, 1, 1) + timedelta(days=day),
        "vegetation_score": vegetation,
        "water_candidate_fraction": 0.4 if vegetation < 0.25 else 0.05,
        "bare_soil_fraction": 0.7 if vegetation < 0.2 else 0.1,
        "cultivated_area_estimate_rai": vegetation * 24,
        "possible_harvested_area_rai": (1 - vegetation) * 10,
    }


def test_sha256_is_deterministic_and_detects_identical_content(tmp_path):
    first = tmp_path / "first.tif"
    second = tmp_path / "second.tif"
    first.write_bytes(b"same-raster-content")
    second.write_bytes(b"same-raster-content")
    assert sha256_file(first) == sha256_file(second)
    assert len(sha256_file(first)) == 64


def test_valid_geotiff_is_clipped_and_scored(tmp_path):
    path = tmp_path / "valid.tif"
    _write_s2_stack(path)
    result = _s2_metrics(path, 24)
    assert result["metadata"]["crs"] == "EPSG:32647"
    assert result["metadata"]["band_count"] == 10
    assert result["quality"]["spatial_coverage_score"] > 0
    assert result["metric"]["vegetation_score"] == pytest.approx(0.55)


def test_invalid_crs_is_rejected(tmp_path):
    path = tmp_path / "invalid-crs.tif"
    _write_s2_stack(path, crs=None)
    with pytest.raises(ValueError, match="no CRS"):
        _s2_metrics(path, 24)


def test_image_outside_plot_is_clearly_low_coverage(tmp_path):
    path = tmp_path / "outside.tif"
    _write_s2_stack(path, outside=True)
    result = _s2_metrics(path, 24)
    assert result["quality"]["spatial_coverage_score"] == 0
    assert result["quality"]["usable"] is False


def test_nodata_is_excluded_from_multispectral_metric(tmp_path):
    path = tmp_path / "nodata.tif"
    _write_s2_stack(path)
    with rasterio.open(path, "r+") as dataset:
        array = dataset.read(7)
        array[0:4, 0:4] = np.nan
        dataset.write(array, 7)
    result = _s2_metrics(path, 24)
    assert np.isfinite(result["metric"]["vegetation_score"])
    assert 0 <= result["quality"]["valid_pixel_fraction"] <= 1


def test_band_mapping_requires_explicit_semantics():
    validate_band_mapping(
        "Sentinel-2",
        {"BLUE": 1, "GREEN": 2, "RED": 3, "NIR": 4, "SWIR1": 5},
    )
    with pytest.raises(ValueError, match="NIR"):
        validate_band_mapping("Sentinel-2", {"BLUE": 1, "GREEN": 2, "RED": 3})
    with pytest.raises(ValueError, match="unique"):
        validate_band_mapping(
            "Sentinel-2", {"BLUE": 1, "GREEN": 2, "RED": 3, "NIR": 3}
        )


def test_multispectral_indices_are_numerically_correct():
    red = np.array([[0.2]], dtype=np.float32)
    green = np.array([[0.3]], dtype=np.float32)
    blue = np.array([[0.1]], dtype=np.float32)
    nir = np.array([[0.6]], dtype=np.float32)
    swir = np.array([[0.4]], dtype=np.float32)
    indices = calculate_multispectral_indices(red, green, blue, nir, swir)
    assert indices["NDVI"][0, 0] == pytest.approx(0.5)
    assert indices["NDMI"][0, 0] == pytest.approx(0.2)
    assert {"NDVI", "GNDVI", "NDWI", "SAVI", "EVI", "MNDWI", "NDMI"} <= set(indices)


def test_rgb_analysis_does_not_mislabel_visible_score_as_ndvi():
    values = np.array([[10, 20]], dtype=np.float32)
    result = calculate_rgb_indices(values, values * 2, values / 2)
    assert "NDVI" not in result
    assert {"EXCESS_GREEN", "VARI", "GLI", "NORMALIZED_GREEN", "BRIGHTNESS"} == set(result)


def test_rolling_median_is_deterministic_and_preserves_raw_series():
    raw = [0.1, 0.9, 0.2, None, 0.4]
    assert rolling_median(raw) == rolling_median(raw)
    assert raw == [0.1, 0.9, 0.2, None, 0.4]
    assert rolling_median(raw)[1] == pytest.approx(0.2)


def test_temporal_gap_detection_is_chronological():
    gaps = detect_temporal_gaps(
        [date(2024, 2, 10), date(2024, 1, 1), date(2024, 1, 9)]
    )
    assert gaps == [
        {
            "start": "2024-01-09",
            "end": "2024-02-10",
            "days": 32,
            "expected_days": 8,
        }
    ]


def test_no_cycle_or_fallow_sequence_returns_no_cycle():
    points = [_point(index * 14, 0.12) for index in range(10)]
    assert detect_crop_cycles(points) == []


def test_multiple_crop_cycles_use_date_windows_not_false_precision():
    vegetation = [0.1, 0.2, 0.45, 0.66, 0.4, 0.12, 0.1, 0.22, 0.5, 0.7, 0.38, 0.1]
    cycles = detect_crop_cycles(
        [_point(index * 14, value) for index, value in enumerate(vegetation)]
    )
    assert len(cycles) == 2
    assert cycles[0]["probable_planting_window_start"] < cycles[0]["probable_planting_window_end"]
    assert cycles[0]["probable_harvest_window_start"] < cycles[0]["probable_harvest_window_end"]
    assert cycles[0]["number_of_supporting_images"] >= 5


def test_baseline_evidence_marks_unsupported_claims():
    rows = build_baseline_evidence_matrix(["image-1", "image-2"], 2)
    by_key = {row["claim_key"]: row for row in rows}
    assert len(rows) == 14
    assert by_key["cultivated_area"]["support_level"] == "STRONG"
    assert by_key["awd_cycles"]["support_level"] == "NOT_SUPPORTED"
    assert by_key["water_depth"]["provenance"] == "UNKNOWN"
    assert by_key["ghg_emissions"]["evidence_image_ids"] == []


def test_sensor_proposals_are_not_field_verified():
    zones = [
        {
            "zone_key": "wet-zone",
            "zone_type": "RECURRING_WETNESS_CANDIDATE",
            "number_of_occurrences": 12,
        },
        {
            "zone_key": "low-zone",
            "zone_type": "RECURRING_LOW_GROWTH_CANDIDATE",
            "number_of_occurrences": 9,
        },
    ]
    proposals = propose_sensor_locations(zones)
    assert len(proposals) == 8
    assert all(item["status"] == "PROPOSED" for item in proposals)
    assert all(item["field_verification_status"] == "NOT_FIELD_VERIFIED" for item in proposals)
    assert all(14.469 <= item["latitude"] <= 14.471 for item in proposals)


def test_required_disclaimers_are_complete():
    assert len(HISTORICAL_DISCLAIMERS) == 6
    assert any("AWD compliance" in item for item in HISTORICAL_DISCLAIMERS)
    assert any("water depth" in item for item in HISTORICAL_DISCLAIMERS)
    assert any("not verified carbon credits" in item for item in HISTORICAL_DISCLAIMERS)


def test_historical_page_and_replay_api_are_connected():
    page = client.get("/historical")
    assert page.status_code == 200
    assert "Historical Baseline Explorer" in page.text
    response = client.get("/api/v1/plots/DEMO-PLOT-001/imagery-timeline")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert len(data["raw_observations"]) >= 200
    assert data["smoothing"]["interpolation_enabled"] is False
    assert data["raw_observations"][0]["preview_url"].startswith("/api/v1/imagery/")


def test_historical_baseline_api_exposes_separate_confidence_components():
    response = client.get("/api/v1/plots/DEMO-PLOT-001/historical-baseline")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["algorithm"]["version"] == ALGORITHM_VERSION
    assert data["image_count"] >= data["usable_image_count"]
    assert len(data["quality_scores"]) == 8
    assert data["provenance"] == "DERIVED"
    assert data["synthetic_boundary_warning"]


def test_historical_preview_supports_optical_and_radar_modes():
    optical = client.get("/api/v1/imagery/hist-s2-2025-01-05/preview.png?mode=ndvi")
    radar = client.get("/api/v1/imagery/hist-s1-2025-01-04/preview.png?mode=vh_vv_diff")
    assert optical.status_code == 200
    assert optical.headers["content-type"] == "image/png"
    assert radar.status_code == 200
    assert radar.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/plots/DEMO-PLOT-001/exports/historical-baseline.json",
        "/api/v1/plots/DEMO-PLOT-001/exports/recurring-zones.geojson",
        "/api/v1/plots/DEMO-PLOT-001/exports/sensor-proposals.geojson",
    ],
)
def test_json_exports_include_auditable_metadata(path):
    response = client.get(path)
    assert response.status_code == 200
    metadata = response.json()["metadata"]
    assert metadata["plot_id"] == "DEMO-PLOT-001"
    assert metadata["image_count"] >= 200
    assert metadata["algorithm_versions"] == [ALGORITHM_VERSION]
    assert metadata["provenance"] == "DERIVED"
    assert metadata["limitations"]
    assert metadata["synthetic_boundary_warning"]
    assert metadata["demo_disclaimer"]


def test_csv_export_contains_metadata_and_raw_observations():
    response = client.get("/api/v1/plots/DEMO-PLOT-001/exports/timeline.csv")
    assert response.status_code == 200
    assert "# plot_id,DEMO-PLOT-001" in response.text
    assert "smoothed_vegetation_score" in response.text
    assert "synthetic_boundary_warning" in response.text
