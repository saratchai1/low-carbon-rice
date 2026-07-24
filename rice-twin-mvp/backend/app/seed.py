from datetime import datetime, timedelta, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Activity, CropSeason, Plot


DEMO_PLOT_ID = "DEMO-PLOT-001"
DEMO_CENTER_LAT = 14.469728
DEMO_CENTER_LON = 100.274733

# A 240 m x 160 m synthetic rectangle centered near the supplied coordinate.
# It is a demonstration boundary only and must not be treated as a cadastral boundary.
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


def seed_demo_data(db: Session) -> None:
    exists = db.scalar(select(Plot.id).where(Plot.id == DEMO_PLOT_ID))
    if exists:
        season = db.scalar(
            select(CropSeason).where(
                CropSeason.plot_id == DEMO_PLOT_ID,
                CropSeason.season_code == "2026-WET-DEMO",
            )
        )
        if season is None:
            now = datetime.now(timezone.utc)
            season = CropSeason(
                plot_id=DEMO_PLOT_ID,
                season_code="2026-WET-DEMO",
                name="ฤดูนาปี 2569 (ข้อมูลสาธิต)",
                started_at=now - timedelta(days=65),
                status="active",
            )
            db.add(season)
            db.flush()
            for activity in db.scalars(
                select(Activity).where(Activity.plot_id == DEMO_PLOT_ID)
            ):
                activity.crop_season_id = season.id
            db.commit()
        return

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
        water_level_cm=-8.0,
        awd_cycle=2,
        dry_days=4,
        recommendation="ชะลอการให้น้ำ ตรวจพยากรณ์ฝน และวัดระดับน้ำซ้ำภายใน 24 ชั่วโมง",
        yield_risk="ต่ำ",
        mrv_confidence="สูง",
        data_confidence_score=86,
    )
    db.add(plot)
    db.flush()

    now = datetime.now(timezone.utc)
    season = CropSeason(
        plot_id=DEMO_PLOT_ID,
        season_code="2026-WET-DEMO",
        name="ฤดูนาปี 2569 (ข้อมูลสาธิต)",
        started_at=now - timedelta(days=65),
        status="active",
    )
    db.add(season)
    db.flush()
    db.add_all(
        [
            Activity(
                plot_id=DEMO_PLOT_ID,
                crop_season_id=season.id,
                activity_type="หยุดให้น้ำ",
                occurred_at=now - timedelta(days=4),
                note="เริ่มรอบ AWD ที่ 2",
                water_level_cm=3.0,
                source="seed_demo",
                evidence={"type": "demo_record"},
            ),
            Activity(
                plot_id=DEMO_PLOT_ID,
                crop_season_id=season.id,
                activity_type="วัดระดับน้ำ",
                occurred_at=now - timedelta(days=2),
                note="ระดับน้ำลดต่ำกว่าผิวดิน",
                water_level_cm=-4.0,
                source="seed_demo",
                evidence={"type": "demo_record"},
            ),
            Activity(
                plot_id=DEMO_PLOT_ID,
                crop_season_id=season.id,
                activity_type="วัดระดับน้ำ",
                occurred_at=now - timedelta(hours=6),
                note="ยังอยู่ในช่วงปลอดภัยของข้อมูลสาธิต",
                water_level_cm=-8.0,
                source="seed_demo",
                evidence={"type": "demo_record"},
            ),
        ]
    )
    db.commit()
