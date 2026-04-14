"""Safe `{{ name }}` templating with dotted lookups; no code evaluation."""

from __future__ import annotations

import re
from typing import Any

_VAR = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def render_template(template: str, context: dict[str, Any]) -> str:
    """Replace `{{ key }}` and `{{ a.b.c }}` using dict traversal."""

    def lookup(path: str) -> str:
        parts = path.split(".")
        cur: Any = context
        for p in parts:
            if isinstance(cur, dict):
                if p not in cur:
                    raise KeyError(path)
                cur = cur[p]
            else:
                raise KeyError(path)
        return str(cur) if cur is not None else ""

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        try:
            return lookup(key)
        except KeyError as e:
            raise KeyError(f"Missing template variable: {e}") from e

    return _VAR.sub(repl, template)


def render_optional(value: str | None, context: dict[str, Any]) -> str | None:
    if value is None:
        return None
    return render_template(value, context)
