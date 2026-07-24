# Ultimate Low-Carbon Rice Digital Twin

แพลตฟอร์มสาธิตระดับ executive ที่เชื่อม Digital Twin, IoT, AWD decision support,
public-data adapters, Sentinel imagery, field evidence และ Carbon MRV readiness
บน FastAPI + PostgreSQL/PostGIS + MapLibre

> **DEMO-PLOT-001 is a synthetic demonstration boundary. It is not a cadastral,
> surveyed, legal, ownership, or officially verified plot boundary.**

หน้าใช้งานหลักอยู่ที่ `http://localhost:8000` และโหมดนำเสนออยู่ที่
`http://localhost:8000/presentation` ส่วน UI รุ่นก่อนยังเปิดได้ที่ `/legacy`

ระบบสร้างข้อมูลสาธิตแบบ deterministic จำนวน 1 แปลงหลัก + 5 แปลงใกล้เคียง,
อุปกรณ์ 12 ตัว, observations 30 วัน, public snapshots, evidence, alerts และ
สถานการณ์ end-to-end 10 แบบ ค่าทุกกลุ่มติดป้าย `LIVE`, `SIMULATED`, `PUBLIC`,
`MANUAL`, `DERIVED` หรือ `REFERENCE`

## คู่มือเวอร์ชัน Ultimate

- [Executive Demo Guide](docs/EXECUTIVE_DEMO_GUIDE.md)
- [IoT Integration Guide](docs/IOT_INTEGRATION_GUIDE.md)
- [Public Data Adapter Guide](docs/PUBLIC_DATA_ADAPTER_GUIDE.md)
- [Satellite Imagery Guide](docs/SATELLITE_IMAGERY_GUIDE.md)
- [Carbon MRV Limitations](docs/CARBON_MRV_LIMITATIONS.md)
- [Architecture](docs/ARCHITECTURE.md)

## เริ่มระบบ

```bash
docker compose up --build
```

ตรวจสุขภาพและรันชุดทดสอบ:

```bash
curl http://localhost:8000/api/health
docker compose exec api pytest -q
```

API รุ่น Ultimate ใช้ prefix `/api/v1` และ Swagger อยู่ที่ `/docs`

---

# Rice Twin MVP (บันทึกความสามารถรุ่นเดิม)

ต้นแบบ Digital Twin สำหรับแปลงข้าวคาร์บอนต่ำ โดยเน้นสถานะน้ำแบบ AWD, บันทึกกิจกรรม, evidence timeline และการซ้อนภาพ GeoTIFF บนแผนที่

## สิ่งที่มีในต้นแบบ

- แผนที่ MapLibre พร้อมภาพถ่ายดาวเทียม Esri เป็นพื้นหลังเริ่มต้น และ dropdown สลับแผนที่ถนน OSM
- MapLibre GL JS ถูกเก็บและเสิร์ฟจากตัวโครงการ ไม่ต้องโหลด JavaScript/CSS จาก CDN
- จุดกึ่งกลาง `14.469728, 100.274733`
- ขอบเขตสมมติประมาณ 240 × 160 เมตร หรือประมาณ 24 ไร่
- Plot Digital Twin: ระยะข้าว ระดับน้ำ รอบ AWD จำนวนวันแห้ง คำแนะนำ และ data confidence
- บันทึกกิจกรรมภาคสนามและกราฟระดับน้ำ
- PostgreSQL + PostGIS
- อัปโหลด GeoTIFF/COG ที่มี CRS
- สร้าง PNG preview จาก raster และซ้อนตาม bounds ของไฟล์
- เลือก RGB band และปรับความทึบของภาพ
- Swagger API ที่ `/docs`
- ไฟล์ GeoTIFF สังเคราะห์สำหรับทดสอบก่อนมีภาพจริง
- crop season ที่เชื่อมกับทุกกิจกรรม
- กฎ AWD สาธิตแบบมีเวอร์ชันและเก็บผลการประเมิน
- คะแนน data quality ที่แสดงองค์ประกอบทุกข้อ
- SHA-256, processing status และการตรวจ footprint ตัดกับแปลง
- Carbon MRV panel ที่หยุดการคำนวณจนกว่าจะตั้ง methodology
- append-only audit events สำหรับการสร้างและแก้ไขข้อมูล
- นำเข้าคลัง Sentinel-1/Sentinel-2 จาก `../output` อัตโนมัติแบบ read-only

> ขอบเขตแปลงในโครงการนี้สร้างขึ้นเพื่อสาธิตเท่านั้น ไม่ใช่แนวเขตสำรวจ แนวเขตโฉนด หรือขอบเขตแปลงจริง

## เริ่มใช้งาน

ต้องมี Docker และ Docker Compose

```bash
cd rice-twin-mvp
docker compose up --build
```

