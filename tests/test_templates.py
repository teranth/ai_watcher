import pytest

from ai_watcher.templates import render_template


def test_simple_substitution() -> None:
    assert render_template("x={{ a }}", {"a": "1"}) == "x=1"


def test_nested_path() -> None:
    ctx = {"steps": {"s": {"stdout": "out"}}}
    assert render_template("{{ steps.s.stdout }}", ctx) == "out"


def test_missing_key() -> None:
    with pytest.raises(KeyError):
        render_template("{{ missing }}", {})
