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

    # --- AI ---
    #: Chat and the monthly summary run on Groq (switched 20 Sep 2026 — the
    #: Gemini free tier's 20-requests/day cap was exhausted mid-demo-prep and
    #: is per Cloud project, not something a consumer Google AI plan raises).
    #: Groq's free tier is rate-limited per minute, not a hard daily wall, and
    #: `openai/gpt-oss-20b` supports the same function-calling shape the
    #: agent loop already drives by hand.
    groq_api_key: str = ""
    groq_model_chat: str = "openai/gpt-oss-20b"
    groq_model_summary: str = "openai/gpt-oss-20b"

    #: Google Gemini stays for bulk categorisation (enrich/llm_classify.py),
    #: the PDF LLM-fallback adapter, and embeddings — none of which this
    #: switch touches, and none of which shares Groq's rate limits.
    gemini_api_key: str = ""
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
        """Comma-separated origins, normalised.

        `CORSMiddleware` matches the browser's `Origin` header by exact
        string equality, and a browser's `Origin` never carries a trailing
        slash. A value pasted straight from an address bar almost always
        does, and the failure mode is silent: no error, no log line, just
        CORS quietly rejecting the deployed frontend (found live, 20 Sep
        2026, against `.../vercel.app/`). Stripping a trailing slash here
        makes that specific paste-in mistake impossible to reintroduce.
        """
        return [
            o.strip().rstrip("/")
            for o in self.allowed_origins.split(",")
            if o.strip()
        ]


settings = Settings()
