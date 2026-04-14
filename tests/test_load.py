from pathlib import Path

import pytest

from ai_watcher.load import WorkflowLoadError, load_workflow_file


def test_load_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("{", encoding="utf-8")
    with pytest.raises(WorkflowLoadError):
        load_workflow_file(p)
