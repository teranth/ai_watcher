import pytest
from pydantic import ValidationError

from ai_watcher.schema import RootDocument


def test_minimal_workflow() -> None:
    doc = RootDocument.model_validate(
        {
            "version": 1,
            "workflow": {
                "name": "t",
                "steps": [{"id": "a", "type": "command", "run": ["true"]}],
            },
        }
    )
    assert doc.workflow.steps[0].id == "a"


def test_reject_unknown_step_type() -> None:
    with pytest.raises(ValidationError):
        RootDocument.model_validate(
            {
                "version": 1,
                "workflow": {
                    "name": "t",
                    "steps": [{"id": "a", "type": "not_a_type", "run": ["x"]}],
                },
            }
        )
