# Public Data Adapter Guide

## Contract

adapter ทุกตัวใช้ interface เดียวกัน:

- `fetch_current()`
- `fetch_history()`
- `fetch_forecast()`
- `normalize()`
- `validate()`
- `cache()`
- `report_status()`

registry อยู่ใน `backend/app/services/public_data.py` และแสดงผลที่
`GET /api/v1/public-data`

## Adapter ที่มีในเดโม

- Open-Meteo demo adapter: ตัวอย่าง current/forecast structure
- Thai Water mock adapter: ตัวอย่างสถานีและบริบทน้ำ
- LDD import adapter: boundary สำหรับการนำเข้าข้อมูลดิน

snapshot ทุกตัวเก็บ provider, station, observed/retrieved timestamps, coordinate,
distance, licence status, quality flag, payload และ limitations พร้อม
`source_type=PUBLIC`

## การเพิ่ม adapter

1. สร้าง class ที่สืบทอด `PublicDataAdapter`
2. normalize เป็นหน่วยมาตรฐานของแพลตฟอร์ม
3. validate schema, range และเวลา
4. ระบุ licence/attribution และข้อจำกัดเชิงพื้นที่
5. เพิ่ม instance ลง `ADAPTERS`
6. เพิ่ม contract test สำหรับ timeout, malformed payload และ cache fallback

Public data เป็นบริบทระดับพื้นที่ ไม่ควรแทน point sensor ในแปลงโดยอัตโนมัติ
เมื่อแหล่งข้อมูลขัดแย้ง ระบบต้องเก็บทั้งสองค่าและสร้าง review item
