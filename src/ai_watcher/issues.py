"""
Extension point for future issue sources (GitHub Issues, webhooks, etc.).

The MVP does not implement ingestion; workflows are driven by CLI prompt input only.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IssueSource(Protocol):
    """Pluggable source of work items (title, body, metadata) for future versions."""

    async def next_item(self) -> dict[str, Any] | None:
        """Return the next issue/task payload, or None when exhausted."""

    def describe(self) -> str:
        """Human-readable label for logging and diagnostics."""
