"""Application configuration loaded from environment variables.

Centralizes all settings so the rest of the app never reads os.environ directly.
This makes testing trivial: override settings in fixtures, not env vars.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for FlowPass.

    Values are loaded from environment variables or a .env file in development.
    In production (Cloud Run), env vars are set via deploy config.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core app
    app_name: str = "FlowPass"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", description="development | production")
    debug: bool = Field(default=False)

    # Server
    host: str = "0.0.0.0"
    port: int = 8080  # Cloud Run injects PORT env var; default 8080

    # Data paths
    venue_data_path: str = "app/data/venue.json"
    crowd_flow_path: str = "app/data/crowd_flow.json"
    reason_templates_path: str = "app/data/reason_templates.json"

    # Google services (set in .env, never committed)
    gemini_api_key: str = Field(default="", description="Gemini API key from AI Studio")
    maps_api_key: str = Field(default="", description="Google Maps Demo Key")

    # Rate limiting
    ask_rate_limit_per_session: int = 5
    ask_rate_limit_window_seconds: int = 600


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance.

    Using lru_cache means Settings is instantiated exactly once per process.
    In tests, call get_settings.cache_clear() after monkeypatching env vars.
    """
    return Settings()
