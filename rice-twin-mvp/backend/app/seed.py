import hashlib
import math
from datetime import datetime, timedelta, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    AWDRuleConfiguration,
    Activity,
    Alert,
    CropSeason,
    EvidenceRecord,
    Farmer,
    FarmerGroup,
    IoTGateway,
    Plot,
    Project,
    PublicDataSnapshot,
    SensorChannel,
    SensorDevice,
    SensorObservation,
    TwinStateSnapshot,
)


DEMO_PLOT_ID = "DEMO-PLOT-001"
DEMO_CENTER_LAT = 14.469728
DEMO_CENTER_LON = 100.274733
DEMO_BOUNDARY_WARNING = (
    "DEMO-PLOT-001 is a synthetic demonstration boundary. "
    "It is not a cadastral, surveyed, legal, ownership, or officially verified plot boundary."
)
DEMO_NOW = datetime(2026, 7, 24, 3, 30, tzinfo=timezone.utc)

# A 240 m x 160 m synthetic rectangle centered near the supplied coordinate.
DEMO_RING = [
    [100.27361993687678, 14.470451039387699],
    [100.27584606312321, 14.470451039387699],
    [100.27584605591937, 14.469004955303385],
    [100.27361994408062, 14.469004955303385],
    [100.27361993687678, 14.470451039387699],
]


def ring_to_wkt(ring: list[list[float]]) -> str:
    points = ", ".join(f"{lon} {lat}" for lon, lat in ring)
    return f"POLYGON(({points}))"


def shifted_ring(lon_offset: float, lat_offset: float) -> list[list[float]]:
    return [[lon + lon_offset, lat + lat_offset] for lon, lat in DEMO_RING]


def ensure_primary_plot_and_season(db: Session) -> tuple[Plot, CropSeason]:
    plot = db.get(Plot, DEMO_PLOT_ID)
    if plot is None:
        plot = Plot(
            id=DEMO_PLOT_ID,
            name="แปลงสาธิตข้าวคาร์บอนต่ำ",
            geometry=WKTElement(ring_to_wkt(DEMO_RING), srid=4326),
            center_lat=DEMO_CENTER_LAT,
            center_lon=DEMO_CENTER_LON,
            area_rai=24.0,
            boundary_source="synthetic_demo",
            crop_stage="แตกกอ",
            water_state="ช่วงปล่อยแห้ง",
            water_level_cm=-8.4,
            awd_cycle=2,
            dry_days=4,
            recommendation="รอฝน 12 ชั่วโมงและวัดระดับน้ำซ้ำ",
            yield_risk="ต่ำ",
            mrv_confidence="สูง",
            data_confidence_score=87,
        )
        db.add(plot)
        db.flush()

    season = db.scalar(
        select(CropSeason).where(
            CropSeason.plot_id == DEMO_PLOT_ID,
            CropSeason.season_code == "2026-WET-DEMO",
        )
    )
    if season is None:
        season = CropSeason(
            id="SEASON-2026-01",
            plot_id=DEMO_PLOT_ID,
            season_code="2026-WET-DEMO",
            name="ฤดูนาปี 2569 (ข้อมูลสาธิต)",
            started_at=DEMO_NOW - timedelta(days=65),
            status="active",
            crop_year=2026,
            rice_variety="กข43 (ข้อมูลสาธิต)",
            planting_method="ปักดำ",
            planting_date=(DEMO_NOW - timedelta(days=65)).date(),
            expected_harvest_date=(DEMO_NOW + timedelta(days=55)).date(),
            baseline_scenario="Traditional continuous flooding — simulated reference",
            project_scenario="Alternate Wetting and Drying — demonstration",
        )
        db.add(season)
        db.flush()

    for activity in db.scalars(select(Activity).where(Activity.plot_id == DEMO_PLOT_ID)):
        if activity.crop_season_id is None:
            activity.crop_season_id = season.id
    db.flush()
    return plot, season


