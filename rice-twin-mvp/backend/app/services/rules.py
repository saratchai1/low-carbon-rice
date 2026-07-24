from datetime import datetime, timezone


DEMO_RULE_VERSION = "demo-1.0"


def evaluate_awd(*, water_level_cm: float, crop_stage: str, dry_days: int) -> list[dict]:
    """Transparent demo rules. Thresholds are not agronomic prescriptions."""
    inputs = {
        "water_level_cm": water_level_cm,
        "crop_stage": crop_stage,
        "dry_days": dry_days,
        "weather_forecast": "not_connected",
    }
    evaluated_at = datetime.now(timezone.utc).isoformat()
    if crop_stage in {"ออกดอก", "ตั้งท้อง"}:
        return [{
            "rule_id": "AWD-SENSITIVE-STAGE",
            "rule_version": DEMO_RULE_VERSION,
            "severity": "warning",
            "explanation": "ระยะข้าวถูกตั้งเป็นระยะอ่อนไหว จึงไม่ใช้เกณฑ์ระดับน้ำสาธิตตัดสินการให้น้ำ",
            "inputs_used": inputs,
            "evaluated_at": evaluated_at,
            "recommended_action": "ให้เจ้าหน้าที่ภาคสนามและนักวิชาการตรวจสอบก่อนตัดสินใจ",
        }]
    if water_level_cm <= -15:
        severity = "high" if dry_days >= 7 else "warning"
        action = "ตรวจระดับน้ำซ้ำและพิจารณาให้น้ำภายใต้คำแนะนำของนักวิชาการ"
        explanation = "ระดับน้ำต่ำกว่าเกณฑ์สาธิต -15 ซม.; ระบบยังไม่มีพยากรณ์ฝน"
    else:
        severity = "info"
        action = "ติดตามระดับน้ำภายใน 24 ชั่วโมง"
        explanation = "ระดับน้ำยังไม่ถึงเกณฑ์สาธิต -15 ซม.; ควรติดตามต่อเนื่อง"
    return [{
        "rule_id": "AWD-WATER-LEVEL-DEMO",
        "rule_version": DEMO_RULE_VERSION,
        "severity": severity,
        "explanation": explanation,
        "inputs_used": inputs,
        "evaluated_at": evaluated_at,
        "recommended_action": action,
    }]

