from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_token: str
    google_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    database_url: str
    redis_url: str

    allowed_user_ids: str = ""

    @field_validator("database_url")
    @classmethod
    def _ensure_asyncpg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    @property
    def allowed_user_ids_set(self) -> set[int]:
        return {
            int(uid.strip())
            for uid in self.allowed_user_ids.split(",")
            if uid.strip()
        }


settings = Settings()
