import requests
import json
from datetime import datetime

LAT = 14.469728
LON = 100.274733
# Bounding box ~ 0.02 deg x 0.02 deg (~2km x 2km)
DELTA = 0.015
BBOX = [LON - DELTA, LAT - DELTA, LON + DELTA, LAT + DELTA]
START_DATE = "2026-05-24T00:00:00Z"
END_DATE = "2026-07-24T23:59:59Z"

print(f"Target BBOX: {BBOX}")
print(f"Time window: {START_DATE} to {END_DATE}")

# 1. Try Planetary Computer STAC
pc_stac_url = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
headers = {"Content-Type": "application/json"}

# Query Sentinel-2
s2_payload = {
    "collections": ["sentinel-2-l2a"],
    "bbox": BBOX,
    "datetime": f"{START_DATE}/{END_DATE}",
    "limit": 100
}

try:
    r = requests.post(pc_stac_url, json=s2_payload, headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        items = data.get("features", [])
        print(f"\n[Planetary Computer] Sentinel-2 items found: {len(items)}")
        for item in items:
            dt = item["properties"].get("datetime")
            cloud = item["properties"].get("eo:cloud_cover", 0)
            print(f"  S2 Date: {dt} | Cloud cover: {cloud:.1f}% | ID: {item['id']}")
    else:
        print(f"Planetary Computer S2 Error {r.status_code}: {r.text}")
except Exception as e:
    print(f"Planetary Computer S2 Exception: {e}")

# Query Sentinel-1
s1_payload = {
    "collections": ["sentinel-1-grd", "sentinel-1-rtc"],
    "bbox": BBOX,
    "datetime": f"{START_DATE}/{END_DATE}",
    "limit": 100
}

try:
    r = requests.post(pc_stac_url, json=s1_payload, headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        items = data.get("features", [])
        print(f"\n[Planetary Computer] Sentinel-1 items found: {len(items)}")
        for item in items:
            dt = item["properties"].get("datetime")
            orbit = item["properties"].get("sat:orbit_state", "N/A")
            pol = item["properties"].get("sat:polarizations", [])
            print(f"  S1 Date: {dt} | Orbit: {orbit} | Pol: {pol} | ID: {item['id']}")
    else:
        print(f"Planetary Computer S1 Error {r.status_code}: {r.text}")
except Exception as e:
    print(f"Planetary Computer S1 Exception: {e}")

# Also test Earth Search (Element 84)
es_stac_url = "https://earth-search.aws.element84.com/v1/search"
try:
    r = requests.post(es_stac_url, json={"collections": ["sentinel-2-l2a", "sentinel-2-c1-l2a"], "bbox": BBOX, "datetime": f"{START_DATE}/{END_DATE}", "limit": 100}, headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        items = data.get("features", [])
        print(f"\n[Earth Search AWS] Sentinel-2 items found: {len(items)}")
        for item in items:
            dt = item["properties"].get("datetime")
            cloud = item["properties"].get("eo:cloud_cover", 0)
            print(f"  S2 Date: {dt} | Cloud: {cloud:.1f}% | ID: {item['id']}")
except Exception as e:
    print(f"Earth Search Exception: {e}")
