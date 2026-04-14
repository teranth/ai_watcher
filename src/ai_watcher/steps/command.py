"""Run `command` steps via subprocess."""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from ai_watcher.context import RunContext
from ai_watcher.schema import CommandStep
from ai_watcher.steps.base import StepResult, cap_bytes
from ai_watcher.templates import render_optional, render_template


def _merge_env(ctx: RunContext, extra: dict[str, str] | None) -> dict[str, str]:
    base = {**os.environ, **ctx.env}
    if extra:
        base.update(extra)
    return base


def _render_run(step: CommandStep, tmpl: dict[str, Any]) -> str | list[str]:
    if isinstance(step.run, str):
        return render_template(step.run, tmpl)
    return [render_template(x, tmpl) for x in step.run]


async def run_command_step(
    step: CommandStep,
    ctx: RunContext,
    *,
    timeout: float | None = None,
) -> StepResult:
    tmpl = ctx.as_template_dict()
    cwd_raw = render_optional(step.working_directory, tmpl)
    cwd = Path(cwd_raw).expanduser() if cwd_raw else ctx.cwd
    env = _merge_env(ctx, step.env)
    run = _render_run(step, tmpl)
    to = timeout if timeout is not None else step.timeout_seconds

    def _sync_run() -> StepResult:
        if step.shell:
            cmd = run if isinstance(run, str) else " ".join(shlex.quote(x) for x in run)
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=to,
            )
        else:
            if isinstance(run, str):
                raise ValueError("command.run must be a list when shell is false")
            proc = subprocess.run(
                run,
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
