"""`ai-watcher` CLI entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from ai_watcher.context import RunContext
from ai_watcher.executor import ExecutionResult, WorkflowExecutionError, execute_workflow
from ai_watcher.load import WorkflowLoadError, load_workflow_file
from ai_watcher.reporting import emit_run_report


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-watcher",
        description="Run YAML DAG workflows (commands, Copilot SDK, external agent CLIs).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Execute a workflow file")
    run.add_argument(
        "--workflow",
        "-w",
        type=Path,
        required=True,
        help="Path to workflow YAML",
    )
    run.add_argument(
        "--prompt",
        "-p",
        default="",
        help="Inline prompt text (combined with --prompt-file if both set)",
    )
    run.add_argument(
        "--prompt-file",
        "-f",
        type=Path,
        help="Path to a markdown/text file used as prompt context",
    )
    run.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Working directory (default: current directory)",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate graph and print execution order without running steps",
    )
    run.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log each step name and exit code to stderr (executor log)",
    )
    run.add_argument(
        "--debug",
        action="store_true",
        help="Like --verbose, and print full stdout/stderr for every step (to stderr)",
    )
    run.add_argument(
        "--stream-copilot",
        action="store_true",
        help="Stream Copilot SDK assistant deltas to the merged stdout capture",
    )
    run.add_argument(
        "--model",
        "-m",
        default=None,
        metavar="MODEL",
        help="Override Copilot model for all copilot_sdk steps (e.g. claude-haiku-4.5)",
    )
    return p


def _resolve_prompt(args: argparse.Namespace, *, allow_empty: bool) -> tuple[str, Path | None]:
    parts: list[str] = []
    ppath: Path | None = None
    if args.prompt:
        parts.append(args.prompt)
    if args.prompt_file:
        ppath = args.prompt_file.resolve()
        parts.append(ppath.read_text(encoding="utf-8"))
    text = "\n\n".join(parts).strip()
    if not text and not allow_empty:
        raise ValueError("Provide --prompt and/or --prompt-file with non-empty content.")
    return text, ppath


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)

    if ns.command != "run":
        parser.print_help()
        return 2

    if ns.verbose or ns.debug:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        doc = load_workflow_file(ns.workflow)
    except WorkflowLoadError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        prompt, prompt_path = _resolve_prompt(ns, allow_empty=ns.dry_run)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    cwd = (ns.cwd or Path.cwd()).resolve()
    ctx = RunContext(
        cwd=cwd,
        prompt=prompt,
        prompt_path=prompt_path,
        env={},
        copilot_model_override=ns.model,
    )

    async def _go() -> ExecutionResult:
        return await execute_workflow(
            doc,
            ctx,
            dry_run=ns.dry_run,
            verbose=ns.verbose or ns.debug,
            stream_copilot=ns.stream_copilot,
        )

    try:
        result = asyncio.run(_go())
    except WorkflowExecutionError as e:
        print(str(e), file=sys.stderr)
        return 1

    if ns.dry_run:
        for line in result.plan_lines:
            print(line)
        return 0

    emit_run_report(
        result,
        workflow_name=doc.workflow.name,
        cwd=cwd,
        debug=ns.debug,
    )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
