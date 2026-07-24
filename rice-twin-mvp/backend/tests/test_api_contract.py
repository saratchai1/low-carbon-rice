from pathlib import Path
from types import SimpleNamespace

from app.main import carbon_status, health, imagery_variant, infer_capture_datetime


class FakeDb:
    def get(self, model, plot_id):
        return object() if plot_id == "DEMO-PLOT-001" else None


def test_health_endpoint_contract() -> None:
    assert health() == {"status": "ok"}


def test_carbon_endpoint_is_not_configured() -> None:
    result = carbon_status("DEMO-PLOT-001", FakeDb())
    assert result["status"] == "not_configured"
    assert result["methodology_version"] is None
    assert result["creditable_amount"] is None
    assert "no carbon-credit claim" in result["message"]


def test_capture_date_is_inferred_from_common_filenames() -> None:
    assert infer_capture_datetime("2026-07-19_scene.tif").date().isoformat() == "2026-07-19"
    assert infer_capture_datetime("S2A_20260701T034201.tif").date().isoformat() == "2026-07-01"
    assert infer_capture_datetime("unknown.tif") is None


def test_rice_display_modes_map_to_processed_sentinel_bands() -> None:
    sentinel2 = SimpleNamespace(
        stored_path="/satellite-output/scene/sentinel2_rice_bands.tif",
        source_metadata={"satellite": "Sentinel-2"},
    )
    sentinel1 = SimpleNamespace(
        stored_path="/satellite-output/scene/VV_dB.tif",
        source_metadata={"satellite": "Sentinel-1"},
    )

    assert imagery_variant(sentinel2, "rice_ndvi")[1:] == ([7, 7, 7], "vegetation")
    assert imagery_variant(sentinel2, "rice_lswi")[1:] == ([8, 8, 8], "water")
    assert imagery_variant(sentinel1, "rice_sar_vh")[0] == Path("/satellite-output/scene/VH_dB.tif")
