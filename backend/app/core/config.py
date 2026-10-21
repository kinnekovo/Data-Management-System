from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    app_name: str = "基于 MongoDB 的问卷系统"
    app_environment: str = "development"
    api_prefix: str = "/api/v1"
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_database: str = "survey_system"
    mongodb_test_database: str = "survey_system_test"
    mongodb_timeout_ms: int = 5000
    frontend_origins: str = "http://localhost:5173"
    jwt_secret: str = "local-development-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    max_page_size: int = 100

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