def seed_core_records(db: Session, plot: Plot) -> None:
    project = db.get(Project, "PROJECT-RICE-DEMO")
    if project is None:
        project = Project(
            id="PROJECT-RICE-DEMO",
            name="โครงการสาธิตข้าวคาร์บอนต่ำภาคกลาง",
            description="Integrated Digital Twin executive demonstration",
            status="ACTIVE",
            source_type="REFERENCE",
            is_demo=True,
        )
        db.add(project)
        db.flush()
    if db.get(FarmerGroup, "GROUP-001") is None:
        db.add(FarmerGroup(
            id="GROUP-001", project_id=project.id,
            name="กลุ่มชาวนาสาธิตพระนครศรีอยุธยา",
            province="พระนครศรีอยุธยา", source_type="SIMULATED",
        ))
        db.flush()
    if db.get(Farmer, "FARMER-001") is None:
        db.add(Farmer(
            id="FARMER-001", group_id="GROUP-001",
            display_name="เกษตรกรสาธิต 001", phone_masked="08X-XXX-1201",
            source_type="SIMULATED", is_demo=True,
        ))
        db.flush()
    plot.project_id = project.id
    plot.farmer_id = "FARMER-001"

    offsets = [
        (0.0030, 0.0002), (-0.0030, 0.0003), (0.0004, 0.0025),
        (-0.0003, -0.0025), (0.0031, -0.0021),
    ]
    for index, (lon_offset, lat_offset) in enumerate(offsets, start=2):
        plot_id = f"DEMO-PLOT-{index:03d}"
        if db.get(Plot, plot_id) is not None:
            continue
        ring = shifted_ring(lon_offset, lat_offset)
        db.add(Plot(
            id=plot_id,
            name=f"แปลงเครือข่ายสาธิต {index - 1}",
            geometry=WKTElement(ring_to_wkt(ring), srid=4326),
            center_lat=DEMO_CENTER_LAT + lat_offset,
            center_lon=DEMO_CENTER_LON + lon_offset,
            area_rai=18.0 + index,
            boundary_source="synthetic_demo",
            project_id=project.id,
            farmer_id="FARMER-001",
            crop_stage=["แตกกอ", "ตั้งท้อง", "ออกรวง"][index % 3],
            water_state=["ช่วงปล่อยแห้ง", "ต้องทบทวนให้น้ำ", "ชื้นเพียงพอ"][index % 3],
            water_level_cm=-5.0 - index,
            awd_cycle=max(1, index - 2),
            dry_days=index,
            recommendation="จัดลำดับการส่งน้ำตามความเสี่ยงและระยะข้าว",
            yield_risk="ต่ำ" if index < 5 else "ปานกลาง",
            mrv_confidence="ปานกลาง",
            data_confidence_score=78 + index,
        ))


DEVICE_SPECS = [
    ("WATER-LEVEL-01", "ระดับน้ำในท่อ AWD หลัก", "AWD_PIPE_WATER_LEVEL", "water_level_cm", "cm"),
    ("WATER-LEVEL-02", "ระดับน้ำสำรอง", "FIELD_WATER_LEVEL", "water_level_cm", "cm"),
    ("SOIL-10", "ความชื้นดิน 10 ซม.", "SOIL_MOISTURE_10CM", "soil_moisture_10cm", "%"),
    ("SOIL-30", "ความชื้นดิน 30 ซม.", "SOIL_MOISTURE_30CM", "soil_moisture_30cm", "%"),
    ("SOIL-50", "ความชื้นดิน 50 ซม.", "SOIL_MOISTURE_50CM", "soil_moisture_50cm", "%"),
    ("RAIN-01", "มาตรวัดฝนประจำแปลง", "RAINFALL", "rainfall_mm", "mm"),
    ("WEATHER-01", "สถานีอากาศขนาดเล็ก", "WEATHER", "air_temperature_c", "°C"),
    ("PUMP-01", "สถานะเครื่องสูบน้ำ", "PUMP_STATUS", "pump_status", "state"),
    ("FLOW-01", "อัตราการไหลทางน้ำเข้า", "FLOW_RATE", "flow_rate_lps", "L/s"),
    ("ENERGY-01", "พลังงานเครื่องสูบน้ำ", "PUMP_ENERGY", "pump_energy_kwh", "kWh"),
    ("WATER-QUALITY-01", "คุณภาพน้ำทางน้ำเข้า", "WATER_QUALITY", "water_ec_us_cm", "µS/cm"),
    ("GATE-01", "ตำแหน่งประตูน้ำ", "GATE_POSITION", "gate_position_percent", "%"),
]


