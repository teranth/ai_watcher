from pathlib import Path

import pytest

from ai_watcher.context import RunContext
from ai_watcher.executor import ExecutionHooks, execute_workflow
from ai_watcher.schema import RootDocument
from ai_watcher.steps.base import StepResult


async def _fake_cmd(step, ctx, **kwargs):
    return StepResult(exit_code=0, stdout=f"did-{step.id}", stderr="")


async def _fake_copilot(step, ctx, **kwargs):
    return StepResult(exit_code=0, stdout="assistant-ok", stderr="")


@pytest.mark.asyncio
async def test_execute_linear_commands() -> None:
    doc = RootDocument.model_validate(
        {
            "version": 1,
            "workflow": {
                "name": "w",
                "steps": [
                    {"id": "a", "type": "command", "run": ["true"]},
                    {"id": "b", "type": "command", "run": ["true"], "depends_on": ["a"]},
                ],
            },
        }
    )
    ctx = RunContext(cwd=Path("/tmp"), prompt="hi", prompt_path=None, env={})
    hooks = ExecutionHooks(
        run_command=_fake_cmd,
    )
    r = await execute_workflow(doc, ctx, hooks=hooks)
    assert r.exit_code == 0
    assert "a" in ctx.step_outputs and "b" in ctx.step_outputs
    assert [k for k, _ in r.execution_log] == ["a", "b"]


@pytest.mark.asyncio
async def test_continue_on_error_defers_exit() -> None:
    async def flaky(step, ctx, **kwargs):
        if step.id == "bad":
            return StepResult(exit_code=1, stdout="", stderr="e")
        return StepResult(0, "ok", "")

    doc = RootDocument.model_validate(
        {
            "version": 1,
            "workflow": {
                "name": "w",
                "steps": [
                    {"id": "bad", "type": "command", "run": ["false"], "continue_on_error": True},
                    {"id": "after", "type": "command", "run": ["true"], "depends_on": ["bad"]},
                ],
            },
        }
    )
    ctx = RunContext(cwd=Path("/tmp"), prompt="", prompt_path=None, env={})
    r = await execute_workflow(doc, ctx, hooks=ExecutionHooks(run_command=flaky))
    assert r.exit_code == 1


@pytest.mark.asyncio
async def test_repeat_until_all_success() -> None:
    doc = RootDocument.model_validate(
        {
            "version": 1,
            "workflow": {
                "name": "w",
                "steps": [
                    {
                        "id": "r",
                        "type": "repeat",
                        "max_iterations": 3,
                        "until": "all_success",
                        "steps": [
                            {"id": "x", "type": "command", "run": ["true"]},
                            {"id": "y", "type": "command", "run": ["true"], "depends_on": ["x"]},
                        ],
                    }
                ],
            },
        }
    )
    ctx = RunContext(cwd=Path("/tmp"), prompt="", prompt_path=None, env={})
    r = await execute_workflow(doc, ctx, hooks=ExecutionHooks(run_command=_fake_cmd))
    assert r.exit_code == 0
    assert [k for k, _ in r.execution_log] == ["r[iter 1/3].x", "r[iter 1/3].y"]


@pytest.mark.asyncio
async def test_copilot_sdk_mocked() -> None:
    doc = RootDocument.model_validate(
        {
            "version": 1,
            "workflow": {
                "name": "w",
                "steps": [
                    {
                        "id": "c",
                        "type": "copilot_sdk",
                        "prompt": "Hello {{ prompt }}",
                    }
                ],
            },
        }
    )
    ctx = RunContext(cwd=Path("/tmp"), prompt="world", prompt_path=None, env={})
    r = await execute_workflow(
        doc,
        ctx,
        hooks=ExecutionHooks(run_copilot_sdk=_fake_copilot),
    )
    assert r.exit_code == 0
    assert ctx.outputs == {} or "c" in ctx.step_outputs
