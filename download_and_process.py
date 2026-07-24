import os
import sys
import glob
import math
import json
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from datetime import datetime
import planetary_computer as pc
import warnings

# Suppress numpy / rasterio deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# Target Coordinates requested by user
TARGET_LAT = 14.469728
TARGET_LON = 100.274733

# Create ~2.2 km x 2.2 km bounding box (0.01 degree offset in lat/lon)
HALF_SIZE = 0.010
BBOX = [
    TARGET_LON - HALF_SIZE,
    TARGET_LAT - HALF_SIZE,
    TARGET_LON + HALF_SIZE,
    TARGET_LAT + HALF_SIZE
]

START_DATE = "2026-05-24T00:00:00Z"
END_DATE = "2026-07-24T23:59:59Z"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
S2_DIR = os.path.join(OUTPUT_DIR, "sentinel2")
S1_DIR = os.path.join(OUTPUT_DIR, "sentinel1")

os.makedirs(S2_DIR, exist_ok=True)
os.makedirs(S1_DIR, exist_ok=True)

print("="*70)
print("  SENTINEL-1 & SENTINEL-2 LOW CARBON RICE MONITORING PIPELINE")
print(f"  Target Point: Lat {TARGET_LAT}, Lon {TARGET_LON}")
print(f"  ROI Bounding Box (EPSG:4326): {BBOX}")
print(f"  Date Range: {START_DATE[:10]} to {END_DATE[:10]}")
print("="*70)

# Helper function to read windowed COG raster directly from signed STAC asset URL
def fetch_raster_window(asset_url, bbox_4326, target_shape=None):
    try:
        with rasterio.open(asset_url) as src:
            src_crs = src.crs
            minx, miny, maxx, maxy = transform_bounds("EPSG:4326", src_crs, bbox_4326[0], bbox_4326[1], bbox_4326[2], bbox_4326[3])
            window = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
            
            if target_shape is not None:
                data = src.read(1, window=window, out_shape=target_shape, resampling=Resampling.bilinear)
            else:
                data = src.read(1, window=window)
                
            win_transform = rasterio.windows.transform(window, src.transform)
            return data, win_transform, src_crs
    except Exception as e:
        print(f"    Error reading COG window: {e}")
        return None, None, None

# Helper to save single band GeoTIFF raster
def save_geotiff(filename, data, transform_matrix, crs):
    height, width = data.shape
    dtype = data.dtype
    nodata_val = np.nan if np.issubdtype(dtype, np.floating) else 0
    with rasterio.open(
        filename,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=dtype,
        crs=crs,
        transform=transform_matrix,
        nodata=nodata_val
    ) as dst:
        dst.write(data, 1)

# Helper to save multiband GeoTIFF raster
def save_multiband_geotiff(filename, bands_dict, transform_matrix, crs):
    band_names = list(bands_dict.keys())
    first_band = bands_dict[band_names[0]]
    height, width = first_band.shape
    count = len(band_names)
    
    with rasterio.open(
        filename,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=count,
        dtype='float32',
        crs=crs,
        transform=transform_matrix,
        nodata=np.nan
    ) as dst:
        for idx, name in enumerate(band_names, start=1):
            dst.write(bands_dict[name].astype('float32'), idx)
            dst.set_band_description(idx, name)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
headers = {"Content-Type": "application/json"}

# -------------------------------------------------------------
# 1. PROCESS SENTINEL-2 (OPTICAL MULTISPECTRAL)
# -------------------------------------------------------------
print("\n[1/3] Querying & Downloading Sentinel-2 Optical Data...")
s2_payload = {
    "collections": ["sentinel-2-l2a"],
    "bbox": BBOX,
    "datetime": f"{START_DATE}/{END_DATE}",
    "limit": 100
}

r = requests.post(STAC_URL, json=s2_payload, headers=headers)
s2_items = r.json().get("features", []) if r.status_code == 200 else []
print(f"Total Sentinel-2 scenes found: {len(s2_items)}")

# Select best scene per acquisition date (lowest cloud cover)
s2_by_date = {}
for item in s2_items:
    dt_str = item["properties"]["datetime"][:10]
    cloud = item["properties"].get("eo:cloud_cover", 100.0)
    if dt_str not in s2_by_date or cloud < s2_by_date[dt_str]["cloud"]:
        s2_by_date[dt_str] = {"item": item, "cloud": cloud}

