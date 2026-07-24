from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Activity, Imagery, Plot


def evaluate_data_quality(db: Session, plot: Plot) -> dict:
    activities = list(db.scalars(
        select(Activity).where(Activity.plot_id == plot.id).order_by(Activity.occurred_at)
    ))
    imagery = list(db.scalars(select(Imagery).where(Imagery.plot_id == plot.id)))
    water = [item for item in activities if item.water_level_cm is not None]
    chronology_ok = all(
        activities[index].occurred_at <= activities[index + 1].occurred_at
        for index in range(max(0, len(activities) - 1))
    )
    jump_ok = all(
        abs(float(water[index + 1].water_level_cm) - float(water[index].water_level_cm)) <= 50
        for index in range(max(0, len(water) - 1))
    )
    imagery_ok = not imagery or all(item.footprint_intersects_plot for item in imagery)
    recent = bool(water) and (datetime.now(timezone.utc) - water[-1].occurred_at).days <= 7
    evidence_ok = any(bool(item.evidence) for item in activities)
    checks = [
        ("recent_water_observation", recent, 30, "มีข้อมูลระดับน้ำภายใน 7 วัน"),
        ("chronology", chronology_ok, 15, "ลำดับเวลากิจกรรมถูกต้อง"),
        ("water_level_jump", jump_ok, 20, "ไม่พบการกระโดดของระดับน้ำเกิน 50 ซม."),
        ("imagery_intersection", imagery_ok, 20, "footprint ภาพทุกภาพตัดกับแปลง"),
        ("evidence_presence", evidence_ok, 15, "มีกิจกรรมอย่างน้อยหนึ่งรายการพร้อมหลักฐาน"),
    ]
    components = [
        {"check_id": check_id, "passed": passed, "weight": weight,
         "score": weight if passed else 0, "explanation": explanation}
        for check_id, passed, weight, explanation in checks
    ]
    return {
        "plot_id": plot.id,
        "score": sum(item["score"] for item in components),
        "components": components,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "คะแนนความครบถ้วนของข้อมูลสาธิต ไม่ใช่ผลการรับรอง MRV",
    }

