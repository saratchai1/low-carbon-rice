from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://rice_twin:rice_twin@db:5432/rice_twin"
    imagery_dir: Path = Path("/data/imagery")
    satellite_output_dir: Path = Path("/satellite-output")
    max_upload_mb: int = 512

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
