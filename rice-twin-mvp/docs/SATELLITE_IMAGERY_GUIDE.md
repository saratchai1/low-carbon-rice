# Satellite Imagery Guide

## การจัดวางภาพ

ระบบอ่าน CRS และ geotransform จาก GeoTIFF/COG แล้วแปลง bounds เป็น EPSG:4326
ก่อนซ้อนบน MapLibre พิกัดเว็บและ GeoJSON ใช้ `[longitude, latitude]`:

```json
[100.274733, 14.469728]
```

ไฟล์ที่ไม่มี CRS จะถูกปฏิเสธ ภาพในคลังปัจจุบันผ่านการตรวจ intersection กับ
ขอบเขตเดโม และ Sentinel-2 ทุกวันที่ใช้ mosaic ของ tile ที่ครอบคลุมแปลง

## Dropdown สำหรับข้าว

- True color: ดูเมฆ คันนา และสภาพผิวทั่วไป
- False color vegetation: แยกพืชพรรณ
- NDVI: ความเขียว/vigor
- EVI: พืชหนาแน่นและลดผลกระทบบางส่วนจากบรรยากาศ
- LSWI: ความชื้นในพืชและผิวดิน
- NDWI: candidate water/wetness

ดัชนีเป็น analytical indicator ไม่ใช่หลักฐานตรงว่าแปลงปฏิบัติ AWD ตามเกณฑ์
ต้องอ่านร่วมกับเมฆ คุณภาพภาพ crop stage, water sensor และ field evidence

## ข้อกำหนดไฟล์

GeoTIFF ควรมี CRS, transform, NoData, band description และ acquisition time
ระบบไม่แก้ไฟล์ต้นฉบับ และใช้ SHA-256 ป้องกัน catalog ซ้ำ การใช้จริงควรสร้าง
COG, STAC Item, object storage และ tile service เช่น TiTiler

ห้ามเดาพิกัดจาก PNG/JPEG ที่ไม่มี world file, bounds หรือ footprint
