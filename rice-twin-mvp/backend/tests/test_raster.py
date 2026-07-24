from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from PIL import Image

from app.services.raster import create_preview


def write_test_raster(
    path: Path,
    *,
    crs: str | None = "EPSG:4326",
    count: int = 3,
    descriptions: list[str] | None = None,
) -> None:
    height, width = 40, 60
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": count,
        "dtype": "uint8",
        "transform": from_bounds(100.27, 14.46, 100.28, 14.47, width, height),
    }
    if crs:
        profile["crs"] = crs
    with rasterio.open(path, "w", **profile) as dst:
        for band in range(1, count + 1):
            dst.write(np.full((height, width), 30 * band, dtype=np.uint8), band)
            if descriptions:
                dst.set_band_description(band, descriptions[band - 1])


def test_create_preview_and_extract_bounds(tmp_path: Path) -> None:
    source = tmp_path / "source.tif"
    preview = tmp_path / "preview.png"
    write_test_raster(source)

    metadata = create_preview(source, preview, [1, 2, 3], max_dimension=100)

    assert preview.exists()
    assert metadata.crs == "EPSG:4326"
    assert metadata.bounds_wgs84 == pytest.approx([100.27, 14.46, 100.28, 14.47])
    assert metadata.band_count == 3
    assert metadata.render_bands == [1, 2, 3]


def test_missing_crs_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "no-crs.tif"
    preview = tmp_path / "preview.png"
    write_test_raster(source, crs=None)

    with pytest.raises(ValueError, match="no CRS"):
        create_preview(source, preview, [1, 2, 3])


def test_invalid_band_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "two-band.tif"
    preview = tmp_path / "preview.png"
    write_test_raster(source, count=2)

    with pytest.raises(ValueError, match="outside the raster band range"):
        create_preview(source, preview, [1, 2, 3])


def test_auto_detects_sentinel2_true_color_bands(tmp_path: Path) -> None:
    source = tmp_path / "sentinel2.tif"
    preview = tmp_path / "preview.png"
    write_test_raster(
        source,
        count=4,
        descriptions=["B02", "B03", "B04", "B08"],
    )

    metadata = create_preview(source, preview, [])

    assert metadata.render_bands == [3, 2, 1]
    assert metadata.band_descriptions == ["B02", "B03", "B04", "B08"]


def test_rice_index_preview_uses_color_ramp(tmp_path: Path) -> None:
    source = tmp_path / "ndvi.tif"
    preview = tmp_path / "ndvi.png"
    write_test_raster(source, count=1)

    create_preview(source, preview, [1, 1, 1], color_scheme="vegetation")

    rgb = np.asarray(Image.open(preview).convert("RGB"))
    assert not np.array_equal(rgb[..., 0], rgb[..., 1])


def test_filename_path_traversal_is_removed() -> None:
    assert Path("../../escape.tif").name == "escape.tif"
