from pathlib import Path

from ai_watcher.cli import main


def test_cli_run_executes_step(tmp_path: Path) -> None:
    """End-to-end run (stdout formatting is covered in test_reporting)."""
    wf = tmp_path / "w.yaml"
    wf.write_text(
        """
version: 1
workflow:
  name: echo_test
  steps:
    - id: greet
      type: command
      run: ["echo", "hello-from-step"]
""",
        encoding="utf-8",
    )
    code = main(["run", "--workflow", str(wf), "-p", "ctx"])
    assert code == 0


def test_cli_dry_run(tmp_path: Path) -> None:
    wf = tmp_path / "w.yaml"
    wf.write_text(
        """
version: 1
workflow:
  name: t
  steps:
    - id: a
      type: command
      run: ["echo", "x"]
""",
        encoding="utf-8",
    )
    code = main(["run", "--workflow", str(wf), "--dry-run"])
    assert code == 0


def test_cli_requires_prompt_when_not_dry_run(tmp_path: Path) -> None:
    wf = tmp_path / "w.yaml"
    wf.write_text(
        """
version: 1
workflow:
  name: t
  steps:
    - id: a
      type: command
      run: ["echo", "x"]
""",
        encoding="utf-8",
    )
    code = main(["run", "--workflow", str(wf)])
    assert code == 1
