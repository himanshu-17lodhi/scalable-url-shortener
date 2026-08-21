from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Scalable URL Shortener"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8000"

    # Database Configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "url_shortener"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/url_shortener"
    )
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: float = 30.0
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600

    # Rate Limit & Proxy Security Configuration
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_CAPACITY: int = 10
    RATE_LIMIT_REFILL_RATE: float = 1.0  # Tokens per second
    TRUST_PROXY_HEADERS: bool = True
    TRUSTED_PROXIES: list[str] = ["127.0.0.1", "::1"]
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str | None) -> str:
        if isinstance(v, str) and v:
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            if v.startswith("postgresql://") and not v.startswith(
                "postgresql+asyncpg://"
            ):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
            return v
        return "postgresql+asyncpg://postgres:postgres@localhost:5432/url_shortener"


settings = Settings()
