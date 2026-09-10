#!/usr/bin/env python3
"""Inspect the official LegInfo bulk ZIP and write a small schema probe.

The bulk file (``pubinfo_<session>.zip``, ~764 MB) contains tab-delimited
tables and hundreds of thousands of XML content files. This script never
extracts the whole archive: it reads the central directory, captures the
header and first rows of every table file, and keeps a handful of sample
content files, so the result is a few megabytes.

Usage:  python3 scripts/probe_bulk.py pubinfo_2025.zip probe_out/
"""

from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

MAX_SAMPLE_CONTENT_FILES = 4
MAX_HEADER_ROWS = 4
MAX_NAMES = 3000


def probe(zip_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "headers").mkdir(exist_ok=True)
    (out_dir / "samples").mkdir(exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        by_dir: Counter[str] = Counter()
        by_suffix: Counter[str] = Counter()
        total_uncompressed = 0
        names: list[str] = []

        for info in infos:
            name = info.filename
            total_uncompressed += info.file_size
            by_dir[name.split("/")[0] if "/" in name else "(root)"] += 1
            by_suffix[Path(name).suffix.lower() or "(none)"] += 1
            if len(names) < MAX_NAMES:
                names.append(name)

        (out_dir / "names.txt").write_text("\n".join(names), encoding="utf-8")

        tables = [i for i in infos if Path(i.filename).suffix.lower() in {".dat", ".tbl", ".txt", ".csv"}]
        content = [i for i in infos if Path(i.filename).suffix.lower() in {".lob", ".xml"}]

        headers_written = []
        for info in tables:
            target = out_dir / "headers" / (Path(info.filename).name + ".head")
            try:
                with zf.open(info) as handle:
                    rows = []
                    for _ in range(MAX_HEADER_ROWS):
                        line = handle.readline()
                        if not line:
                            break
                        rows.append(line.decode("utf-8", errors="replace").rstrip("\r\n"))
            except Exception as exc:  # noqa: BLE001 - probing should never abort
                rows = [f"!! could not read: {exc}"]
            target.write_text("\n".join(rows), encoding="utf-8")
            headers_written.append(
                {
                    "name": info.filename,
                    "uncompressed_size": info.file_size,
                    "sample_rows": len(rows),
                    "columns": len(rows[0].split("\t")) if rows and "\t" in rows[0] else None,
                    "quoted_fields": rows[0].startswith("`") if rows else None,
                }
            )

        sampled = []
        for info in content[:MAX_SAMPLE_CONTENT_FILES]:
            target = out_dir / "samples" / Path(info.filename).name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = zf.read(info)
            target.write_bytes(data)
            sampled.append({"name": info.filename, "size": len(data)})

    summary = {
        "zip": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "entries": len(infos),
        "total_uncompressed": total_uncompressed,
        "top_level_dirs": by_dir.most_common(30),
        "suffixes": by_suffix.most_common(20),
        "table_count": len(tables),
        "content_count": len(content),
        "tables": headers_written,
        "sampled_content": sampled,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    summary = probe(Path(argv[1]), Path(argv[2]))
    print(json.dumps({k: v for k, v in summary.items() if k not in {"tables"}}, indent=2))
    print(f"\ntables probed: {len(summary['tables'])}")
    for table in summary["tables"]:
        print(f"  {table['name']:<45} {table['uncompressed_size']:>12,} bytes  cols={table['columns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