print(f"Unique acquisition dates for Sentinel-2: {len(s2_by_date)} days")

inventory_records = []

for dt_str, info in sorted(s2_by_date.items()):
    raw_item = info["item"]
    cloud_cover = info["cloud"]
    scene_id = raw_item["id"]
    
    print(f"\nProcessing Sentinel-2 | Date: {dt_str} | Cloud: {cloud_cover:.1f}% | Tile ID: {scene_id[:35]}...")
    
    # Sign item using Planetary Computer SDK
    item = pc.sign(raw_item)
    assets = item["assets"]
    
    date_dir = os.path.join(S2_DIR, f"{dt_str}_{scene_id[:25]}")
    os.makedirs(date_dir, exist_ok=True)
    
    bands_data = {}
    trans, crs = None, None
    target_shape = None
    
    # First load 10m bands (B02, B03, B04, B08) to establish reference spatial grid
    for b_name in ["B02", "B03", "B04", "B08"]:
        if b_name in assets:
            url = assets[b_name]["href"]
            arr, tr, c = fetch_raster_window(url, BBOX)
            if arr is not None:
                bands_data[b_name] = arr.astype(np.float32) / 10000.0
                if target_shape is None:
                    target_shape = arr.shape
                    trans = tr
                    crs = c
                    
    # Now load 20m SWIR bands (B11, B12) resampled to 10m grid
    for b_name in ["B11", "B12"]:
        if b_name in assets and target_shape is not None:
            url = assets[b_name]["href"]
            arr, tr, c = fetch_raster_window(url, BBOX, target_shape=target_shape)
            if arr is not None:
                bands_data[b_name] = arr.astype(np.float32) / 10000.0

    if "B04" in bands_data and "B08" in bands_data and "B11" in bands_data:
        red = bands_data["B04"]
        green = bands_data["B03"]
        blue = bands_data["B02"]
        nir = bands_data["B08"]
        swir1 = bands_data["B11"]
        swir2 = bands_data["B12"]
        
        # Calculate Rice Monitoring Spectral Indices
        # 1. NDVI = (NIR - Red) / (NIR + Red)
        denom_ndvi = (nir + red)
        denom_ndvi[denom_ndvi == 0] = np.nan
        ndvi = np.clip((nir - red) / denom_ndvi, -1.0, 1.0)
        
        # 2. LSWI = (NIR - SWIR1) / (NIR + SWIR1) -> Critical indicator for soil moisture & AWD (Alternate Wetting and Drying)
        denom_lswi = (nir + swir1)
        denom_lswi[denom_lswi == 0] = np.nan
        lswi = np.clip((nir - swir1) / denom_lswi, -1.0, 1.0)
        
        # 3. NDWI = (Green - NIR) / (Green + NIR) -> Surface water indicator
        denom_ndwi = (green + nir)
        denom_ndwi[denom_ndwi == 0] = np.nan
        ndwi = np.clip((green - nir) / denom_ndwi, -1.0, 1.0)

        # 4. EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
        denom_evi = (nir + 6.0 * red - 7.5 * blue + 1.0)
        denom_evi[denom_evi == 0] = np.nan
        evi = np.clip(2.5 * (nir - red) / denom_evi, -1.0, 1.5)
        
        bands_data["NDVI"] = ndvi
        bands_data["LSWI"] = lswi
        bands_data["NDWI"] = ndwi
        bands_data["EVI"] = evi
        
        # Export Rasters
        save_multiband_geotiff(os.path.join(date_dir, "sentinel2_rice_bands.tif"), bands_data, trans, crs)
        save_geotiff(os.path.join(date_dir, "NDVI.tif"), ndvi, trans, crs)
        save_geotiff(os.path.join(date_dir, "LSWI.tif"), lswi, trans, crs)
        save_geotiff(os.path.join(date_dir, "NDWI.tif"), ndwi, trans, crs)
        save_geotiff(os.path.join(date_dir, "B02_Blue.tif"), blue, trans, crs)
        save_geotiff(os.path.join(date_dir, "B03_Green.tif"), green, trans, crs)
        save_geotiff(os.path.join(date_dir, "B04_Red.tif"), red, trans, crs)
        save_geotiff(os.path.join(date_dir, "B08_NIR.tif"), nir, trans, crs)
        save_geotiff(os.path.join(date_dir, "B11_SWIR1.tif"), swir1, trans, crs)
        save_geotiff(os.path.join(date_dir, "B12_SWIR2.tif"), swir2, trans, crs)
        
        # Statistics over ROI
        mean_ndvi = float(np.nanmean(ndvi))
        mean_lswi = float(np.nanmean(lswi))
        mean_ndwi = float(np.nanmean(ndwi))
        mean_evi = float(np.nanmean(evi))
        
        # Render Composite PNG Visualizations
        rgb = np.clip(np.stack([red, green, blue], axis=-1) * 3.5, 0, 1)
        fc_nir = np.clip(np.stack([nir, red, green], axis=-1) * 3.0, 0, 1)
        swir_comp = np.clip(np.stack([swir1, nir, red], axis=-1) * 3.0, 0, 1)
        
        fig, axes = plt.subplots(2, 3, figsize=(16, 10))
        fig.suptitle(f"Sentinel-2 Rice Monitoring | Date: {dt_str} | Cloud: {cloud_cover:.1f}%\nTarget ROI: {TARGET_LAT}, {TARGET_LON}", fontsize=14, fontweight='bold')
        
        axes[0, 0].imshow(rgb)
        axes[0, 0].set_title("True Color RGB (B4-B3-B2)")
        axes[0, 0].axis('off')
        
        axes[0, 1].imshow(fc_nir)
        axes[0, 1].set_title("False Color NIR (B8-B4-B3)")
        axes[0, 1].axis('off')
        
        axes[0, 2].imshow(swir_comp)
        axes[0, 2].set_title("SWIR Moisture (B11-B8-B4)")
        axes[0, 2].axis('off')
        
        im_ndvi = axes[1, 0].imshow(ndvi, vmin=-0.1, vmax=0.9, cmap='YlGn')
        axes[1, 0].set_title(f"NDVI Crop Growth (Mean: {mean_ndvi:.3f})")
        axes[1, 0].axis('off')
        plt.colorbar(im_ndvi, ax=axes[1, 0], fraction=0.046, pad=0.04)
        
        im_lswi = axes[1, 1].imshow(lswi, vmin=-0.3, vmax=0.7, cmap='Blues')
        axes[1, 1].set_title(f"LSWI Soil/Canopy Water (Mean: {mean_lswi:.3f})")
        axes[1, 1].axis('off')
        plt.colorbar(im_lswi, ax=axes[1, 1], fraction=0.046, pad=0.04)
        
        im_ndwi = axes[1, 2].imshow(ndwi, vmin=-0.5, vmax=0.5, cmap='BrBG')
        axes[1, 2].set_title(f"NDWI Water Index (Mean: {mean_ndwi:.3f})")
        axes[1, 2].axis('off')
        plt.colorbar(im_ndwi, ax=axes[1, 2], fraction=0.046, pad=0.04)
        
        plt.tight_layout()
        preview_png = os.path.join(date_dir, "preview_summary.png")
        plt.savefig(preview_png, dpi=150, bbox_inches='tight')
        plt.close()
        
        inventory_records.append({
            "date": dt_str,
            "datetime": raw_item["properties"]["datetime"],
            "satellite": "Sentinel-2",
            "type": "Optical Multispectral",
            "scene_id": scene_id,
            "cloud_cover_%": cloud_cover,
            "mean_ndvi": mean_ndvi,
            "mean_lswi": mean_lswi,
            "mean_ndwi": mean_ndwi,
            "mean_evi": mean_evi,
            "mean_vv_dB": np.nan,
            "mean_vh_dB": np.nan,
            "output_dir": date_dir
        })
        print(f"  ✓ Saved Sentinel-2 rasters & preview for {dt_str} (NDVI: {mean_ndvi:.3f}, LSWI: {mean_lswi:.3f})")

