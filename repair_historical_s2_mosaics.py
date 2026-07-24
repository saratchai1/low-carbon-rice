"""Repair cached Sentinel-2 scenes that contain only one side of an MGRS boundary."""

from __future__ import annotations

import glob
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import planetary_computer as pc
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds


ROOT = Path(__file__).resolve().parent
S2_ROOT = ROOT / "output_3yr_4per_month" / "sentinel2"
BBOX = [100.264733, 14.459728, 100.284733, 14.479728]
DATE_RANGE = "2023-07-01T00:00:00Z/2026-07-24T23:59:59Z"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]


def partial_scene_directories() -> list[Path]:
    partial = []
    for name in glob.glob(str(S2_ROOT / "*" / "sentinel2_rice_bands.tif")):
        with rasterio.open(name) as source:
            if source.height < 200:
                partial.append(Path(name).parent)
    return sorted(partial)


def query_items_by_date() -> dict[str, list[dict]]:
    response = requests.post(
        STAC_URL,
        json={
            "collections": ["sentinel-2-l2a"],
            "bbox": BBOX,
            "datetime": DATE_RANGE,
            "limit": 500,
        },
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    response.raise_for_status()
    by_date: dict[str, dict[str, dict]] = {}
    for item in response.json().get("features", []):
        date = item["properties"]["datetime"][:10]
        match = re.search(r"_T([0-9]{2}[A-Z]{3})_", item["id"])
        tile = match.group(1) if match else item["id"]
        existing = by_date.setdefault(date, {}).get(tile)
        cloud = item["properties"].get("eo:cloud_cover", 100.0)
        if existing is None or cloud < existing["properties"].get("eo:cloud_cover", 100.0):
            by_date[date][tile] = item
    return {date: list(tiles.values()) for date, tiles in by_date.items()}


def destination_grid():
    minx, miny, maxx, maxy = transform_bounds(
        "EPSG:4326", "EPSG:32647", *BBOX, densify_pts=21
    )
    minx = math.floor(minx / 10) * 10
    miny = math.floor(miny / 10) * 10
    maxx = math.ceil(maxx / 10) * 10
    maxy = math.ceil(maxy / 10) * 10
    return (
        int(round((maxx - minx) / 10)),
        int(round((maxy - miny) / 10)),
        from_origin(minx, maxy, 10, 10),
    )


WIDTH, HEIGHT, TRANSFORM = destination_grid()


def mosaic_band(urls: list[str]) -> np.ndarray:
    mosaic = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    for url in urls:
        for attempt in range(1, 4):
            try:
                with rasterio.open(url) as source:
                    tile = np.full_like(mosaic, np.nan)
                    reproject(
                        source=rasterio.band(source, 1),
                        destination=tile,
                        src_transform=source.transform,
                        src_crs=source.crs,
                        src_nodata=source.nodata,
                        dst_transform=TRANSFORM,
                        dst_crs="EPSG:32647",
                        dst_nodata=np.nan,
                        resampling=Resampling.bilinear,
                    )
                    valid = np.isnan(mosaic) & np.isfinite(tile)
                    mosaic[valid] = tile[valid]
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt)
    if not np.isfinite(mosaic).any():
        raise RuntimeError("Mosaic has no valid pixels")
    return mosaic / 10000.0


def write_single(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(".repairing.tif")
    with rasterio.open(
        temporary,
        "w",
        driver="GTiff",
        width=WIDTH,
        height=HEIGHT,
        count=1,
        dtype="float32",
        crs="EPSG:32647",
        transform=TRANSFORM,
        nodata=np.nan,
    ) as target:
        target.write(values.astype("float32"), 1)
    os.replace(temporary, path)


def write_stack(path: Path, bands: dict[str, np.ndarray]) -> None:
    temporary = path.with_suffix(".repairing.tif")
    with rasterio.open(
        temporary,
        "w",
        driver="GTiff",
        width=WIDTH,
        height=HEIGHT,
        count=len(bands),
        dtype="float32",
        crs="EPSG:32647",
        transform=TRANSFORM,
        nodata=np.nan,
    ) as target:
        for index, (name, values) in enumerate(bands.items(), 1):
            target.write(values.astype("float32"), index)
            target.set_band_description(index, name)
    os.replace(temporary, path)


def repair(scene_dir: Path, raw_items: list[dict]) -> str:
    signed = [pc.sign(item) for item in raw_items]
    bands = {}
    for band in BANDS:
        urls = [item["assets"][band]["href"] for item in signed if band in item["assets"]]
        bands[band] = mosaic_band(urls)

    blue, green, red = bands["B02"], bands["B03"], bands["B04"]
    nir, swir1 = bands["B08"], bands["B11"]
    with np.errstate(divide="ignore", invalid="ignore"):
        bands["NDVI"] = np.clip((nir - red) / (nir + red), -1, 1)
        bands["LSWI"] = np.clip((nir - swir1) / (nir + swir1), -1, 1)
        bands["NDWI"] = np.clip((green - nir) / (green + nir), -1, 1)
        bands["EVI"] = np.clip(
            2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1), -1, 1.5
        )
    write_stack(scene_dir / "sentinel2_rice_bands.tif", bands)
    for name in ("NDVI", "LSWI", "NDWI"):
        write_single(scene_dir / f"{name}.tif", bands[name])
    return scene_dir.name[:10]


def main() -> None:
    partial = partial_scene_directories()
    print(f"Found {len(partial)} partial Sentinel-2 scenes")
    if not partial:
        return
    items_by_date = query_items_by_date()
    missing = [path.name[:10] for path in partial if path.name[:10] not in items_by_date]
    if missing:
        raise RuntimeError(f"STAC query did not return dates: {', '.join(missing)}")
    with ThreadPoolExecutor(max_workers=8) as executor:
        jobs = {
            executor.submit(repair, path, items_by_date[path.name[:10]]): path
            for path in partial
        }
        for completed, future in enumerate(as_completed(jobs), 1):
            print(f"[{completed}/{len(jobs)}] repaired {future.result()}", flush=True)


if __name__ == "__main__":
    main()
