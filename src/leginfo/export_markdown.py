"""Generate one clean Markdown document per law section for AutoRAG."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from .config import CODES


def _slug(value: str) -> str:
    return quote(value, safe=".-_")


def _records(path: Path) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def export_markdown(data_dir: str | Path, output_dir: str | Path) -> dict[str, int]:
    """Write a Markdown corpus from canonical law snapshots and return counts."""
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("**/*"):
        if path.is_file():
            path.unlink()

    section_count = 0
    largest = 0
    for code_meta in sorted(CODES, key=lambda c: c.order):
        code = code_meta.abbr
        code_name = code_meta.name
        sections = [r for r in _records(data_dir / "law" / f"{code}.jsonl.gz") if r.get("kind") == "section"]
        for row in sections:
            citation = _clean(row.get("citation"))
            text = _clean(row.get("text"))
            history = _clean(row.get("history"))
            lines = [f"# {citation}", "", f"**Code:** {code_name} ({code})", f"**Section:** {_clean(row.get('section'))}"]
            if row.get("path"):
                lines.append(f"**Location:** {_clean(row['path'])}")
            lines += ["", "## Text", "", text]
            if history:
                lines += ["", "## History", "", history]
            content = "\n".join(lines).rstrip() + "\n"
            path = output_dir / "codes" / code / f"{_slug(_clean(row['section']))}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            largest = max(largest, len(content.encode("utf-8")))
            section_count += 1

    readme = "# California Legislative Information\n\nThis directory contains one Markdown document per California statutory or constitutional section. The source snapshot is the `leginfo` repository's `data/law/*.jsonl.gz`.\n"
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    manifest = {"format": "markdown", "codes": len(CODES), "sections": section_count, "largest_bytes": largest}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


__all__ = ["export_markdown"]