# -------------------------------------------------------------
# 2. PROCESS SENTINEL-1 (RADAR SAR - C-BAND)
# -------------------------------------------------------------
print("\n[2/3] Querying & Downloading Sentinel-1 Radar SAR Data...")
s1_payload = {
    "collections": ["sentinel-1-rtc", "sentinel-1-grd"],
    "bbox": BBOX,
    "datetime": f"{START_DATE}/{END_DATE}",
    "limit": 100
}

r = requests.post(STAC_URL, json=s1_payload, headers=headers)
s1_items = r.json().get("features", []) if r.status_code == 200 else []
print(f"Total Sentinel-1 scenes found: {len(s1_items)}")

# Group S1 scenes by acquisition date
s1_by_date = {}
for item in s1_items:
    dt_str = item["properties"]["datetime"][:10]
    coll = item.get("collection", "")
    if dt_str not in s1_by_date or coll == "sentinel-1-rtc":
        s1_by_date[dt_str] = item

print(f"Unique acquisition dates for Sentinel-1: {len(s1_by_date)} days")

for dt_str, raw_item in sorted(s1_by_date.items()):
    scene_id = raw_item["id"]
    orbit = raw_item["properties"].get("sat:orbit_state", "N/A")
    print(f"\nProcessing Sentinel-1 | Date: {dt_str} | Orbit: {orbit.capitalize()} | ID: {scene_id[:35]}...")
    
    # Sign item using Planetary Computer SDK
    item = pc.sign(raw_item)
    assets = item["assets"]
    
    date_dir = os.path.join(S1_DIR, f"{dt_str}_{scene_id[:25]}")
    os.makedirs(date_dir, exist_ok=True)
    
    vv_arr, vh_arr = None, None
    trans, crs = None, None
    
    for vv_key in ["vv", "VV"]:
        if vv_key in assets:
            url = assets[vv_key]["href"]
            vv_arr, tr, c = fetch_raster_window(url, BBOX)
            if vv_arr is not None:
                trans, crs = tr, c
                break
                
    for vh_key in ["vh", "VH"]:
        if vh_key in assets:
            url = assets[vh_key]["href"]
            # match shape of VV if available
            target_shp = vv_arr.shape if vv_arr is not None else None
            vh_arr, tr, c = fetch_raster_window(url, BBOX, target_shape=target_shp)
            if vh_arr is not None:
                if trans is None:
                    trans, crs = tr, c
                break
                
    if vv_arr is not None and vh_arr is not None:
        # Check scale: Convert linear power scale to decibels (dB) if needed
        if np.nanmean(vv_arr) > 0 and np.nanmax(vv_arr) < 50:
            vv_db = 10.0 * np.log10(np.clip(vv_arr, 1e-4, None))
            vh_db = 10.0 * np.log10(np.clip(vh_arr, 1e-4, None))
        else:
            vv_db = vv_arr.astype(np.float32)
            vh_db = vh_arr.astype(np.float32)
            
        vh_vv_diff = vh_db - vv_db # Difference in dB scale = log ratio (crop canopy proxy)
        
        # Save GeoTIFFs
        save_geotiff(os.path.join(date_dir, "VV_dB.tif"), vv_db, trans, crs)
        save_geotiff(os.path.join(date_dir, "VH_dB.tif"), vh_db, trans, crs)
        save_geotiff(os.path.join(date_dir, "VH_VV_diff_dB.tif"), vh_vv_diff, trans, crs)
        
        mean_vv = float(np.nanmean(vv_db))
        mean_vh = float(np.nanmean(vh_db))
        
        # SAR RGB False Color Composite (R: VV, G: VH, B: VH-VV)
        r_norm = np.clip((vv_db + 20) / 20, 0, 1)
        g_norm = np.clip((vh_db + 25) / 20, 0, 1)
        b_norm = np.clip((vh_vv_diff + 10) / 15, 0, 1)
        sar_rgb = np.stack([r_norm, g_norm, b_norm], axis=-1)
        
        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        fig.suptitle(f"Sentinel-1 SAR Radar Rice Monitoring | Date: {dt_str} | Orbit: {orbit.capitalize()}\nCloud-Free Microwave Sensing", fontsize=14, fontweight='bold')
        
        im0 = axes[0].imshow(vv_db, vmin=-25, vmax=0, cmap='gray')
        axes[0].set_title(f"VV Backscatter (Surface Water/Roughness)\nMean: {mean_vv:.2f} dB")
        axes[0].axis('off')
        plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
        
        im1 = axes[1].imshow(vh_db, vmin=-30, vmax=-5, cmap='magma')
        axes[1].set_title(f"VH Backscatter (Canopy Volume/Height)\nMean: {mean_vh:.2f} dB")
        axes[1].axis('off')
        plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
        
        axes[2].imshow(sar_rgb)
        axes[2].set_title("SAR False Color RGB\n(Red:VV, Green:VH, Blue:VH/VV)")
        axes[2].axis('off')
        
        plt.tight_layout()
        preview_png = os.path.join(date_dir, "preview_sar_summary.png")
        plt.savefig(preview_png, dpi=150, bbox_inches='tight')
        plt.close()
        
        inventory_records.append({
            "date": dt_str,
            "datetime": raw_item["properties"]["datetime"],
            "satellite": "Sentinel-1",
            "type": "Radar SAR (C-band)",
            "scene_id": scene_id,
            "cloud_cover_%": 0.0, # Cloud penetrating
            "mean_ndvi": np.nan,
            "mean_lswi": np.nan,
            "mean_ndwi": np.nan,
            "mean_evi": np.nan,
            "mean_vv_dB": mean_vv,
            "mean_vh_dB": mean_vh,
            "output_dir": date_dir
        })
        print(f"  ✓ Saved Sentinel-1 rasters & preview for {dt_str} (VV: {mean_vv:.2f} dB, VH: {mean_vh:.2f} dB)")

