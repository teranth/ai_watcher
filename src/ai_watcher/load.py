"""Load workflow YAML and validate against schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ai_watcher.schema import RootDocument


class WorkflowLoadError(Exception):
    """Raised when YAML cannot be read or validated."""

    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


def load_yaml_dict(raw: str | bytes, *, source_hint: str | None = None) -> dict[str, Any]:
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        hint = f" ({source_hint})" if source_hint else ""
        raise WorkflowLoadError(f"Invalid YAML{hint}: {e}", path=source_hint) from e
    if not isinstance(data, dict):
        raise WorkflowLoadError(
            f"Workflow root must be a mapping, got {type(data).__name__}",
            path=source_hint,
        )
    return data


def parse_workflow(data: dict[str, Any], *, source_hint: str | None = None) -> RootDocument:
    try:
        return RootDocument.model_validate(data)
    except ValidationError as e:
        hint = f" ({source_hint})" if source_hint else ""
        raise WorkflowLoadError(f"Invalid workflow schema{hint}:\n{e}") from e


def load_workflow_file(path: Path | str) -> RootDocument:
    p = Path(path)
    raw = p.read_bytes()
    data = load_yaml_dict(raw, source_hint=str(p.resolve()))
    return parse_workflow(data, source_hint=str(p.resolve()))
