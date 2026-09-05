"""
Central configuration for FinRecon AI.

All secrets and environment-specific values come from environment variables.
Nothing sensitive is hardcoded. See .env.example for the full list.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "FinRecon AI"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "sqlite:///./finrecon.db"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # LLM provider abstraction
    # Supported: anthropic | openai | gemini | none
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"

    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    LLM_REQUEST_TIMEOUT_SECONDS: int = 30

    # Reconciliation tuning
    DATE_TOLERANCE_DAYS: int = 2
    AMOUNT_MISMATCH_THRESHOLD: float = 1.0
    FUZZY_MATCH_MIN_CONFIDENCE: float = 0.75

    # Uploads
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_UPLOAD_ROWS: int = 20000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        if self.LLM_PROVIDER == "none":
            return False

        if self.LLM_PROVIDER == "anthropic":
            return bool(self.ANTHROPIC_API_KEY)

        if self.LLM_PROVIDER == "openai":
            return bool(self.OPENAI_API_KEY)

        if self.LLM_PROVIDER == "gemini":
            return bool(self.GEMINI_API_KEY)

        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()