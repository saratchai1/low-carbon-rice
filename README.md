# Low-Carbon Rice Digital Twin

เครื่องมือต้นแบบสำหรับติดตามแปลงนาแบบลดคาร์บอน โดยรวมข้อมูลกิจกรรมภาคสนาม
ภาพดาวเทียม Sentinel-1/Sentinel-2 การประเมิน AWD และความพร้อมด้าน Carbon MRV
ไว้ในหน้าจอเดียว

## Web application

ตัวเว็บอยู่ใน [`rice-twin-mvp`](./rice-twin-mvp) และรันด้วย Docker Compose:

```bash
cd rice-twin-mvp
docker compose up --build
```

จากนั้นเปิด <http://localhost:8000>

## Satellite processing

สคริปต์ดาวน์โหลดและประมวลผลภาพอยู่ที่
[`download_and_process.py`](./download_and_process.py) ผลลัพธ์ตัวอย่างที่ใช้ในเว็บเก็บอยู่ใน
[`output`](./output)

> โครงการนี้เป็นต้นแบบเพื่อสนับสนุนการตัดสินใจและการตรวจสอบข้อมูล
> ไม่ใช่การรับรองคาร์บอนเครดิตหรือขอบเขตที่ดินตามกฎหมาย