def seed_devices_and_observations(db: Session, season: CropSeason) -> None:
    gateway = db.get(IoTGateway, "GW-DEMO-001")
    if gateway is None:
        gateway = IoTGateway(
            id="GW-DEMO-001", name="Rice Twin LoRaWAN Gateway",
            plot_id=DEMO_PLOT_ID, protocol="LoRaWAN / Simulator",
            status="ONLINE", last_seen_at=DEMO_NOW - timedelta(minutes=1),
            source_type="SIMULATED",
            configuration={"mqtt_prefix": "rice-twin/demo-plot-001"},
        )
        db.add(gateway)
    db.flush()

    for index, (device_id, name, device_type, metric, unit) in enumerate(DEVICE_SPECS):
        if db.get(SensorDevice, device_id) is None:
            db.add(SensorDevice(
                id=device_id,
                device_name=name,
                device_type=device_type,
                manufacturer="Demo Instrumentation",
                model=f"RT-{index + 1:02d}",
                serial_number=f"SIM-2026-{index + 1:04d}",
                firmware_version="1.4.2-demo",
                plot_id=DEMO_PLOT_ID,
                gateway_id=gateway.id,
                latitude=DEMO_CENTER_LAT + ((index % 4) - 1.5) * 0.00012,
                longitude=DEMO_CENTER_LON + ((index % 3) - 1) * 0.00014,
                installation_date=(DEMO_NOW - timedelta(days=90)).date(),
                installation_depth_cm=10.0 if "SOIL-10" in device_id else (
                    30.0 if "SOIL-30" in device_id else (50.0 if "SOIL-50" in device_id else None)
                ),
                communication_protocol="LoRaWAN" if index < 7 else "Wi-Fi",
                battery_percent=92 - index * 3,
                signal_rssi=-67 - index * 2,
                last_seen_at=DEMO_NOW - timedelta(minutes=index + 1),
                calibration_due_at=DEMO_NOW + timedelta(days=30 - index),
                status="WARNING" if device_id == "WATER-LEVEL-02" else "ONLINE",
                source_type="SIMULATED",
                is_simulated=True,
                metadata_json={
                    "supported_protocols": ["MQTT", "HTTP webhook", "CSV", "Simulator"],
                    "installation_history": [{"installed_at": "2026-04-25", "plot_id": DEMO_PLOT_ID}],
                },
            ))
            # SensorChannel has a foreign key to SensorDevice but the demo models
            # intentionally do not define an ORM relationship. Flush each new
            # device first so SQLAlchemy cannot reorder its channel insert ahead
            # of the parent row.
            db.flush()
        channel_id = f"CH-{device_id}"
        if db.get(SensorChannel, channel_id) is None:
            limits = {
                "water_level_cm": (-40, 60),
                "soil_moisture_10cm": (0, 100),
                "rainfall_mm": (0, 300),
                "air_temperature_c": (-10, 55),
                "flow_rate_lps": (0, 100),
            }.get(metric, (None, None))
            db.add(SensorChannel(
                id=channel_id, device_id=device_id, channel_key="primary",
                metric=metric, unit=unit, minimum_value=limits[0], maximum_value=limits[1],
                depth_cm=10 if "10cm" in metric else (30 if "30cm" in metric else (50 if "50cm" in metric else None)),
                enabled=True,
            ))
    db.flush()

    if db.scalar(select(SensorObservation.id).limit(1)) is not None:
        return

    metric_devices = {
        "water_level_cm": ("WATER-LEVEL-01", "cm"),
        "soil_moisture_10cm": ("SOIL-10", "%"),
        "rainfall_mm": ("RAIN-01", "mm"),
        "air_temperature_c": ("WEATHER-01", "°C"),
        "pump_status": ("PUMP-01", "state"),
        "flow_rate_lps": ("FLOW-01", "L/s"),
        "pump_energy_kwh": ("ENERGY-01", "kWh"),
    }
    cumulative_energy = 0.0
    for day_index in range(30):
        observed_at = DEMO_NOW - timedelta(days=29 - day_index)
        cycle_day = day_index % 8
        rainfall = 17.0 if day_index in {6, 17, 26} else (4.5 if day_index % 9 == 0 else 0.0)
        pump_on = 1.0 if cycle_day == 7 and rainfall < 10 else 0.0
        water_level = 3.0 - cycle_day * 2.15 + rainfall * 0.34 + pump_on * 10.5
        soil_moisture = 64.0 - cycle_day * 2.1 + rainfall * 0.45 + pump_on * 5.0
        temperature = 29.5 + 2.8 * math.sin(day_index / 4)
        flow = 12.4 if pump_on else 0.0
        cumulative_energy += 4.1 if pump_on else 0.0
        values = {
            "water_level_cm": round(water_level, 2),
            "soil_moisture_10cm": round(min(92, soil_moisture), 2),
            "rainfall_mm": rainfall,
            "air_temperature_c": round(temperature, 2),
            "pump_status": pump_on,
            "flow_rate_lps": flow,
            "pump_energy_kwh": round(cumulative_energy, 2),
        }
        for metric, value in values.items():
            device_id, unit = metric_devices[metric]
            db.add(SensorObservation(
                id=f"OBS-{day_index:02d}-{metric}",
                device_id=device_id,
                plot_id=DEMO_PLOT_ID,
                crop_season_id=season.id,
                metric=metric,
                value=value,
                unit=unit,
                observed_at=observed_at,
                retrieved_at=observed_at + timedelta(seconds=2),
                source_type="SIMULATED",
                source_name="Deterministic Rice Twin Simulator",
                quality_flag="valid",
                is_demo=True,
                ingestion_protocol="SIMULATOR",
                external_id=f"seed-2026-{day_index:02d}-{metric}",
                payload={"seed": 20260724, "scenario": "normal_awd_cycle"},
            ))


