# IoT Integration Guide

## Device model

โครงสร้างหลักคือ `IoTGateway → SensorDevice → SensorChannel →
SensorObservation` อุปกรณ์มีตำแหน่ง วันติดตั้ง ความลึก protocol, battery,
RSSI, firmware, last-seen และ calibration due date

## HTTP ingestion

```bash
curl -X POST http://localhost:8000/api/v1/observations \
  -H 'Content-Type: application/json' \
  -d '{
    "device_id": "WATER-LEVEL-01",
    "plot_id": "DEMO-PLOT-001",
    "metric": "water_level_cm",
    "value": -9.4,
    "unit": "cm",
    "observed_at": "2026-07-24T03:30:00Z",
    "source_type": "LIVE",
    "source_name": "field-gateway-01",
    "ingestion_protocol": "HTTP",
    "external_id": "gateway-message-10001"
  }'
```

`external_id` ควรไม่ซ้ำเพื่อรองรับ idempotency ค่า out-of-range จะได้ HTTP 422
และ duplicate จะได้ 409

## Protocol mapping

- MQTT: bridge topic ไป payload เดียวกับ HTTP แล้วส่งเข้า ingestion service
- LoRaWAN: map DevEUI → `device_id`; decoded port/field → `metric`
- CSV: แปลงแต่ละแถวเป็น observation พร้อม `source_name=CSV import`
- Simulator: ใช้ `source_type=SIMULATED`; ห้ามแสดงเป็น live telemetry

## Quality checks

ระบบตรวจ physical range และใช้ข้อมูล registry เพื่อแสดง offline, low battery,
weak RSSI และ overdue calibration การใช้จริงควรเพิ่ม sequence gap, clock skew,
stuck-value, rate-of-change, cross-sensor agreement และ quarantine queue

## Production checklist

ใช้ TLS และ per-device credential, เซ็น payload, เก็บ raw immutable message,
บังคับ UTC, ทำ dead-letter queue, metric/trace, rotate key และแยก tenant
ข้อมูล telemetry ไม่ควรถือเป็นหลักฐานที่รับรองแล้วจนกว่าจะผ่าน quality review
