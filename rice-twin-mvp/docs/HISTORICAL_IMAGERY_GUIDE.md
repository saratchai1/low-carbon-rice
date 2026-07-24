# Historical Imagery Guide

## เปิดใช้งาน

คลังต้นฉบับถูก mount แบบ read-only จาก:

```text
../output_3yr_4per_month/
├── sentinel2/
└── sentinel1/
```

เริ่มระบบด้วย:

```bash
docker compose up --build
```

หน้าใช้งาน:

- Historical Baseline Explorer: `http://localhost:8000/historical`
- Executive presentation: `http://localhost:8000/presentation`
- OpenAPI: `http://localhost:8000/docs`

ระบบนำเข้าแบบ idempotent ตอน startup หรือเรียก:

```bash
curl -X POST http://localhost:8000/api/v1/imagery/bulk-import \
  -H 'Content-Type: application/json' \
  -d '{"force_analysis": false}'
```

ไฟล์ต้นฉบับไม่ถูกแก้ไขหรือย้าย ระบบบันทึก path, SHA‑256, metadata,
quality และผลวิเคราะห์ลงฐานข้อมูล

## โครงสร้าง scene ที่รองรับใน archive นี้

Sentinel‑2:

```text
YYYY-MM-DD_.../
├── sentinel2_rice_bands.tif
├── NDVI.tif
├── LSWI.tif
├── NDWI.tif
└── preview_summary.png
```

Band mapping ของ `sentinel2_rice_bands.tif` ต้องเป็น
`B02, B03, B04, B08, B11, B12, NDVI, LSWI, NDWI, EVI`
ตามลำดับ 1–10 ระบบไม่เดาลำดับ band

Sentinel‑1:

```text
YYYY-MM-DD_.../
├── VV_dB.tif
├── VH_dB.tif
├── VH_VV_diff_dB.tif
└── preview_sar_summary.png
```

## ผลตรวจ archive ปัจจุบัน

- Sentinel‑2: 142 scene; 91 scene ครอบคลุมแปลงเต็มและ 51 scene เป็น
  `WARNING` เพราะครอบคลุมแปลงประมาณ 27.38%
- Sentinel‑1: 122 scene สมบูรณ์
- Sentinel‑1 ที่ไม่สมบูรณ์: `2023-10-18...` และ `2026-02-16...`
  ถูกบันทึกเป็น `FAILED` พร้อมรายชื่อไฟล์ที่ขาด
- Scene ที่คำนวณ metric: 264
- Scene ที่ผ่านเกณฑ์ usable เต็มแปลง: 213

## สถานะ

`UPLOADED`, `VALIDATING`, `VALID`, `PROCESSING`, `READY`, `WARNING`,
`FAILED`, `ARCHIVED`

ระบบไม่ข้ามข้อผิดพลาดเงียบ: missing file, CRS, geotransform,
outside/partial coverage และ duplicate SHA‑256 มีสถานะและเหตุผลกำกับ

## รูปแบบอื่น

หน้า upload รุ่นเดิมรองรับ GeoTIFF/COG ที่มี georeferencing.
PNG/JPEG จำเป็นต้องมี bounds หรือ world file ก่อนจึงจะเป็น imagery asset
ที่มีตำแหน่งได้; archive importer รุ่นนี้ไม่เดาพิกัดจากรูปภาพธรรมดา

ใช้ [IMAGERY_IMPORT_TEMPLATE.csv](IMAGERY_IMPORT_TEMPLATE.csv) เมื่อต้อง
เตรียม manifest สำหรับชุดข้อมูลเพิ่มเติม

## API หลัก

```text
POST /api/v1/imagery/bulk-import
GET  /api/v1/imagery
GET  /api/v1/imagery/{image_id}
POST /api/v1/imagery/{image_id}/process
GET  /api/v1/imagery/{image_id}/metrics
GET  /api/v1/imagery/{image_id}/preview.png
GET  /api/v1/plots/{plot_id}/imagery-timeline
POST /api/v1/plots/{plot_id}/temporal-analysis
GET  /api/v1/plots/{plot_id}/crop-cycles
GET  /api/v1/plots/{plot_id}/historical-baseline
GET  /api/v1/plots/{plot_id}/recurring-zones
GET  /api/v1/plots/{plot_id}/baseline-evidence
POST /api/v1/plots/{plot_id}/sensor-location-analysis
GET  /api/v1/plots/{plot_id}/sensor-location-proposals
GET  /api/v1/analysis-runs/{run_id}
GET  /api/v1/algorithm-versions
```

## Export

```text
/api/v1/plots/DEMO-PLOT-001/exports/timeline.csv
/api/v1/plots/DEMO-PLOT-001/exports/historical-baseline.json
/api/v1/plots/DEMO-PLOT-001/exports/recurring-zones.geojson
/api/v1/plots/DEMO-PLOT-001/exports/sensor-proposals.geojson
/api/v1/plots/DEMO-PLOT-001/exports/executive-report.html
```

ทุก export มี plot ID, period, image count, source, algorithm version,
processing date, provenance, confidence, limitations และ synthetic-boundary
warning
