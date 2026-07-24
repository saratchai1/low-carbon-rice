# Rice Twin MVP

ต้นแบบ Digital Twin สำหรับแปลงข้าวคาร์บอนต่ำ โดยเน้นสถานะน้ำแบบ AWD, บันทึกกิจกรรม, evidence timeline และการซ้อนภาพ GeoTIFF บนแผนที่

## สิ่งที่มีในต้นแบบ

- แผนที่ MapLibre พร้อมขอบเขตแปลงสาธิต
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

> ขอบเขตแปลงในโครงการนี้สร้างขึ้นเพื่อสาธิตเท่านั้น ไม่ใช่แนวเขตสำรวจ แนวเขตโฉนด หรือขอบเขตแปลงจริง

## เริ่มใช้งาน

ต้องมี Docker และ Docker Compose

```bash
cd rice-twin-mvp
docker compose up --build
```

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
docker compose exec api pytest -q
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
GET    /api/plots/{plot_id}
PATCH  /api/plots/{plot_id}
GET    /api/plots/{plot_id}/activities
POST   /api/plots/{plot_id}/activities
GET    /api/imagery?plot_id=DEMO-PLOT-001
POST   /api/imagery
GET    /api/imagery/{imagery_id}/preview.png
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
- ยังไม่มี methodology engine สำหรับคำนวณก๊าซเรือนกระจก
- data confidence เป็นค่าตัวอย่าง ไม่ใช่ผลการตรวจรับรอง
- ไม่มีการออก ซื้อขาย หรือรับรอง carbon credit
- basemap ใช้บริการ tile ภายนอก จึงต้องมีอินเทอร์เน็ต

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
