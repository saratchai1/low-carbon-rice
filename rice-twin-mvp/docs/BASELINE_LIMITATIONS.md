# Historical Baseline Limitations

ข้อความต่อไปนี้ต้องแสดงใน UI และรายงาน:

- Historical imagery analysis is an analytical demonstration. It does not
  independently verify AWD compliance.
- Overhead imagery cannot directly measure water depth below the soil surface.
- Crop-stage, planting-window, and harvest-window results are estimates unless
  confirmed by field records.
- Fertilizer application, straw management, yield, and greenhouse-gas emissions
  cannot be determined reliably from imagery alone.
- Carbon results shown in the demonstration are not verified carbon credits.
- No actual cultivation or field IoT installation has been completed for the
  demonstration plot.

ข้อจำกัดเฉพาะชุดข้อมูล:

- ขอบเขต DEMO-PLOT-001 เป็น synthetic
- Sentinel‑2 จำนวน 51 scene ครอบคลุมเพียงด้านเหนือของแปลงและถูกตัดออกจาก
  cycle detection
- Sentinel‑2 ไม่มี cloud probability/SCL metadata จึงมี optical quality cap 85
- Sentinel‑1 ไม่มี field calibration/orbit-normalization record
- ปี 2023 และ 2026 เป็น partial calendar years
- ไม่มี field crop label, planting log, harvest weighing, fertilizer, straw,
  yield, water depth หรือ chamber GHG record
- wetness ที่เกิดหลังฝนเป็นเพียง plausible context ไม่ใช่ causal conclusion
