from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Scalable URL Shortener"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
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

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600

    # Rate Limit Configuration
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_CAPACITY: int = 10
    RATE_LIMIT_REFILL_RATE: float = 1.0  # Tokens per second

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
