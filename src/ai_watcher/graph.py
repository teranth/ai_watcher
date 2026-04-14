"""DAG validation and topological ordering for workflow steps."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from ai_watcher.schema import InnerStep, RepeatStep, RootDocument, TopLevelStep


class GraphError(Exception):
    """Invalid or cyclic dependency graph."""


@dataclass(frozen=True)
class TopoResult:
    """Topological order and adjacency metadata."""

    order: list[str]
    """Execution order (stable where possible)."""

    incoming: dict[str, set[str]]
    """For each node, set of predecessor ids."""

    outgoing: dict[str, set[str]]
    """For each node, set of successor ids."""


def _validate_deps(step_ids: set[str], depends_on: list[str], step_label: str) -> None:
    for d in depends_on:
        if d not in step_ids:
            raise GraphError(f"Step {step_label!r} depends on unknown id {d!r}")


def build_top_level_graph(steps: list[TopLevelStep]) -> TopoResult:
    """Validate top-level DAG (repeat nodes are single vertices; inner graphs validated separately)."""
    step_ids = {s.id for s in steps}
    if len(step_ids) != len(steps):
        dup = [s.id for s in steps]
        raise GraphError(f"Duplicate top-level step id: {sorted({x for x in dup if dup.count(x) > 1})}")

    for s in steps:
        _validate_deps(step_ids, s.depends_on, s.id)
        if isinstance(s, RepeatStep):
            inner_ids = {x.id for x in s.steps}
            if len(inner_ids) != len(s.steps):
                raise GraphError(f"Duplicate inner step id inside repeat {s.id!r}")
            for inner in s.steps:
                _validate_deps(inner_ids, inner.depends_on, f"{s.id}.{inner.id}")

    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    for s in steps:
        for d in s.depends_on:
            incoming[s.id].add(d)
            outgoing[d].add(s.id)

    order = _topological_sort(step_ids, incoming, outgoing)
    return TopoResult(order=order, incoming=dict(incoming), outgoing=dict(outgoing))


def build_inner_graph(steps: list[InnerStep], *, scope_label: str) -> TopoResult:
    """Topological order for inner steps of a repeat block."""
    step_ids = {s.id for s in steps}
    if len(step_ids) != len(steps):
        raise GraphError(f"Duplicate inner step id in {scope_label!r}")

    for s in steps:
        _validate_deps(step_ids, s.depends_on, f"{scope_label}.{s.id}")

    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    for s in steps:
        for d in s.depends_on:
            incoming[s.id].add(d)
            outgoing[d].add(s.id)

    order = _topological_sort(step_ids, incoming, outgoing)
    return TopoResult(order=order, incoming=dict(incoming), outgoing=dict(outgoing))


def _topological_sort(
    nodes: set[str],
    incoming: dict[str, set[str]],
    outgoing: dict[str, set[str]],
) -> list[str]:
    # Kahn's algorithm with deterministic ordering (sorted ready queue).
    in_degree = {n: len(incoming.get(n, ())) for n in nodes}
    ready = deque(sorted(n for n in nodes if in_degree[n] == 0))
    result: list[str] = []
    while ready:
        n = ready.popleft()
        result.append(n)
        for m in sorted(outgoing.get(n, ())):
            in_degree[m] -= 1
            if in_degree[m] == 0:
                ready.append(m)

    if len(result) != len(nodes):
        raise GraphError("Workflow graph contains a cycle or unreachable nodes")
    return result


def validate_document(doc: RootDocument) -> None:
    """Run all graph checks for a parsed document."""
    build_top_level_graph(doc.workflow.steps)
    for s in doc.workflow.steps:
        if isinstance(s, RepeatStep):
            build_inner_graph(s.steps, scope_label=f"repeat:{s.id}")
