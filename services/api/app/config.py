"""Environment configuration.

Every value here is supplied by the environment. Nothing is defaulted to a
real secret, and `.env` is git-ignored (DESIGN.md section 12.2).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- AI ---
    anthropic_api_key: str = ""

    # --- Supabase ---
    supabase_url: str = ""
    supabase_service_key: str = ""  # service_role: server only, never the browser
    supabase_anon_key: str = ""
    database_url: str = ""

    # --- Web ---
    allowed_origins: str = "http://localhost:3000"

    # --- Integrations ---
    telegram_bot_token: str = ""
    internal_api_token: str = ""
    bhashini_user_id: str = ""
    bhashini_api_key: str = ""

    # --- Behaviour ---
    retention_days: int = 90
    max_upload_mb: int = 20

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
