"""Run `copilot_sdk` steps using github-copilot-sdk."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType
from copilot.session import PermissionHandler

from ai_watcher.context import RunContext
from ai_watcher.schema import CopilotSdkStep
from ai_watcher.steps.base import StepResult, cap_bytes
from ai_watcher.templates import render_optional, render_template

# Matches Copilot CLI `--model` ids (see `copilot help` / GitHub docs).
DEFAULT_MODEL = "claude-haiku-4.5"


def _load_tools(module_name: str, export: str) -> list[Any]:
    mod = importlib.import_module(module_name)
    tools = getattr(mod, export, None)
    if tools is None:
        raise ValueError(
            f"Module {module_name!r} has no attribute {export!r} (expected a list of tools)"
        )
    if not isinstance(tools, (list, tuple)):
        raise ValueError(f"{module_name}.{export} must be a list or tuple")
    return list(tools)


async def run_copilot_sdk_step(
    step: CopilotSdkStep,
    ctx: RunContext,
    *,
    stream: bool = False,
) -> StepResult:
    tmpl = ctx.as_template_dict()
    prompt = render_template(step.prompt, tmpl)
    cwd_raw = render_optional(step.working_directory, tmpl)
    work_dir = str(Path(cwd_raw).expanduser().resolve()) if cwd_raw else str(ctx.cwd.resolve())

    if ctx.copilot_model_override:
        model = ctx.copilot_model_override.strip() or DEFAULT_MODEL
    else:
        model = render_template(step.model, tmpl).strip() or DEFAULT_MODEL

    create_kwargs: dict[str, Any] = {
        "on_permission_request": PermissionHandler.approve_all,
        "model": model,
        "streaming": step.streaming or stream,
        "working_directory": work_dir,
    }
    if step.skill_directories:
        create_kwargs["skill_directories"] = [
            str(Path(render_template(d, tmpl)).expanduser().resolve()) for d in step.skill_directories
        ]
    if step.tools_module:
        create_kwargs["tools"] = _load_tools(step.tools_module, step.tools_export)

    chunks: list[str] = []
    client = CopilotClient()

    async def _run() -> StepResult:
        await client.start()
        session = None
        try:
            # SDK 0.2+: create_session is keyword-only; no positional config dict.
            session = await client.create_session(**create_kwargs)

            if stream or step.streaming:

                def handle_event(event: Any) -> None:
                    if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                        d = getattr(event.data, "delta_content", None) or ""
                        if d:
                            chunks.append(d)

                session.on(handle_event)

            last = await session.send_and_wait(
                prompt,
                timeout=step.send_timeout_seconds,
            )
            text = ""
            if chunks:
                text = "".join(chunks)
            elif last is not None:
                data = last.data
                text = getattr(data, "content", None) or getattr(data, "detailed_content", None) or ""
            return StepResult(exit_code=0, stdout=cap_bytes(str(text)), stderr="")
        finally:
            if session is not None:
                try:
                    await session.destroy()
                except Exception:
                    pass
            await client.stop()

    try:
        return await _run()
    except Exception as e:
        return StepResult(
            exit_code=1,
            stdout="",
            stderr=cap_bytes(f"copilot_sdk error: {e!s}"),
        )
