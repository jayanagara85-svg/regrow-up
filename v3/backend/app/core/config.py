from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://regrow:regrowpass@postgres:5432/regrow_db"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "regrow-files"
    MINIO_SECURE: bool = False

    # Auth
    SECRET_KEY: str = "super-secret-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # AI
    GEMINI_API_KEY: str = "not-set"

    # WhatsApp
    WHATSAPP_VERIFY_TOKEN: str = "regrow-verify-token"
    WHATSAPP_API_TOKEN: str = "not-set"
    WHATSAPP_PHONE_ID: str = "not-set"

    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