เมื่อเริ่มระบบครั้งแรก API จะอ่าน `../output/summary_inventory.json` และ catalog ภาพดังนี้:

- Sentinel-2 ใช้ `sentinel2_rice_bands.tif` และแสดง true colour ด้วย band `3/2/1`
- Sentinel-1 ใช้ `VV_dB.tif` เป็น grayscale
- ไฟล์ต้นฉบับไม่ถูกแก้ไขหรือคัดลอก ระบบเก็บเฉพาะ preview ใน `data/imagery`
- การนำเข้าเป็น idempotent โดยใช้ SHA-256 จึงไม่สร้างรายการซ้ำเมื่อ restart

เปิดเว็บที่:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

รันชุดทดสอบภายใน container:

```bash
docker compose exec api python -m pytest -q
```

หยุดระบบ:

```bash
docker compose down
```

ล้างฐานข้อมูลสาธิตแล้วเริ่มใหม่:

```bash
docker compose down -v
docker compose up --build
```

## ทดสอบการอัปโหลดภาพ

ใช้ไฟล์นี้ในแท็บ “ภาพดาวเทียม”:

```text
sample/synthetic_imagery_demo.tif
```

ไฟล์ดังกล่าวเป็น raster สังเคราะห์ที่มี CRS `EPSG:4326` ไม่ใช่ภาพดาวเทียมจริง มีไว้ตรวจสอบขั้นตอน upload → raster preview → map overlay เท่านั้น

หน้าอัปโหลดใช้โหมดอัตโนมัติเป็นค่าเริ่มต้น:

1. เลือกไฟล์ GeoTIFF
2. ระบบอ่านวันที่จากชื่อไฟล์รูปแบบ `YYYY-MM-DD` หรือ `YYYYMMDD` เมื่อมี
3. ระบบอ่านชื่อ band จาก GeoTIFF; ถ้าพบ `B04/B03/B02` จะเลือกสีธรรมชาติ `3/2/1`
4. ไฟล์ band เดียวจะแสดงเป็น grayscale
5. กด “เพิ่มภาพลงบนแผนที่”

ผู้ใช้ทั่วไปไม่ต้องกรอกวันที่หรือหมายเลข band ส่วนการแก้วันที่, เลือก preset และกำหนด band เองอยู่ใน “ตัวเลือกขั้นสูง”

ภาพ Sentinel ในระบบเลือกผ่าน dropdown สองช่อง:

- วันที่และดาวเทียม
- มุมมองสำหรับนาข้าว

Sentinel-2 มีสีธรรมชาติ, สีเท็จพืชพรรณ, NDVI, EVI, LSWI และ NDWI ส่วน Sentinel-1 มี VV, VH และ VH−VV ระบบใช้สีเขียวสำหรับดัชนีพืช และสีน้ำเงินสำหรับดัชนีน้ำ/ความชื้น ค่าทั้งหมดเป็นหลักฐานช่วยตีความ ต้องอ่านร่วมกับข้อมูลภาคสนามและไม่ใช่การจำแนกแปลงข้าวหรือการรับรอง AWD โดยอัตโนมัติ

## ข้อกำหนดของภาพจริง

MVP รับ `.tif` หรือ `.tiff` โดยไฟล์ควรมี:

- CRS ฝังอยู่ในไฟล์
- affine transform หรือ geotransform
- ค่า NoData ถ้ามีพื้นที่โปร่งใส
- band ที่ต้องการแสดงผลระบุได้เป็น Red/Green/Blue
- วันเวลาถ่ายภาพเป็น metadata เพิ่มเติมได้

GeoJSON และ MapLibre ใช้ลำดับพิกัด `[longitude, latitude]` ดังนั้นจุดกลางในโค้ดคือ:

```json
[100.274733, 14.469728]
```

กรณีเป็น PNG หรือ JPEG ระบบไม่สามารถรู้ตำแหน่งจากภาพเพียงอย่างเดียว ต้องมีอย่างใดอย่างหนึ่งเพิ่มเติม:

- bounding box: west, south, east, north
- พิกัดมุมทั้งสี่
- world file
- GeoJSON footprint

## Band selection

ค่าเริ่มต้นคือ `1 / 2 / 3` หมายถึงเอา band 1 เป็นแดง, band 2 เป็นเขียว และ band 3 เป็นน้ำเงิน ไม่ได้หมายความว่าจะถูกต้องกับทุกผลิตภัณฑ์ดาวเทียม ต้องดู metadata ของไฟล์จริงก่อนเลือก

ระบบทำ percentile stretch ที่ 2–98% เพื่อสร้าง preview สำหรับแสดงผล แต่ไม่แก้ไขไฟล์ต้นฉบับ

## API หลัก

