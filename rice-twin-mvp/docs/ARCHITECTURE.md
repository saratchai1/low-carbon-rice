# Architecture

## Runtime

```text
Browser (MapLibre + vanilla JS)
        │  HTTP / JSON
        ▼
FastAPI ─── /api legacy
        └── /api/v1 Ultimate platform
        │
        ├── Twin / AWD / quality / scenario services
        ├── Public-data adapter boundary
        ├── Raster preview and Sentinel catalogue
        └── Report renderers (HTML / JSON / CSV)
        │
        ▼
PostgreSQL + PostGIS
        │
        ├── projects / groups / farmers / plots / crop seasons
        ├── gateways / devices / channels / observations
        ├── public snapshots / imagery
        ├── twin states / rules / recommendations / decisions
        └── alerts / evidence / scenario runs / audit events
```

Docker Compose เปิด service `api` ที่ port 8000 และ `db` ภายใน network
ไฟล์ภาพจาก `../output` mount แบบ read-only ส่วน preview อยู่ใน `data/imagery`

## Design boundaries

- ทุก datetime เก็บเป็น UTC; UI แสดง Asia/Bangkok
- geometry ใช้ EPSG:4326 ที่ API และ PostGIS สำหรับ validation/query
- API v1 ตอบ envelope `{data, meta}` พร้อม request ID, demo flag และ warning
- provenance เป็น controlled vocabulary 6 ค่า
- scenario engine ใช้ seed และ tick จึงทำซ้ำได้
- role switcher เป็น demo UI ไม่ใช่ authentication
- field draft อยู่ใน localStorage; production ต้องใช้ encrypted offline store
- external public APIs เป็น adapter boundary; เดโมไม่พึ่ง availability ภายนอก

## Migration

`0003_ultimate_platform.sql` ขยาย schema แบบ idempotent และมี migration ledger
startup ทำ create/migrate/seed โดยข้อมูล seed ใช้ ID คงที่และไม่สร้างซ้ำ

## Production gaps

ต้องเพิ่ม OIDC/RBAC, tenant isolation, secret manager, message broker/time-series
pipeline, object storage/COG tiles, background jobs, rate limiting, monitoring,
backup/restore, data retention, e-signature และ methodology-governed calculation
ก่อนใช้กับการดำเนินงานหรือ MRV จริง
