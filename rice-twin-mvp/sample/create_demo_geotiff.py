"""Create a synthetic georeferenced RGB GeoTIFF for testing the upload workflow.

This is not satellite imagery. It only verifies CRS extraction, preview generation,
and map overlay alignment around the demo plot.
"""
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds


OUTPUT = Path(__file__).with_name("synthetic_imagery_demo.tif")
WIDTH = 640
HEIGHT = 480
BOUNDS = (100.2722, 14.4678, 100.2772, 14.4722)  # west, south, east, north


def main() -> None:
    rng = np.random.default_rng(42)
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH]

    # Agricultural-looking synthetic texture. Values are arbitrary RGB display data.
    red = 75 + 18 * np.sin(x / 31) + 10 * np.cos(y / 17)
    green = 105 + 28 * np.sin((x + y) / 43) + 16 * np.cos(y / 24)
    blue = 58 + 11 * np.cos(x / 29) + 8 * np.sin(y / 21)

    # Add rectangular field blocks and narrow irrigation lines.
    for row in range(0, HEIGHT, 80):
        for col in range(0, WIDTH, 110):
            adjustment = rng.integers(-15, 18)
            red[row : row + 72, col : col + 102] += adjustment
            green[row : row + 72, col : col + 102] += adjustment * 1.4
    green[:, 208:216] -= 48
    blue[:, 208:216] += 38
    green[302:310, :] -= 45
    blue[302:310, :] += 34

    noise = rng.normal(0, 4, size=(HEIGHT, WIDTH))
    rgb = np.stack([red + noise, green + noise, blue + noise])
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    profile = {
        "driver": "GTiff",
        "width": WIDTH,
        "height": HEIGHT,
        "count": 3,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": from_bounds(*BOUNDS, WIDTH, HEIGHT),
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
        "interleave": "pixel",
    }
    with rasterio.open(OUTPUT, "w", **profile) as dst:
        dst.write(rgb)
        dst.build_overviews([2, 4, 8], Resampling.average)
        dst.update_tags(ns="rio_overview", resampling="average")
        dst.update_tags(
            DESCRIPTION="Synthetic test raster; not satellite imagery",
            DEMO_CENTER="14.469728,100.274733",
        )
    print(OUTPUT)


if __name__ == "__main__":
    main()
