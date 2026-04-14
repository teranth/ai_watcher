"""Orchestrate workflow execution: DAG order, retries, repeat blocks."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

from ai_watcher.context import RunContext, StepOutputRecord
from ai_watcher.graph import (
    GraphError,
    build_inner_graph,
    build_top_level_graph,
    validate_document,
)
from ai_watcher.load import RootDocument
from ai_watcher.schema import (
    CommandStep,
    CopilotSdkStep,
    ExternalCliStep,
    InnerStep,
    RepeatStep,
    RepeatUntil,
    ScriptStep,
    TopLevelStep,
)
from ai_watcher.steps.command import run_command_step
from ai_watcher.steps.copilot_sdk import run_copilot_sdk_step
from ai_watcher.steps.external_cli import run_external_cli_step
from ai_watcher.steps.script import run_script_step
from ai_watcher.steps.base import StepResult
from ai_watcher.templates import render_template

log = logging.getLogger("ai_watcher.executor")


class WorkflowExecutionError(Exception):
    """Fatal workflow error."""


@dataclass
class ExecutionHooks:
    """Optional overrides for testing (mock subprocess / SDK)."""

    run_command: Callable[..., Coroutine[Any, Any, StepResult]] | None = None
    run_script: Callable[..., Coroutine[Any, Any, StepResult]] | None = None
    run_external_cli: Callable[..., Coroutine[Any, Any, StepResult]] | None = None
    run_copilot_sdk: Callable[..., Coroutine[Any, Any, StepResult]] | None = None


@dataclass
class ExecutionResult:
    exit_code: int
    """0 if workflow completed successfully."""

    plan_lines: list[str] = field(default_factory=list)
    """Populated when dry_run is True."""

    execution_log: list[tuple[str, StepResult]] = field(default_factory=list)
    """Ordered (step_key, result) for each executed step (including skipped)."""


def _check_only_if(step: InnerStep | TopLevelStep, ctx: RunContext) -> bool:
    if step.only_if is None:
        return True
    tmpl = ctx.as_template_dict()
    path_str = render_template(step.only_if.file_exists, tmpl)
    return Path(path_str).expanduser().exists()


def _store_result(
    ctx: RunContext,
    storage_key: str,
    result: StepResult,
    output_key: str | None,
) -> None:
    ctx.step_outputs[storage_key] = StepOutputRecord(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        skipped=result.skipped,
    )
    if output_key and not result.skipped:
        ctx.outputs[output_key] = result.stdout


def _until_satisfied(until: RepeatUntil, order: list[str], results: dict[str, StepResult]) -> bool:
    ran: list[tuple[str, StepResult]] = []
    for iid in order:
        r = results[iid]
        if not r.skipped:
            ran.append((iid, r))
    if not ran:
        return False
    if until == "all_success":
        return all(r.exit_code == 0 for _, r in ran)
    if until == "any_success":
        return any(r.exit_code == 0 for _, r in ran)
    _, last = ran[-1]
    return last.exit_code == 0


async def _run_with_retries(
    factory: Callable[[], Coroutine[Any, Any, StepResult]],
    retries: int,
    backoff: float,
) -> StepResult:
    attempt = 0
    while True:
        res = await factory()
        if res.skipped or res.exit_code == 0:
            return res
        if attempt >= retries:
            return res
        if backoff > 0:
            await asyncio.sleep(backoff)
        attempt += 1


async def _dispatch_executable(
    step: InnerStep,
    ctx: RunContext,
    hooks: ExecutionHooks,
    *,
    stream_copilot: bool,
) -> StepResult:
    if isinstance(step, CommandStep):
        fn = hooks.run_command or run_command_step
        return await fn(step, ctx)
    if isinstance(step, ScriptStep):
        fn = hooks.run_script or run_script_step
        return await fn(step, ctx)
    if isinstance(step, ExternalCliStep):
        fn = hooks.run_external_cli or run_external_cli_step
        return await fn(step, ctx)
    if isinstance(step, CopilotSdkStep):
        fn = hooks.run_copilot_sdk or run_copilot_sdk_step
        return await fn(step, ctx, stream=stream_copilot)
    raise TypeError(f"Unsupported inner step type: {type(step)}")


async def _run_inner_block(
    repeat: RepeatStep,
    ctx: RunContext,
    hooks: ExecutionHooks,
    *,
    stream_copilot: bool,
    verbose: bool,
    iteration_label: str,
    execution_log: list[tuple[str, StepResult]],
) -> tuple[int, dict[str, StepResult]]:
    """Run one full iteration of inner steps. Returns (ok_for_until, last_results)."""
    topo = build_inner_graph(repeat.steps, scope_label=f"repeat:{repeat.id}")
    by_id = {s.id: s for s in repeat.steps}
    results: dict[str, StepResult] = {}

    for iid in topo.order:
        step = by_id[iid]
        storage_key = f"{repeat.id}.{iid}"
        log_key = f"{repeat.id}{iteration_label}.{iid}"
        if not _check_only_if(step, ctx):
            sk = StepResult(exit_code=0, stdout="", stderr="", skipped=True)
            results[iid] = sk
            _store_result(ctx, storage_key, sk, step.output)
            execution_log.append((log_key, sk))
            if verbose:
                log.info("skip %s (only_if false)", storage_key)
            continue

        async def _one() -> StepResult:
            return await _dispatch_executable(step, ctx, hooks, stream_copilot=stream_copilot)

        res = await _run_with_retries(_one, step.retries, step.retry_backoff_seconds)
        results[iid] = res
        _store_result(ctx, storage_key, res, step.output)
        execution_log.append((log_key, res))
        if verbose:
            log.info(
                "step %s exit=%s skipped=%s",
                storage_key,
                res.exit_code,
                res.skipped,
            )

        if res.exit_code != 0 and not res.skipped and not step.continue_on_error:
            return 1, results

    ok = _until_satisfied(repeat.until, topo.order, results)
    return (0 if ok else 1), results


async def _run_repeat(
    repeat: RepeatStep,
    ctx: RunContext,
    hooks: ExecutionHooks,
    *,
    stream_copilot: bool,
    verbose: bool,
    execution_log: list[tuple[str, StepResult]],
) -> int:
    last_code = 1
    for iteration in range(repeat.max_iterations):
        label = f"[iter {iteration + 1}/{repeat.max_iterations}]"
        if verbose:
            log.info("repeat %s iteration %s/%s", repeat.id, iteration + 1, repeat.max_iterations)
        code, _results = await _run_inner_block(
            repeat,
            ctx,
            hooks,
            stream_copilot=stream_copilot,
            verbose=verbose,
            iteration_label=label,
            execution_log=execution_log,
        )
        last_code = code
        if code == 0:
            return 0
    return last_code


async def _run_top_level_step(
    step: TopLevelStep,
    ctx: RunContext,
    hooks: ExecutionHooks,
    *,
    stream_copilot: bool,
    verbose: bool,
    execution_log: list[tuple[str, StepResult]],
) -> int:
    if isinstance(step, RepeatStep):
        return await _run_repeat(
            step,
            ctx,
            hooks,
            stream_copilot=stream_copilot,
            verbose=verbose,
            execution_log=execution_log,
        )

    storage_key = step.id
    if not _check_only_if(step, ctx):
        sk = StepResult(exit_code=0, stdout="", stderr="", skipped=True)
        _store_result(ctx, storage_key, sk, step.output)
        execution_log.append((storage_key, sk))
        return 0

    async def _one() -> StepResult:
        assert not isinstance(step, RepeatStep)
        return await _dispatch_executable(step, ctx, hooks, stream_copilot=stream_copilot)

    res = await _run_with_retries(_one, step.retries, step.retry_backoff_seconds)
    _store_result(ctx, storage_key, res, step.output)
    execution_log.append((storage_key, res))
    if verbose:
        log.info("step %s exit=%s", storage_key, res.exit_code)

    if res.skipped:
        return 0
    if res.exit_code == 0:
        return 0
    if step.continue_on_error:
        return res.exit_code
    return res.exit_code


async def execute_workflow(
    doc: RootDocument,
    ctx: RunContext,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    stream_copilot: bool = False,
    hooks: ExecutionHooks | None = None,
) -> ExecutionResult:
    """
    Execute a validated workflow document.

    Call :func:`validate_document` or load via :func:`ai_watcher.load.load_workflow_file`
    after parsing.
    """
    h = hooks or ExecutionHooks()
    try:
        validate_document(doc)
    except GraphError as e:
        raise WorkflowExecutionError(str(e)) from e

    topo = build_top_level_graph(doc.workflow.steps)
    by_id: dict[str, TopLevelStep] = {s.id: s for s in doc.workflow.steps}

    if dry_run:
        lines: list[str] = ["Top-level order: " + " -> ".join(topo.order)]
        for s in doc.workflow.steps:
            if isinstance(s, RepeatStep):
                inner = build_inner_graph(s.steps, scope_label=f"repeat:{s.id}")
                lines.append(f"  repeat {s.id}: " + " -> ".join(inner.order))
        return ExecutionResult(exit_code=0, plan_lines=lines)

    execution_log: list[tuple[str, StepResult]] = []
    deferred = 0
    for sid in topo.order:
        step = by_id[sid]
        code = await _run_top_level_step(
            step,
            ctx,
            h,
            stream_copilot=stream_copilot,
            verbose=verbose,
            execution_log=execution_log,
        )
        if code == 0:
            continue
        st = by_id[sid]
        if isinstance(st, RepeatStep):
            return ExecutionResult(exit_code=code, execution_log=execution_log)
        if st.continue_on_error:
            deferred = code
        else:
            return ExecutionResult(exit_code=code, execution_log=execution_log)

    return ExecutionResult(exit_code=deferred, execution_log=execution_log)


def execute_workflow_sync(
    doc: RootDocument,
    ctx: RunContext,
    **kwargs: Any,
) -> ExecutionResult:
    return asyncio.run(execute_workflow(doc, ctx, **kwargs))
