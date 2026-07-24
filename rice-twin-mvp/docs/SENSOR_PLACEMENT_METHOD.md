# Sensor Placement Method

Algorithm: `HIST-RICE-1.0.0`

ระบบสร้างข้อเสนอ 8 ประเภท:

1. primary water-level sensor
2. secondary water-level sensor
3. rainfall gauge
4. soil-moisture sensor
5. inlet flow meter
6. drainage observation point
7. pump energy meter
8. repeat field-photo point

Primary water level อยู่บริเวณตัวแทนกลางแปลง. Secondary และ soil moisture
เชื่อมกับ recurring wetness/low-growth candidate. จุด inlet, outlet และ pump
ใช้ assumption ของขอบแปลงเพราะยังไม่มี hydraulic survey

ทุก record มี:

- พิกัด `[longitude, latitude]`
- rationale
- supporting zone IDs
- confidence
- assumptions
- `status=PROPOSED`
- `field_verification_status=NOT_FIELD_VERIFIED`

ก่อนติดตั้งจริงต้องสำรวจระดับ, ทิศทางการไหล, ทางเข้า, ตำแหน่ง pump,
coverage เครือข่าย, ความปลอดภัย, สิทธิการเข้าถึง และตำแหน่งที่เกษตรกรยอมรับ
