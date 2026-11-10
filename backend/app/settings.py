"""Loads backend/.env into the environment for local development.

Variables already set in the real environment (e.g. on Render) win, and blank
values in .env are skipped so an empty ``ANTHROPIC_API_KEY=`` line does not
hide credentials from another source.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for key, value in dotenv_values(path).items():
        if value and key not in os.environ:
            os.environ[key] = value
