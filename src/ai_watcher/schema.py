"""Pydantic models for workflow YAML (version 1)."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class OnlyIfFileExists(BaseModel):
    """Skip the step when the resolved path does not exist."""

    file_exists: str


OnlyIf = OnlyIfFileExists


class StepCommon(BaseModel):
    """Fields shared by executable step types."""

    id: str = Field(..., min_length=1, description="Unique step id within its scope.")
    name: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    retries: int = Field(default=0, ge=0)
    retry_backoff_seconds: float = Field(default=0.0, ge=0.0)
    continue_on_error: bool = False
    only_if: OnlyIf | None = None
    output: str | None = Field(
        default=None,
        description="Context key to store stdout/assistant text (e.g. 'review_notes').",
    )
    timeout_seconds: float | None = Field(default=None, gt=0)


class CommandStep(StepCommon):
    type: Literal["command"] = "command"
    run: str | list[str]
    working_directory: str | None = None
    env: dict[str, str] | None = None
    shell: bool = Field(
        default=False,
        description="If True, run `run` through the system shell (less safe).",
    )


class ScriptStep(StepCommon):
    type: Literal["script"] = "script"
    path: str
    args: list[str] = Field(default_factory=list)
    interpreter: list[str] | None = Field(
        default=None,
        description="Argv prefix e.g. ['python3'] or ['bash']; default runs path executable.",
    )
    working_directory: str | None = None
    env: dict[str, str] | None = None


class CopilotSdkStep(StepCommon):
    type: Literal["copilot_sdk"] = "copilot_sdk"
    model: str = Field(
        default="claude-haiku-4.5",
        description="Copilot CLI model id (e.g. claude-haiku-4.5, claude-sonnet-4.5).",
    )
    streaming: bool = False
    prompt: str = Field(..., description="Message sent to the session; supports templates.")
    skill_directories: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    tools_module: str | None = Field(
        default=None,
        description="Import path; module should expose TOOLS list of @define_tool callables.",
    )
    tools_export: str = "TOOLS"
    send_timeout_seconds: float = Field(default=120.0, gt=0)


class ExternalCliStep(StepCommon):
    type: Literal["external_cli"] = "external_cli"
    command: str
    args: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    env: dict[str, str] | None = None


RepeatUntil = Literal["all_success", "any_success", "last_exit_success"]

InnerStep = Annotated[
    Union[CommandStep, ScriptStep, CopilotSdkStep, ExternalCliStep],
    Field(discriminator="type"),
]


class RepeatStep(BaseModel):
    """Runs nested steps up to max_iterations until `until` is satisfied."""

    type: Literal["repeat"] = "repeat"
    id: str = Field(..., min_length=1)
    name: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    max_iterations: int = Field(..., ge=1)
    until: RepeatUntil
    steps: list[InnerStep] = Field(..., min_length=1)


TopLevelStep = Annotated[
    Union[CommandStep, ScriptStep, CopilotSdkStep, ExternalCliStep, RepeatStep],
    Field(discriminator="type"),
]


class WorkflowSpec(BaseModel):
    name: str = "workflow"
    steps: list[TopLevelStep]


class RootDocument(BaseModel):
    """Top-level YAML document."""

    version: Literal[1] = 1
    workflow: WorkflowSpec
