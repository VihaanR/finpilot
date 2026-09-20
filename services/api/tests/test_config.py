"""Config parsing (app/config.py).

Narrow on purpose: this is one property that broke a real deployment, not a
general settings test suite.
"""

from __future__ import annotations

from app.config import Settings


def test_allowed_origins_list_strips_trailing_slashes() -> None:
    """A pasted-from-address-bar URL breaks CORS silently otherwise.

    Found live 20 Sep 2026: ALLOWED_ORIGINS was set to a Vercel URL with a
    trailing slash. CORSMiddleware matches the browser's Origin header (which
    never has one) by exact string equality, so every request was silently
    rejected -- no error, no log line, just "Failed to fetch" in the browser.
    """
    s = Settings(allowed_origins="https://finpilot-swart.vercel.app/")
    assert s.allowed_origins_list == ["https://finpilot-swart.vercel.app"]


def test_allowed_origins_list_handles_multiple_and_whitespace() -> None:
    s = Settings(
        allowed_origins="https://a.example.com/, https://b.example.com ,,http://localhost:3000/"
    )
    assert s.allowed_origins_list == [
        "https://a.example.com",
        "https://b.example.com",
        "http://localhost:3000",
    ]


def test_allowed_origins_list_without_trailing_slash_is_unchanged() -> None:
    s = Settings(allowed_origins="https://finpilot-swart.vercel.app")
    assert s.allowed_origins_list == ["https://finpilot-swart.vercel.app"]
