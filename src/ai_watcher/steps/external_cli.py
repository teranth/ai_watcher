"""Run external agent CLIs (copilot, codex, claude, …) as subprocess."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ai_watcher.context import RunContext
from ai_watcher.schema import ExternalCliStep
from ai_watcher.steps.base import StepResult, cap_bytes
from ai_watcher.templates import render_optional, render_template


def _merge_env(ctx: RunContext, extra: dict[str, str] | None) -> dict[str, str]:
    base = {**os.environ, **ctx.env}
    if extra:
        base.update(extra)
    return base


async def run_external_cli_step(
    step: ExternalCliStep,
    ctx: RunContext,
    *,
    timeout: float | None = None,
) -> StepResult:
    tmpl = ctx.as_template_dict()
    cmd = render_template(step.command, tmpl)
    args = [render_template(a, tmpl) for a in step.args]
    cwd_raw = render_optional(step.working_directory, tmpl)
    cwd = Path(cwd_raw).expanduser() if cwd_raw else ctx.cwd
    env = _merge_env(ctx, step.env)
    to = timeout if timeout is not None else step.timeout_seconds

    which_cmd = shutil.which(cmd)
    if which_cmd is None:
        return StepResult(
            exit_code=127,
            stdout="",
            stderr=cap_bytes(
                f"Executable not found on PATH: {cmd!r}. "
                "Install the CLI or fix PATH before running this workflow."
            ),
        )

    argv = [which_cmd, *args]

    def _sync_run() -> StepResult:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=to,
        )
        return StepResult(
            exit_code=proc.returncode,
            stdout=cap_bytes(proc.stdout or ""),
            stderr=cap_bytes(proc.stderr or ""),
        )

    return await asyncio.to_thread(_sync_run)
