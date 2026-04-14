"""Run `script` steps: interpreter + path + args."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from ai_watcher.context import RunContext
from ai_watcher.schema import ScriptStep
from ai_watcher.steps.base import StepResult, cap_bytes
from ai_watcher.templates import render_optional, render_template


def _merge_env(ctx: RunContext, extra: dict[str, str] | None) -> dict[str, str]:
    base = {**os.environ, **ctx.env}
    if extra:
        base.update(extra)
    return base


async def run_script_step(
    step: ScriptStep,
    ctx: RunContext,
    *,
    timeout: float | None = None,
) -> StepResult:
    tmpl = ctx.as_template_dict()
    path = Path(render_template(step.path, tmpl)).expanduser()
    args = [render_template(a, tmpl) for a in step.args]
    cwd_raw = render_optional(step.working_directory, tmpl)
    cwd = Path(cwd_raw).expanduser() if cwd_raw else ctx.cwd
    env = _merge_env(ctx, step.env)
    to = timeout if timeout is not None else step.timeout_seconds

    if step.interpreter:
        argv = [render_template(x, tmpl) for x in step.interpreter] + [str(path)] + args
    else:
        argv = [str(path)] + args

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
