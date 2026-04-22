from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    export_dir: str = "./data/exports"
    static_dir: str = "./data/static"
    max_upload_mb: int = Field(default=30, ge=1)
    default_model_name: str = "google/gemini-2.5-flash-lite"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_fallback_models_raw: str = "google/gemini-2.5-flash"
    openrouter_site_url: str = "https://finance-tools.fuhaojun.com"
    openrouter_app_title: str = "PDF to Excel Tool"
    cors_origins_raw: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3001,"
        "http://127.0.0.1:3001"
    )

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def export_path(self) -> Path:
        return Path(self.export_dir)

    @property
    def static_path(self) -> Path:
        return Path(self.static_dir)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def openrouter_fallback_models(self) -> list[str]:
        return [model.strip() for model in self.openrouter_fallback_models_raw.split(",") if model.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.export_path.mkdir(parents=True, exist_ok=True)
    settings.static_path.mkdir(parents=True, exist_ok=True)
    return settings
