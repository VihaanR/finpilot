"""Environment configuration.

Every value here is supplied by the environment. Nothing is defaulted to a
real secret, and `.env` is git-ignored (DESIGN.md section 12.2).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Anchored to this file, not to the working directory.
#:
#: `env_file=".env"` resolves against the *cwd*, so settings loaded only when
#: the process happened to start inside `services/api`. Uvicorn does, which is
#: why this went unnoticed; pytest runs from the repo root and silently got an
#: empty key -- no error, just a product that behaved as though no key existed.
#: A path that depends on where you were standing is not configuration.
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # --- AI (Google Gemini, DESIGN.md 9.1) ---
    gemini_api_key: str = ""
    #: One model per job rather than one model everywhere: the jobs have
    #: different latency and quality profiles.
    #:
    #: Measured against a real key on 20 Sep 2026, and the reason chat and
    #: summary share a model: every Gemini *Pro* model reports limit=0/day on
    #: the free tier, and `gemini-2.5-pro` additionally 404s as "no longer
    #: available to new users". `gemini-3.8-flash` works but allows only
    #: 20 requests/day, and one question costs two or more calls.
    #: `gemini-3.5-flash` supports function calling and has its own, larger
    #: daily bucket, which is what makes the free tier usable at all.
    gemini_model_chat: str = "gemini-3.5-flash"
    gemini_model_summary: str = "gemini-3.5-flash"
    gemini_model_classify: str = "gemini-3.5-flash-lite"
    gemini_model_embedding: str = "gemini-embedding-2"
    #: gemini-embedding-2 emits 3072 dims and truncates cleanly via MRL.
    #: Must match document_chunks.embedding in the migration.
    embedding_dimensions: int = 768

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
