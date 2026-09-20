"""Eval-harness options.

The live layers are opt-in because they cost API quota; the offline layer is
the one that runs in CI and on every commit.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run the `live: true` eval subset against the real model (~8 questions).",
    )
    parser.addoption(
        "--live-all",
        action="store_true",
        default=False,
        help="Run every eval case against the real model. Needs billing; "
        "25 questions at 2-3 calls each exceeds the free-tier daily cap.",
    )
