# Carbon MRV Limitations

## สถานะปัจจุบัน

`METHODOLOGY_NOT_CONFIGURED`

แพลตฟอร์มเดโมเก็บ monitoring data และประเมิน data/evidence readiness เท่านั้น
ไม่มี methodology, baseline definition, approved emission factor, leakage rule,
uncertainty treatment, validation หรือ verification ที่ได้รับอนุมัติ

ดังนั้นระบบจงใจคืนค่า `null` สำหรับ:

- calculated estimate
- eligible estimate
- verified amount
- issued credits
- baseline/project emissions
- estimated reduction

ห้ามตีความ water saved, energy avoided หรือ scenario outcome ว่าเป็น GHG
reduction หรือ carbon credit ค่าดังกล่าวเป็น `DERIVED` operational estimates
ภายใต้ข้อมูลสาธิต

## สิ่งที่ต้องมี ก่อนคำนวณจริง

1. methodology และ version ที่โครงการใช้จริง
2. project boundary, baseline และ eligibility ที่อนุมัติ
3. emission factors พร้อม source/version/effective date
4. monitoring plan และ QA/QC
5. uncertainty, missing-data และ conservative adjustment rules
6. validation/verification workflow และ verifier independence
7. immutable evidence package, sign-off และ audit trail
8. registry issuance/retirement reconciliation

หน้าจอและรายงานต้องคงข้อความ `METHODOLOGY NOT CONFIGURED` จนกว่าส่วนประกอบ
ข้างต้นจะถูกตั้งค่าและอนุมัติตาม governance ของโครงการ
