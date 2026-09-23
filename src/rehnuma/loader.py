"""Load ground-truth bill labels from JSON."""

from __future__ import annotations

import glob
from pathlib import Path

from rehnuma.schema import Bill


def load_bill(path: str | Path) -> Bill:
    # Explicit UTF-8: Windows defaults to cp1252 and would choke on Urdu text.
    return Bill.model_validate_json(Path(path).read_text(encoding="utf-8"))


def expand_paths(inputs: list[str]) -> list[Path]:
    """Accept files, directories and glob patterns. Globs are expanded here because
    PowerShell / cmd do not expand `*.json` the way bash does."""
    paths: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.json")))
        elif any(ch in item for ch in "*?["):
            paths.extend(Path(m) for m in sorted(glob.glob(item)))
        else:
            paths.append(p)
    return paths


def load_bills(inputs: list[str]) -> list[Bill]:
    return [load_bill(p) for p in expand_paths(inputs)]