# -------------------------------------------------------------
# 3. EXPORT METADATA & TIMELINE CHARTS
# -------------------------------------------------------------
print("\n[3/3] Exporting Summary Inventory & Time Series Analysis...")
df_inventory = pd.DataFrame(inventory_records)
if not df_inventory.empty:
    df_inventory.sort_values(by="datetime", inplace=True)
    csv_path = os.path.join(OUTPUT_DIR, "summary_inventory.csv")
    json_path = os.path.join(OUTPUT_DIR, "summary_inventory.json")
    
    df_inventory.to_csv(csv_path, index=False)
    df_inventory.to_json(json_path, orient="records", indent=2)
    print(f"✓ Saved inventory summary table to: {csv_path}")

    # Generate Time Series Chart
    fig, ax1 = plt.subplots(figsize=(13, 6))
    
    df_s2 = df_inventory[df_inventory["satellite"] == "Sentinel-2"].copy()
    if not df_s2.empty:
        df_s2["dt"] = pd.to_datetime(df_s2["datetime"])
        # Filter reasonably clear optical (< 60% cloud) for index trendline
        df_s2_clear = df_s2[df_s2["cloud_cover_%"] < 60.0]
        if not df_s2_clear.empty:
            ax1.plot(df_s2_clear["dt"], df_s2_clear["mean_ndvi"], 'o-', color="forestgreen", linewidth=2, label="NDVI (Crop Canopy Growth)")
            ax1.plot(df_s2_clear["dt"], df_s2_clear["mean_lswi"], 's--', color="dodgerblue", linewidth=2, label="LSWI (Soil/Canopy Water - AWD Indicator)")
            ax1.plot(df_s2_clear["dt"], df_s2_clear["mean_ndwi"], 'd:', color="teal", linewidth=1.5, label="NDWI (Surface Water)")
            
    ax1.set_xlabel("Acquisition Date", fontweight='bold', fontsize=11)
    ax1.set_ylabel("Optical Spectral Indices (-1.0 to 1.0)", color="darkgreen", fontweight='bold', fontsize=11)
    ax1.tick_params(axis='y', labelcolor="darkgreen")
    ax1.grid(True, linestyle="--", alpha=0.5)
    
    ax2 = ax1.twinx()
    df_s1 = df_inventory[df_inventory["satellite"] == "Sentinel-1"].copy()
    if not df_s1.empty:
        df_s1["dt"] = pd.to_datetime(df_s1["datetime"])
        ax2.plot(df_s1["dt"], df_s1["mean_vh_dB"], '^-.', color="purple", linewidth=2, label="Sentinel-1 VH Backscatter (dB)")
        ax2.plot(df_s1["dt"], df_s1["mean_vv_dB"], 'v:', color="gray", linewidth=1.5, label="Sentinel-1 VV Backscatter (dB)")
        
    ax2.set_ylabel("Radar SAR Backscatter Intensity (dB)", color="purple", fontweight='bold', fontsize=11)
    ax2.tick_params(axis='y', labelcolor="purple")
    
    plt.title(f"Low Carbon Rice Monitoring: Optical & Radar Time Series (May - July 2026)\nLocation: Lat {TARGET_LAT}, Lon {TARGET_LON}", fontsize=13, fontweight='bold')
    
    # Combine legend handles
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    
    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "time_series_summary.png")
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"✓ Saved time series chart to: {plot_path}")

print("\n" + "="*70)
print("  ALL SENTINEL-1 & SENTINEL-2 IMAGERY RETRIEVED AND PROCESSED!")
print("="*70)
