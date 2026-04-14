import io
from pathlib import Path

from ai_watcher.executor import ExecutionResult
from ai_watcher.reporting import emit_run_report
from ai_watcher.steps.base import StepResult


def test_emit_run_report_preview() -> None:
    out_s, err_s = io.StringIO(), io.StringIO()
    r = ExecutionResult(
        exit_code=0,
        execution_log=[
            ("a", StepResult(0, "hello\n", "")),
        ],
    )
    emit_run_report(r, workflow_name="w", cwd=Path("/tmp"), debug=False, out=out_s, err=err_s)
    assert "finished with exit code 0" in out_s.getvalue()
    assert "hello" in out_s.getvalue()
    assert err_s.getvalue() == ""


def test_emit_run_report_debug_on_stderr() -> None:
    out_s, err_s = io.StringIO(), io.StringIO()
    r = ExecutionResult(
        exit_code=0,
        execution_log=[("a", StepResult(0, "out", "err"))],
    )
    emit_run_report(r, workflow_name="w", cwd=Path("/tmp"), debug=True, out=out_s, err=err_s)
    assert "--- stdout" in err_s.getvalue()
    assert "out" in err_s.getvalue()
    assert "err" in err_s.getvalue()
