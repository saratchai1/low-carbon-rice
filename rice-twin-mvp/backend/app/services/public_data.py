from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


class PublicDataAdapter(ABC):
    """Protocol-independent adapter contract for public context data."""

    provider_name = "unconfigured"
    category = "unknown"

    @abstractmethod
    def fetch_current(self) -> dict[str, Any]:
        raise NotImplementedError

    def fetch_history(self) -> list[dict[str, Any]]:
        return []

    def fetch_forecast(self) -> list[dict[str, Any]]:
        return []

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def validate(self, payload: dict[str, Any]) -> tuple[bool, list[str]]:
        return bool(payload), [] if payload else ["empty_payload"]

    def cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def report_status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "category": self.category,
            "live_connected": False,
            "mode": "mock",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


class OpenMeteoDemoAdapter(PublicDataAdapter):
    provider_name = "Open-Meteo compatible demo adapter"
    category = "weather"

    def fetch_current(self) -> dict[str, Any]:
        return {
            "temperature_c": 31.2,
            "relative_humidity_percent": 72,
            "wind_speed_kmh": 9.4,
            "source_type": "PUBLIC",
            "quality_flag": "sample",
            "limitations": "Sample snapshot for a no-key local demonstration.",
        }

    def fetch_forecast(self) -> list[dict[str, Any]]:
        return [{
            "window_hours": 12,
            "rainfall_mm": 22.0,
            "source_type": "PUBLIC",
            "quality_flag": "sample",
        }]


class ThaiWaterMockAdapter(PublicDataAdapter):
    provider_name = "ThaiWater mock adapter"
    category = "rainfall_hydrology"

    def fetch_current(self) -> dict[str, Any]:
        return {
            "station_name": "สถานีฝนสาธิต AY-01",
            "distance_km": 6.8,
            "rainfall_mm": 0.0,
            "source_type": "PUBLIC",
            "quality_flag": "sample",
            "limitations": "Regional context; not a direct measurement at the plot.",
        }


class LDDImportAdapter(PublicDataAdapter):
    provider_name = "LDD imported baseline demo"
    category = "soil_land"

    def fetch_current(self) -> dict[str, Any]:
        return {
            "soil_group": "กลุ่มชุดดินสาธิต",
            "texture": "ดินเหนียว",
            "drainage_class": "ค่อนข้างเลว",
            "rice_suitability": "เหมาะสม",
            "source_type": "PUBLIC",
            "quality_flag": "imported_sample",
            "limitations": "Reference-scale data; field survey is required for confirmation.",
        }


ADAPTERS: dict[str, PublicDataAdapter] = {
    "weather": OpenMeteoDemoAdapter(),
    "hydrology": ThaiWaterMockAdapter(),
    "soil": LDDImportAdapter(),
}

