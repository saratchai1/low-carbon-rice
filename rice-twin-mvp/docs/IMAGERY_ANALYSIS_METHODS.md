# Imagery Analysis Methods

Algorithm version: `HIST-RICE-1.0.0`

## Preprocessing

1. ตรวจว่าไฟล์อ่านได้ มี CRS และ affine transform
2. อ่าน dimensions, resolution, bounds, dtype, nodata และ band description
3. คำนวณ SHA‑256 โดยไม่แก้ต้นฉบับ
4. แปลง polygon แปลงจาก EPSG:4326 ไป CRS ของ raster
5. สร้าง geometry mask บน native 10 m grid
6. คำนวณ plot intersection แยกจาก valid-pixel fraction
7. สร้าง web preview ด้วย 2–98 percentile stretch เมื่อถูกเรียก
8. เก็บ processing log, component score, limitations และ version

ข้อมูลชุดปัจจุบันอยู่ EPSG:32647 และกริดตรงกัน จึงไม่ resample ในการวิเคราะห์.
โค้ดเก็บ metadata ที่จำเป็นสำหรับเพิ่ม COG/STAC/TiTiler ภายหลัง

## Multispectral

Band mapping ถูกยืนยันชัดเจน ไม่ assume band order. ผลประกอบด้วย NDVI,
GNDVI, NDWI, SAVI, EVI และเมื่อมี SWIR จะมี MNDWI/NDMI.
Archive ปัจจุบันใช้ NDVI, LSWI, NDWI และ EVI ที่อยู่ใน stack สำหรับ plot metric.

Candidate thresholds:

- dense vegetation: `NDVI >= 0.50`
- cultivated cover: `NDVI >= 0.22`
- water candidate: `NDWI >= 0.10`
- wet-soil candidate: `LSWI >= 0 and NDVI < 0.45`
- bare/prepared candidate: `NDVI < 0.20 and NDWI < 0.10`

Candidate ไม่ใช่ crop-species verification หรือ field measurement.

## RGB-only

มี pure analytical functions สำหรับ Excess Green, VARI, GLI, normalized
green และ brightness. ผล visible-spectrum ไม่ถูกเรียกว่า NDVI.

## Radar

Sentinel‑1 ใช้ VV, VH และ VH−VV. Candidate water/smooth surface ใช้
`VV < −13 dB` และ `VH−VV < −5 dB`; structure candidate ใช้
`VH > −20 dB`. Threshold เหล่านี้เป็น analytical reference ที่ยังไม่ผ่าน
field calibration และไม่วัด water depth

## Temporal

- raw observations ถูกเก็บและส่งออกเสมอ
- smooth: rolling median 3 observations
- interpolation: ปิด
- gap: มากกว่า 2.5 เท่าของ expected interval 8 วัน
- optical scene ที่ plot coverage ต่ำกว่า 80% ไม่เข้าสู่ crop-cycle detection

Cycle peak ต้องมี smoothed vegetation อย่างน้อย 0.38, prominence อย่างน้อย
0.10 และห่างจาก peak ก่อนอย่างน้อย 70 วัน. Planting/harvest แสดงเป็นช่วง
±7 วันรอบ observation anchor

## Confidence

ระบบแสดงคะแนนแยก:

- imagery availability
- image quality
- temporal coverage
- spatial coverage
- classification
- crop-cycle detection
- cultivated-area estimate
- historical baseline completeness

Completeness เป็นค่าเฉลี่ยถ่วงน้ำหนักที่อธิบาย component ได้ ไม่แทนคะแนนอื่น
และไม่ทำให้ข้ออ้าง `NOT_SUPPORTED` กลายเป็นข้ออ้างที่รองรับ

## Spatial

Recurring wetness/low-growth ใช้ native 10 m pixels และสรุปเป็น 4 quadrant
เพื่อไม่แสดง precision เกินข้อมูล. ผลทุก zone เป็น `DERIVED` และต้อง
field-check
