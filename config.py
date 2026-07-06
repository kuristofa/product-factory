"""Typed, environment-driven configuration for the Product Factory.

Generation runs through the Claude Code CLI on the machine's logged-in Max account,
so there is no API key here. Import `settings` and use it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def _get(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name, default)
    return val.strip() if isinstance(val, str) else val


@dataclass(frozen=True)
class Settings:
    model: str
    timeout_seconds: int
    dm_tool: str
    output_dir: Path
    briefs_dir: Path
    methodology_notes_path: Path | None


def load_settings() -> Settings:
    notes_raw = _get("METHODOLOGY_NOTES_PATH", "")
    notes_path = Path(notes_raw) if notes_raw else None
    return Settings(
        # Leave blank to use whatever the logged-in Claude Code session defaults to.
        model=_get("CLAUDE_MODEL", "") or "",
        timeout_seconds=int(_get("CLAUDE_TIMEOUT_SECONDS", "300") or 300),
        # Default DM-automation tool when a brief doesn't specify one.
        dm_tool=_get("DM_TOOL", "ManyChat") or "ManyChat",
        output_dir=ROOT / (_get("OUTPUT_DIR", "output") or "output"),
        briefs_dir=ROOT / (_get("BRIEFS_DIR", "briefs") or "briefs"),
        methodology_notes_path=notes_path,
    )


settings = load_settings()
