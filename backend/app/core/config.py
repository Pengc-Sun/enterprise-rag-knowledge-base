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
    embedding_provider: str = "deterministic"
    embedding_model: str = "deterministic-hash"
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_batch_size: int = 32
    embedding_max_retries: int = 3
    retrieval_top_k: int = 10
    final_context_k: int = 4
    hybrid_source_top_k: int = 20
    hybrid_candidate_top_k: int = 10
    rrf_k: int = 60
    query_rewrite_enabled: bool = True
    query_rewrite_history_limit: int = 6
    conversation_context_limit: int = 10
    reranker_provider: str = "deterministic"
    reranker_model: str = "deterministic-cross-encoder"
    llm_provider: str = "deterministic"
    llm_model: str = "deterministic-chat"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 30.0
    log_level: str = "INFO"
    log_json: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
