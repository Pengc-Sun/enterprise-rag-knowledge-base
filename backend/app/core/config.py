from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise RAG Knowledge Base"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+asyncpg://enterprise_rag:enterprise_rag@localhost:5432/enterprise_rag"
    )
    database_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me-in-production-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    upload_dir: str = "storage/uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    embedding_dimension: int = 1536

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
