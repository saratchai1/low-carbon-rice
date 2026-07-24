# Executive Imagery Demo Guide

เปิด `http://localhost:8000/presentation` แล้วใช้ลูกศรซ้าย/ขวา,
Space หรือ Page Up/Page Down. ปุ่มเต็มจออยู่มุมขวาล่าง

## Presenter notes

1. **Demonstration plot** — ย้ำว่าขอบเขตเป็น synthetic ไม่ใช่แนวเขตสำรวจ
2. **Three-year archive** — ค่า inventory/usable โหลดจาก analysis run จริง
3. **Historical replay** — กด “เล่นย้อนหลัง”; ภาพมาจาก scene จริงตาม timeline
4. **Crop cycles** — อธิบายว่าระบบคืน planting/harvest window ไม่ใช่ exact date
5. **Area estimates** — เป็นช่วงของ candidate cover ไม่ใช่ผลสำรวจผลผลิต
6. **Recurring zones** — ใช้เพื่อกำหนดคำถามภาคสนาม ไม่ใช่ระบุสาเหตุ
7. **Can/cannot prove** — เน้น `NOT_SUPPORTED` สำหรับ AWD, depth, fertilizer,
   straw, yield และ GHG
8. **Sensor design** — ทุกจุด `PROPOSED · NOT FIELD VERIFIED`
9. **Baseline versus project** — historical water management ยัง `UNKNOWN`
10. **Future AWD** — กดเล่นสถานการณ์; ค่าทั้งหมด `SIMULATED`/`DERIVED`
11. **IoT closes gaps** — อธิบายสิ่งที่ภาพวัดไม่ได้และต้องใช้ field record
12. **T-VER readiness** — methodology และ emission factor ยังไม่ตั้งค่า
13. **Close** — เปิด Historical Explorer เพื่อ drill down และดาวน์โหลด export

ก่อนนำเสนอให้ตรวจ:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/v1/plots/DEMO-PLOT-001/historical-baseline
docker compose exec api python -m pytest -q
```