def seed_context_rules_alerts_evidence(db: Session, season: CropSeason) -> None:
    if db.get(AWDRuleConfiguration, "AWD-RULE-DEMO-1") is None:
        db.add(AWDRuleConfiguration(
            id="AWD-RULE-DEMO-1",
            version="AWD-DEMO-1.0",
            name="เกณฑ์ AWD สำหรับการสาธิตแบบอธิบายได้",
            parameters={
                "upper_water_threshold_cm": 5,
                "drying_start_threshold_cm": 0,
                "irrigation_trigger_cm": -15,
                "critical_lower_threshold_cm": -20,
                "maximum_dry_days": 7,
                "rain_forecast_threshold_mm": 15,
                "forecast_window_hours": 12,
                "minimum_soil_moisture": 35,
                "crop_stage_exclusions": ["FLOWERING"],
                "sensor_confidence_requirement": 70,
            },
            source_type="REFERENCE",
            disclaimer="เกณฑ์สาธิต ต้องปรับตามพื้นที่ พันธุ์ข้าว และอนุมัติโดยผู้เชี่ยวชาญก่อนใช้จริง",
        ))

    public_rows = [
        ("PUBLIC-WEATHER-01", "weather_forecast", "Open-Meteo compatible demo adapter", "สถานีบริบทภูมิภาค", 22.0, "พยากรณ์ฝน 22 มม. ภายใน 12 ชั่วโมง"),
        ("PUBLIC-RAIN-01", "rainfall_station", "ThaiWater mock adapter", "สถานีฝนสาธิต AY-01", 17.0, "สถานีอยู่ห่าง 6.8 กม. ไม่ใช่ค่าที่แปลง"),
        ("PUBLIC-HYDRO-01", "hydrology", "RID mock adapter", "คลองส่งน้ำสาธิต", 72.0, "ตัวอย่างสถานะความพร้อมน้ำระดับภูมิภาค"),
        ("PUBLIC-SOIL-01", "soil", "LDD import adapter", "ชุดดินสาธิต", 1.0, "ข้อมูลอ้างอิงนำเข้า ไม่ใช่ผลสำรวจเฉพาะแปลง"),
    ]
    for row_id, category, provider, station, value, limitations in public_rows:
        if db.get(PublicDataSnapshot, row_id) is None:
            db.add(PublicDataSnapshot(
                id=row_id, category=category, provider=provider, station_name=station,
                plot_id=DEMO_PLOT_ID, observed_at=DEMO_NOW - timedelta(hours=1),
                retrieved_at=DEMO_NOW, latitude=DEMO_CENTER_LAT + 0.04,
                longitude=DEMO_CENTER_LON - 0.05, distance_km=6.8,
                quality_flag="sample", licence_status="demo_sample",
                source_type="PUBLIC", payload={"value": value, "unit": "context"},
                limitations=limitations,
            ))

    alert_rows = [
        ("ALERT-001", "HEAVY_RAIN_FORECAST", "ฝนหนักคาดการณ์ภายใน 12 ชั่วโมง", "MEDIUM", None),
        ("ALERT-002", "SENSOR_DRIFT", "เซนเซอร์ระดับน้ำสองตัวเริ่มคลาดกัน", "MEDIUM", "WATER-LEVEL-02"),
        ("ALERT-003", "MISSING_EVIDENCE", "หลักฐานรูปถ่ายรอบ AWD ยังไม่ครบ", "LOW", None),
        ("ALERT-004", "CALIBRATION_DUE", "กำหนดสอบเทียบอุปกรณ์ใกล้ถึง", "LOW", "WATER-LEVEL-01"),
    ]
    for alert_id, alert_type, title, severity, device_id in alert_rows:
        if db.get(Alert, alert_id) is None:
            db.add(Alert(
                id=alert_id, alert_type=alert_type, title=title, severity=severity,
                status="OPEN", plot_id=DEMO_PLOT_ID, device_id=device_id,
                assigned_to="FIELD_OFFICER", detail="รายการสาธิตที่สร้างจากกฎคุณภาพข้อมูล",
                source_type="DERIVED", created_at=DEMO_NOW - timedelta(hours=2),
                due_at=DEMO_NOW + timedelta(days=1),
            ))

    evidence_rows = [
        ("EVID-001", "SENSOR_OBSERVATION", "ชุดข้อมูลระดับน้ำ 30 วัน", "SIMULATED", "ACCEPTED"),
        ("EVID-002", "SATELLITE_IMAGE", "Sentinel-2 mosaic ครอบคลุมแปลง", "PUBLIC", "ACCEPTED"),
        ("EVID-003", "FIELD_ACTIVITY", "บันทึกหยุดให้น้ำรอบ AWD", "MANUAL", "ACCEPTED"),
        ("EVID-004", "PUBLIC_DATASET", "Snapshot พยากรณ์อากาศ", "PUBLIC", "PENDING"),
        ("EVID-005", "PHOTO", "ภาพถ่ายท่อ AWD สาธิต", "SIMULATED", "PENDING"),
        ("EVID-006", "CALCULATION_INPUT", "ข้อมูลพลังงานเครื่องสูบน้ำ", "DERIVED", "ACCEPTED"),
        ("EVID-007", "REVIEWER_NOTE", "ข้อสังเกตความพร้อม MRV", "MANUAL", "PENDING"),
        ("EVID-008", "LAB_RESULT", "ตัวอย่างผลวิเคราะห์ในห้องปฏิบัติการ", "SIMULATED", "REJECTED"),
    ]
    for evidence_id, evidence_type, title, source_type, review_status in evidence_rows:
        if db.get(EvidenceRecord, evidence_id) is None:
            db.add(EvidenceRecord(
                id=evidence_id, evidence_type=evidence_type, plot_id=DEMO_PLOT_ID,
                crop_season_id=season.id, title=title,
                captured_at=DEMO_NOW - timedelta(days=3),
                captured_by="demo-field-officer",
                latitude=DEMO_CENTER_LAT, longitude=DEMO_CENTER_LON,
                file_hash=hashlib.sha256(title.encode()).hexdigest(),
                source_type=source_type, review_status=review_status,
                metadata_json={"is_demo": True, "provenance": source_type},
            ))