```text
GET    /api/health
GET    /api/config
GET    /api/plots
POST   /api/plots
GET    /api/plots/{plot_id}
PATCH  /api/plots/{plot_id}
GET    /api/plots/{plot_id}/activities
POST   /api/plots/{plot_id}/activities
GET    /api/plots/{plot_id}/crop-seasons
POST   /api/plots/{plot_id}/evaluate
GET    /api/plots/{plot_id}/alerts
GET    /api/plots/{plot_id}/data-quality
GET    /api/plots/{plot_id}/carbon
GET    /api/imagery?plot_id=DEMO-PLOT-001
POST   /api/imagery
GET    /api/imagery/{imagery_id}
GET    /api/imagery/{imagery_id}/preview.png
GET    /api/audit-events
```

ตัวอย่างบันทึกระดับน้ำ:

```bash
curl -X POST http://localhost:8000/api/plots/DEMO-PLOT-001/activities \
  -H 'Content-Type: application/json' \
  -d '{
    "activity_type": "วัดระดับน้ำ",
    "occurred_at": "2026-07-24T10:00:00+07:00",
    "note": "อ่านค่าจากท่อวัดระดับน้ำ",
    "water_level_cm": -10.5,
    "source": "field_app",
    "evidence": {"photo_id": "PHOTO-001"}
  }'
```

## โครงสร้างโครงการ

```text
rice-twin-mvp/
├── CODEX_PROMPT.md
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── models.py
│       ├── seed.py
│       ├── services/raster.py
│       └── static/
│           ├── index.html
│           ├── app.js
│           └── styles.css
├── data/imagery/
└── sample/
    ├── demo_plot.geojson
    ├── imagery-manifest.example.json
    ├── create_demo_geotiff.py
    └── synthetic_imagery_demo.tif
```

## ข้อจำกัดของ MVP

- ยังไม่มี authentication และ role-based access control
- ยังไม่มี mobile offline sync
- ยังไม่เชื่อมเซนเซอร์หรือสถานีอากาศจริง
- preview แบบ image overlay เหมาะกับ raster ขนาดเล็กถึงกลาง; production ควรใช้ COG tile service เช่น TiTiler
- มี data model/status สำหรับ Carbon MRV แต่ยังไม่มี methodology หรือ emission factor ที่อนุมัติ จึงไม่คำนวณก๊าซเรือนกระจก
- กฎ AWD รุ่น `demo-1.0` และ data confidence เป็นตรรกะสาธิต ไม่ใช่คำแนะนำสากลหรือผลการตรวจรับรอง
- ไม่มีการออก ซื้อขาย หรือรับรอง carbon credit
- basemap ใช้บริการ tile ภายนอก จึงต้องมีอินเทอร์เน็ต
- footprint validation ใน MVP ใช้กรอบครอบภาพเทียบตำแหน่งแปลง; production ควรใช้ PostGIS polygon intersection เต็มรูปแบบ
- authentication/RBAC เป็นเพียง schema-ready boundary และ local demo ยังทำงานโดยไม่ login

## Migration และเวลา

ไฟล์ `backend/migrations/0002_vertical_slice.sql` ใช้ `ADD COLUMN IF NOT EXISTS` เพื่ออัปเกรดฐานข้อมูลต้นแบบเดิมโดยไม่ล้าง volume การเริ่มระบบจะรัน migration แบบ idempotent อัตโนมัติ เวลาเก็บในฐานข้อมูลเป็น UTC และหน้าเว็บแสดงเขตเวลา Asia/Bangkok

## ขั้นตอนถัดไปสำหรับภาพจริง

วางผลลัพธ์ดาวน์โหลดไว้ใน `../output` โดยคง `summary_inventory.json` และโครงสร้างโฟลเดอร์ scene จากสคริปต์ดาวน์โหลดเดิม แล้วรัน `docker compose up --build` ระบบจะ catalog ภาพใหม่จาก hash โดยอัตโนมัติ หากเป็นไฟล์ชนิดอื่น ให้อัปโหลด GeoTIFF/COG ผ่านหน้าเว็บและเลือก band ให้ตรง metadata ห้ามเดาพิกัดจาก PNG/JPEG

เส้นทาง production ที่แนะนำ:

```text
validate → COG → object storage → STAC Item → TiTiler → MapLibre
```

## สิ่งที่ควรเพิ่มก่อนใช้จริง

1. ผู้ใช้ สิทธิ์ และ audit trail แบบ append-only
2. parcel import และ validation ของ geometry
3. sensor/device registry และ time-series database
4. weather, irrigation และ satellite catalog
5. COG object storage + TiTiler หรือ STAC API
6. methodology-versioned carbon calculation
7. evidence signing, verifier portal และ export package
8. automated tests, migrations, observability และ backup policy

ใช้ `CODEX_PROMPT.md` เป็นคำสั่งหลักสำหรับให้ Codex ขยายต้นแบบนี้เป็นระบบที่ครบขึ้น
