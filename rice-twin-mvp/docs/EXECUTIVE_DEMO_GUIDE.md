# Executive Demo Guide

## เป้าหมาย

เดโมนี้แสดงให้ผู้บริหารเห็นว่าแพลตฟอร์มรวมข้อมูลแปลง เซนเซอร์ น้ำ สภาพอากาศ
ดาวเทียม งานภาคสนาม และหลักฐานไว้ใน operational workflow เดียว โดยทุกค่าระบุ
provenance และข้อจำกัดอย่างชัดเจน

## ก่อนนำเสนอ

```bash
docker compose up --build
curl http://localhost:8000/api/health
```

เปิด:

- Command Center: `http://localhost:8000`
- Presentation: `http://localhost:8000/presentation`
- API documentation: `http://localhost:8000/docs`

จอเหมาะกับความละเอียด 1440×900 ขึ้นไป กดลูกศรซ้าย/ขวาใน Presentation mode
และกดปุ่มเต็มจอที่มุมขวาล่าง

## เส้นเรื่องแนะนำ 12 นาที

1. เปิด Command Center อธิบายว่าค่าต่าง ๆ เป็นข้อมูลสาธิตและมีป้าย provenance
2. เปิดแผนที่ ย้ำว่าขอบเขต DEMO-PLOT-001 เป็นรูปสังเคราะห์ ไม่ใช่แนวเขตสิทธิ
3. เปิด Plot Digital Twin ดูระดับน้ำ ความชื้น ระยะข้าว ความเสี่ยง และ confidence
4. เปิด Water & AWD อ่าน input, threshold, เหตุผล และคำเตือนของกฎ
5. เปิด IoT Operations ดูอุปกรณ์ 12 ตัว battery, RSSI และ calibration
6. เปิด Satellite เลือกวันที่และ NDVI/LSWI/NDWI จาก dropdown
7. เปิด Demo Scenarios และเล่น “รอฝนตามพยากรณ์”
8. แสดงผลการหลีกเลี่ยงการสูบน้ำ ซึ่งติดป้าย `DERIVED`
9. เปิด Verifier Portal ดู hash, reviewer status และรายงาน
10. จบที่ Carbon MRV: methodology ยังไม่ถูกตั้ง จึงไม่มีการคำนวณหรือกล่าวอ้างเครดิต

## สถานการณ์สาธิต

ระบบมี 10 สถานการณ์แบบ deterministic: รอบ AWD ปกติ, รอฝน, แห้งเกิน,
น้ำท่วม, sensor offline, sensor drift, รายงานภาคสนามไม่ตรง, public-data
ไม่ตรง, satellite conflict และฤดูปลูก/MRV ครบวงจร ปุ่ม Pause, Resume, Reset
และ Next step ทำงานผ่าน Scenario API จริง

## คำตอบสำหรับคำถามสำคัญ

- “ข้อมูลจริงหรือไม่?” — ข้อมูลในเดโมส่วนใหญ่เป็น `SIMULATED`; ภาพดาวเทียมที่
  catalog จากไฟล์ผู้ใช้ติดป้าย `PUBLIC`; ค่าประมวลผลติดป้าย `DERIVED`
- “ออกเครดิตได้หรือยัง?” — ไม่ได้ ระบบยังไม่มี methodology, emission factor
  และ verification ที่อนุมัติ
- “ใช้แปลงจริงหรือไม่?” — ไม่ใช่ ขอบเขตเป็นรูปสังเคราะห์รอบพิกัดเดโม
- “AI ตัดสินใจหรือไม่?” — ผู้ช่วยในเดโมเรียกข้อมูลและเหตุผลจากกฎแบบ deterministic
  ไม่ใช้ external LLM และไม่อนุมัติการให้น้ำแทนผู้รับผิดชอบ
