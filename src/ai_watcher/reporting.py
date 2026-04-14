"""Human-readable run summaries (used by the CLI)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from ai_watcher.executor import ExecutionResult

# Preview size for stdout on normal runs (full output with --debug).
_DEFAULT_STDOUT_PREVIEW = 4000
_DEBUG_STDOUT_CAP = 120_000
_DEBUG_STDERR_CAP = 32_000


def emit_run_report(
    result: ExecutionResult,
    *,
    workflow_name: str,
    cwd: Path,
    debug: bool,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> None:
    """Print a completion banner, per-step status, and captured output previews."""
    print(
        f"ai-watcher: workflow {workflow_name!r} finished with exit code {result.exit_code}",
        file=out,
    )
    print(f"Working directory: {cwd}", file=out)
    print(file=out)
    if not result.execution_log:
        print("(No steps recorded.)", file=out)
        return

    print("Steps:", file=out)
    for key, res in result.execution_log:
        if res.skipped:
            status = "skipped (only_if)"
        else:
            status = f"exit {res.exit_code}"
        print(f"  · {key}: {status}", file=out)

        if res.skipped:
            continue

        if debug:
            if res.stdout:
                body = res.stdout
                if len(body) > _DEBUG_STDOUT_CAP:
                    body = body[:_DEBUG_STDOUT_CAP] + "\n… [stdout truncated in debug preview]\n"
                print(f"    --- stdout ({len(res.stdout)} bytes) ---", file=err)
                print(body, file=err)
            if res.stderr:
                eb = res.stderr
                if len(eb) > _DEBUG_STDERR_CAP:
                    eb = eb[:_DEBUG_STDERR_CAP] + "\n… [stderr truncated]\n"
                print(f"    --- stderr ({len(res.stderr)} bytes) ---", file=err)
                print(eb, file=err)
        else:
            if not res.stdout:
                continue
            body = res.stdout
            if len(body) <= _DEFAULT_STDOUT_PREVIEW:
                print("    stdout:", file=out)
                print(_indent(body.rstrip() + "\n", "      "), file=out, end="")
            else:
                print(
                    f"    stdout: {len(res.stdout)} bytes "
                    f"(showing first {_DEFAULT_STDOUT_PREVIEW} chars; use --debug for more)",
                    file=out,
                )
                print(
                    _indent(body[:_DEFAULT_STDOUT_PREVIEW].rstrip() + "\n", "      "),
                    file=out,
                    end="",
                )
                print("      …", file=out)


def _indent(text: str, prefix: str) -> str:
    return "".join(prefix + line for line in text.splitlines(True))
