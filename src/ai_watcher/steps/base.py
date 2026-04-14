"""Shared types for step execution."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_OUTPUT_CAP = 65536


def cap_bytes(text: str, max_bytes: int = DEFAULT_OUTPUT_CAP) -> str:
    """Truncate UTF-8 text to at most max_bytes (boundary-safe)."""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    truncated = raw[: max_bytes - 20].decode("utf-8", errors="ignore")
    return truncated + "\n...[truncated]...\n"


@dataclass
class StepResult:
    exit_code: int
    stdout: str
    stderr: str
    skipped: bool = False
