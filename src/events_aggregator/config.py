from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения. Читаются из переменных окружения и .env."""

    app_name: str = "Events Aggregator"
    debug: bool = False
    port: int = 8000

    events_provider_base_url: str
    events_provider_api_key: SecretStr = SecretStr("")
    events_provider_timeout: float = 10.0
    events_provider_max_retries: int = 3

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/events"
    db_echo: bool = False
    db_pool_size: int = 20
    db_max_overflow: int = 10

    http_timeout: float = 10.0

    sync_enabled: bool = True
    sync_hour: int = 3
    sync_batch_size: int = 200
    sync_first_date: str = "2000-01-01"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
