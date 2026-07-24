from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds


@dataclass(frozen=True)
class RasterMetadata:
    crs: str
    bounds_wgs84: list[float]
    width: int
    height: int
    band_count: int
    render_bands: list[int]
    band_descriptions: list[str | None]


def _validate_bands(src: rasterio.io.DatasetReader, requested: list[int]) -> list[int]:
    if src.count < 1:
        raise ValueError("Raster has no readable bands")

    if src.count == 1:
        return [1, 1, 1]

    descriptions = {
        str(description).strip().upper(): index
        for index, description in enumerate(src.descriptions, start=1)
        if description
    }
    if not requested and {"B04", "B03", "B02"}.issubset(descriptions):
        return [descriptions["B04"], descriptions["B03"], descriptions["B02"]]

    if src.count == 2:
        defaults = [1, 2, 2]
    else:
        defaults = [1, 2, 3]

    bands = requested if len(requested) == 3 else defaults
    if any(index < 1 or index > src.count for index in bands):
        raise ValueError(
            f"Requested render bands {bands} are outside the raster band range 1..{src.count}"
        )
    return bands


def _stretch_to_byte(channel: np.ma.MaskedArray) -> np.ndarray:
    values = channel.compressed()
    if values.size == 0:
        return np.zeros(channel.shape, dtype=np.uint8)

    low, high = np.percentile(values.astype(np.float64), [2, 98])
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        low = float(np.nanmin(values))
        high = float(np.nanmax(values))
    if high <= low:
        return np.zeros(channel.shape, dtype=np.uint8)

    filled = channel.filled(low).astype(np.float64)
    scaled = np.clip((filled - low) / (high - low), 0, 1) * 255
    return scaled.astype(np.uint8)


def _colorize_index(channel: np.ma.MaskedArray, scheme: str) -> np.ndarray:
    values = channel.compressed().astype(np.float64)
    if values.size == 0:
        return np.zeros((*channel.shape, 3), dtype=np.uint8)
    low, high = np.percentile(values, [2, 98])
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        low, high = float(np.nanmin(values)), float(np.nanmax(values))
    if high <= low:
        high = low + 1
    normalized = np.clip((channel.filled(low).astype(np.float64) - low) / (high - low), 0, 1)
    stops = np.linspace(0, 1, 5)
    if scheme == "vegetation":
        palette = np.array([
            [116, 67, 42], [210, 166, 80], [238, 228, 145],
            [116, 177, 86], [20, 102, 53],
        ])
    else:
        palette = np.array([
            [125, 82, 55], [214, 178, 113], [217, 234, 225],
            [80, 176, 190], [22, 89, 150],
        ])
    return np.stack(
        [np.interp(normalized, stops, palette[:, channel_index]) for channel_index in range(3)],
        axis=-1,
    ).astype(np.uint8)


def create_preview(
    source_path: Path,
    preview_path: Path,
    requested_bands: list[int] | None = None,
    max_dimension: int = 1600,
    color_scheme: str | None = None,
) -> RasterMetadata:
    requested_bands = requested_bands or []

    with rasterio.open(source_path) as src:
        if src.crs is None:
            raise ValueError(
                "The image has no CRS. Upload a georeferenced GeoTIFF/COG or provide georeferencing first."
            )

        render_bands = _validate_bands(src, requested_bands)
        scale = min(1.0, max_dimension / max(src.width, src.height))
        out_width = max(1, int(round(src.width * scale)))
        out_height = max(1, int(round(src.height * scale)))

        channels: list[np.ma.MaskedArray] = []
        for band_index in render_bands:
            band = src.read(
                band_index,
                out_shape=(out_height, out_width),
                masked=True,
                resampling=Resampling.bilinear,
            )
            channels.append(band)

        mask = np.logical_or.reduce([np.ma.getmaskarray(channel) for channel in channels])
        rgb = (
            _colorize_index(channels[0], color_scheme)
            if color_scheme
            else np.stack([_stretch_to_byte(channel) for channel in channels], axis=-1)
        )
        alpha = np.where(mask, 0, 255).astype(np.uint8)
        rgba = np.dstack([rgb, alpha])

        preview_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgba, mode="RGBA").save(preview_path, format="PNG")

        west, south, east, north = transform_bounds(
            src.crs, "EPSG:4326", *src.bounds, densify_pts=21
        )
        return RasterMetadata(
            crs=src.crs.to_string(),
            bounds_wgs84=[west, south, east, north],
            width=src.width,
            height=src.height,
            band_count=src.count,
            render_bands=render_bands,
            band_descriptions=list(src.descriptions),
        )
