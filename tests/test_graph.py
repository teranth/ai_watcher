import pytest

from ai_watcher.graph import GraphError, build_inner_graph, build_top_level_graph
from ai_watcher.schema import CommandStep, RepeatStep, RootDocument


def test_topo_order() -> None:
    steps = [
        CommandStep(id="a", run=["echo", "a"]),
        CommandStep(id="b", run=["echo", "b"], depends_on=["a"]),
    ]
    g = build_top_level_graph(steps)
    assert g.order == ["a", "b"]


def test_cycle_detected() -> None:
    steps = [
        CommandStep(id="a", run=["echo", "a"], depends_on=["b"]),
        CommandStep(id="b", run=["echo", "b"], depends_on=["a"]),
    ]
    with pytest.raises(GraphError, match="cycle"):
        build_top_level_graph(steps)


def test_repeat_inner_order() -> None:
    r = RepeatStep(
        id="r",
        max_iterations=1,
        until="all_success",
        steps=[
            CommandStep(id="x", run=["echo", "x"]),
            CommandStep(id="y", run=["echo", "y"], depends_on=["x"]),
        ],
    )
    g = build_inner_graph(r.steps, scope_label="repeat:r")
    assert g.order == ["x", "y"]


def test_validate_document_integration() -> None:
    from ai_watcher.graph import validate_document

    doc = RootDocument.model_validate(
        {
            "version": 1,
            "workflow": {
                "name": "w",
                "steps": [
                    {"id": "a", "type": "command", "run": ["echo", "a"]},
                    {
                        "id": "r",
                        "type": "repeat",
                        "max_iterations": 1,
                        "until": "all_success",
                        "steps": [
                            {"id": "i", "type": "command", "run": ["echo", "i"]},
                        ],
                    },
                ],
            },
        }
    )
    validate_document(doc)