def seed_activities_and_twin(db: Session, plot: Plot, season: CropSeason) -> None:
    if db.scalar(select(Activity.id).where(Activity.source == "ultimate_seed").limit(1)) is None:
        rows = [
            ("ปักดำ", 60, None, "เริ่มฤดูปลูก"),
            ("ใส่ปุ๋ย", 42, None, "สูตรและปริมาณเป็นข้อมูลสาธิต"),
            ("หยุดให้น้ำ", 7, 3.0, "เริ่มรอบ AWD ที่ 2"),
            ("วัดระดับน้ำ", 4, -4.0, "ระดับน้ำต่ำกว่าผิวดิน"),
            ("ตรวจภาคสนาม", 2, -8.4, "ดินยังมีความชื้นยอมรับได้"),
        ]
        for activity_type, days_ago, level, note in rows:
            db.add(Activity(
                plot_id=plot.id, crop_season_id=season.id,
                activity_type=activity_type, occurred_at=DEMO_NOW - timedelta(days=days_ago),
                note=note, water_level_cm=level, source="ultimate_seed",
                recorded_by="demo-field-officer", latitude=DEMO_CENTER_LAT,
                longitude=DEMO_CENTER_LON, verification_status="demo_reviewed",
                evidence={"source_type": "MANUAL", "is_demo": True},
            ))

    if db.scalar(select(TwinStateSnapshot.id).where(TwinStateSnapshot.plot_id == plot.id).limit(1)) is None:
        db.add(TwinStateSnapshot(
            id="TWIN-STATE-INITIAL",
            plot_id=plot.id, crop_season_id=season.id,
            state={
                "plot_id": plot.id,
                "crop_season_id": season.id,
                "crop_stage": "TILLERING",
                "crop_age_days": 65,
                "water_state": "DRYING",
                "water_level_cm": -8.4,
                "soil_moisture_status": "ACCEPTABLE",
                "soil_moisture_percent": 48.0,
                "awd_cycle_number": 2,
                "dry_period_days": 4.2,
                "rainfall_24h_mm": 2.1,
                "forecast_rainfall_24h_mm": 22.0,
                "pump_status": "OFF",
                "yield_risk": "LOW",
                "flood_risk": "LOW",
                "irrigation_recommendation": "WAIT",
                "data_confidence": 87,
                "provenance": {
                    "water_level_cm": "SIMULATED",
                    "forecast_rainfall_24h_mm": "PUBLIC",
                    "irrigation_recommendation": "DERIVED",
                },
                "updated_at": DEMO_NOW.isoformat(),
            },
            model_version="TWIN-DEMO-1.0", source_type="DERIVED",
            simulated_at=DEMO_NOW, created_at=DEMO_NOW,
        ))


def seed_demo_data(db: Session) -> None:
    plot, season = ensure_primary_plot_and_season(db)
    seed_core_records(db, plot)
    db.flush()
    seed_devices_and_observations(db, season)
    seed_context_rules_alerts_evidence(db, season)
    seed_activities_and_twin(db, plot, season)
    db.commit()
