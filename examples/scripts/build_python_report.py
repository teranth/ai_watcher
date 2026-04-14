#!/usr/bin/env python3
"""
Merge `artifacts/py_files.txt`, `artifacts/py_count.txt`, and optional
`artifacts/file_summaries.txt` into `artifacts/REPORT.md`.

Summaries file format: one line per file, ``PATH<TAB>DESCRIPTION`` (tabs preferred).
Paths in summaries are matched loosely to entries from the scan.
"""

from __future__ import annotations

import pathlib
import sys


def _read_int(path: pathlib.Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        return 0


def _load_summaries(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            p, _, desc = line.partition("\t")
        else:
            parts = line.split(None, 1)
            p = parts[0]
            desc = parts[1] if len(parts) > 1 else ""
        key = p.strip().lstrip("./")
        out[key] = desc.strip()
        out[p.strip()] = desc.strip()
    return out


def main() -> int:
    root = pathlib.Path.cwd()
    art = root / "artifacts"
    art.mkdir(parents=True, exist_ok=True)

    py_files = art / "py_files.txt"
    count_file = art / "py_count.txt"
    summ_file = art / "file_summaries.txt"
    report_path = art / "REPORT.md"

    n = _read_int(count_file)
    paths: list[str] = []
    if py_files.exists():
        paths = [ln.strip().lstrip("./") for ln in py_files.read_text(encoding="utf-8").splitlines() if ln.strip()]

    summaries = _load_summaries(summ_file)

    lines: list[str] = [
        "# Python file report",
        "",
        f"*Working directory: `{root}`*",
        "",
    ]

    if n == 0:
        lines += [
            "No `.py` files were found (after exclusions such as `.venv/` and `.git/`).",
            "",
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(report_path.read_text(encoding="utf-8"))
        return 0

    lines += [
        f"**Total Python files:** {n}",
        "",
        "## Files",
        "",
        "| Path | One-line description |",
        "|------|----------------------|",
    ]

    for p in paths:
        desc = summaries.get(p) or summaries.get(f"./{p}") or "_(no summary — Copilot step skipped or output missing)_"
        lines.append(f"| `{p}` | {desc} |")

    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
