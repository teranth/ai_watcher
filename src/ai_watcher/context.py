"""Runtime context passed to steps and templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StepOutputRecord:
    exit_code: int
    stdout: str
    stderr: str
    skipped: bool = False


@dataclass
class RunContext:
    """Mutable execution context for one workflow run."""

    cwd: Path
    prompt: str
    prompt_path: Path | None
    env: dict[str, str]
    copilot_model_override: str | None = None
    """When set (e.g. CLI ``--model``), overrides each ``copilot_sdk`` step's ``model`` field."""
    step_outputs: dict[str, StepOutputRecord] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)

    def as_template_dict(self) -> dict[str, Any]:
        """Template context: cwd, prompt, prompt_path, nested steps.*, outputs.*."""
        steps_map: dict[str, Any] = {}

        def _set_nested(dotted: str, rec: StepOutputRecord) -> None:
            payload = {
                "exit_code": rec.exit_code,
                "stdout": rec.stdout,
                "stderr": rec.stderr,
                "skipped": rec.skipped,
            }
            parts = dotted.split(".")
            cur: dict[str, Any] = steps_map
            for p in parts[:-1]:
                nxt = cur.get(p)
                if not isinstance(nxt, dict):
                    nxt = {}
                    cur[p] = nxt
                cur = nxt
            cur[parts[-1]] = payload

        for sid, rec in self.step_outputs.items():
            _set_nested(sid, rec)

        pp = str(self.prompt_path.resolve()) if self.prompt_path else ""
        return {
            "cwd": str(self.cwd.resolve()),
            "prompt": self.prompt,
            "prompt_path": pp,
            "steps": steps_map,
            "outputs": dict(self.outputs),
        }
