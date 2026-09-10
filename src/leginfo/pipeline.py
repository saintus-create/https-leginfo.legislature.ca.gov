"""End-to-end pipeline steps: build the law snapshot, build the database, import bills."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import store
from .config import CODES, CODES_BY_ABBR
from .parse_bulk import DAT_SCHEMAS, BulkArchive, open_bulk, read_dat
from .parse_codes_text import parse_code_directory, parse_code_file
from .util import get_logger, human_bytes, sha256_file, write_json, write_jsonl_gz

__all__ = ["build_law_snapshot", "build_database", "import_bills", "write_manifest"]

LOG = get_logger()

LAW_DIRNAME = "law"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_law_snapshot(
    codes_dir: str | os.PathLike[str],
    out_dir: str | os.PathLike[str],
    *,
    codes: Iterable[str] | None = None,
    source_label: str = "mirror:johnakelly-yahoo-com/california-codes",
) -> dict:
    """Parse the plain-text codes into per-code ``.jsonl.gz`` snapshots.

    Also writes ``<out_dir>/../MANIFEST.json`` style provenance via
    :func:`write_manifest` (called by the CLI after the fact).
    """
    codes_dir = Path(codes_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = [CODES_BY_ABBR[c] for c in codes] if codes else list(CODES)
    manifest: dict = {
        "generated_at": _now_iso(),
        "source": source_label,
        "codes": [],
    }

    for code in selected:
        path = codes_dir / f"{code.slug}.txt"
        if not path.exists():
            LOG.warning("missing source file for %s: %s", code.abbr, path)
            continue
        started = time.time()
        result = parse_code_file(path, code.abbr)
        target = out_dir / f"{code.abbr}.jsonl.gz"
        records = [*result.sections, *result.headings]
        count = write_jsonl_gz(target, records)
        char_count = sum(s["char_count"] for s in result.sections)
        entry = {
            "abbr": code.abbr,
            "name": code.name,
            "display_order": code.order,
            "source": source_label,
            "file": target.name,
            "records": count,
            "sections": len(result.sections),
            "headings": len(result.headings),
            "char_count": char_count,
            "source_file": path.name,
            "source_bytes": path.stat().st_size,
            "snapshot_bytes": target.stat().st_size,
            "sha256": sha256_file(target),
            "updated_by_state": result.updated,
            "parse_seconds": round(time.time() - started, 2),
        }
        entry.update(result.stats.as_dict())
        manifest["codes"].append(entry)
        LOG.info(
            "%-5s %6s sections, %5s headings -> %s (%s, %s source text, %.1fs)",
            code.abbr,
            f"{len(result.sections):,}",
            f"{len(result.headings):,}",
            target.name,
            human_bytes(target.stat().st_size),
            human_bytes(char_count),
            time.time() - started,
        )
    return manifest


def write_manifest(manifest: dict, path: str | os.PathLike[str]) -> Path:
    """Write the dataset manifest (provenance + per-code counts and checksums)."""
    return write_json(path, manifest)


def build_database(
    data_dir: str | os.PathLike[str],
    db_path: str | os.PathLike[str],
    *,
    manifest: dict | None = None,
    drop: bool = True,
) -> dict:
    """Load the JSONL snapshots into SQLite and rebuild the full-text indexes."""
    data_dir = Path(data_dir)
    law_dir = data_dir / LAW_DIRNAME
    con = store.connect(db_path, fast_build=True)
    store.init_db(con, drop=drop)

    LOG.info("loading law sections into %s", db_path)
    store.load_law_directory(con, law_dir)

    # Refresh the codes table from the manifest (or from what we just loaded).
    if manifest:
        codes = manifest.get("codes", [])
    else:
        codes = []
    if codes:
        con.executemany(
            """
            INSERT OR REPLACE INTO codes
            (abbr, name, display_order, source, updated, section_count, heading_count, char_count)
            VALUES (:abbr, :name, :display_order, :source, :updated_by_state,
                    :sections, :headings, :char_count)
            """,
            codes,
        )
    else:
        con.execute(
            """
            INSERT OR REPLACE INTO codes (abbr, name, section_count, char_count)
            SELECT code, code, COUNT(*), COALESCE(SUM(char_count), 0)
            FROM law_sections GROUP BY code
            """
        )
    for key, value in {
        "built_at": _now_iso(),
        "law_source": (manifest or {}).get("source", "unknown"),
        "schema_version": "1",
    }.items():
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    con.commit()

    started = time.time()
    store.rebuild_fts(con)
    LOG.info("fts build took %.1fs", time.time() - started)

    LOG.info("compacting database…")
    con.execute("VACUUM")
    con.commit()
    stats = store.db_stats(con)
    con.close()
    return stats


def _rows(archive: BulkArchive, table: str, filter_ids: set[str] | None = None) -> Iterable[dict]:
    """Stream rows of ``table``, optionally keeping only rows for the given bill ids."""
    path = archive.table_path(table)
    for row in read_dat(path):
        if filter_ids is not None and row.get("bill_id") not in filter_ids:
            continue
        yield row


def import_bills(
    zip_path: str | os.PathLike[str],
    db_path: str | os.PathLike[str],
    *,
    session_year: str | None = None,
    with_text: bool = True,
    limit: int | None = None,
) -> dict:
    """Import the bill tables from the official bulk archive into SQLite.

    ``session_year`` keeps the import to one session (e.g. "2025"); bill ids are
    prefixed with the session, so filtering is a prefix match on ``bill_id``.
    """
    con = store.connect(db_path, fast_build=True)
    store.init_db(con)

    counts: dict[str, int] = {}
    with open_bulk(zip_path) as archive:
        LOG.info("archive: %s (%s members)", Path(zip_path).name, f"{len(archive.names()):,}")

        bills_path = archive.table_path("BILL_TBL.dat")
        bill_rows = []
        for row in read_dat(bills_path):
            if session_year and not str(row.get("bill_id", "")).startswith(str(session_year)):
                continue
            bill_rows.append(row)
            if limit and len(bill_rows) >= limit:
                break
        counts["bills"] = store.load_bill_records(con, "bills", bill_rows)
        bill_ids = {r["bill_id"] for r in bill_rows}
        LOG.info("session filter %s -> %s bills", session_year or "all", f"{len(bill_ids):,}")

        # Versions (the expensive table: each row points at an XML content file).
        def version_rows() -> Iterable[dict]:
            emitted = 0
            for row in _rows(archive, "BILL_VERSION_TBL.dat", bill_ids):
                if with_text:
                    xml = archive.read_xml(row.get("xml_path"))
                    if xml:
                        from .parse_bulk import parse_bill_xml

                        parsed = parse_bill_xml(xml)
                        row["title"] = parsed.title
                        row["digest"] = parsed.digest
                        row["text"] = parsed.text
                row["char_count"] = len(row.get("text") or "")
                yield row
                emitted += 1
                if emitted % 20000 == 0:
                    LOG.info("  %s bill versions parsed...", f"{emitted:,}")

        counts["bill_versions"] = store.load_bill_records(con, "bill_versions", version_rows())

        for table, target in (
            ("BILL_HISTORY_TBL.dat", "bill_actions"),
            ("BILL_SUMMARY_VOTE_TBL.dat", "bill_votes"),
            ("BILL_DETAIL_VOTE_TBL.dat", "bill_vote_details"),
            ("BILL_VERSION_AUTHORS_TBL.dat", "bill_authors"),
            ("BILL_ANALYSIS_TBL.dat", "bill_analyses"),
        ):
            try:
                counts[target] = store.load_bill_records(
                    con, target, _rows(archive, table, bill_ids)
                )
            except FileNotFoundError as exc:
                LOG.warning("skipping %s: %s", table, exc)

        for table, target in (
            ("LEGISLATOR_TBL.dat", "legislators"),
            ("LOCATION_CODE_TBL.dat", "locations"),
            ("BILL_MOTION_TBL.dat", "motions"),
        ):
            try:
                counts[target] = store.load_bill_records(con, target, _rows(archive, table))
            except FileNotFoundError as exc:
                LOG.warning("skipping %s: %s", table, exc)

    con.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('bills_imported_at', ?)", (_now_iso(),)
    )
    if session_year:
        con.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('bills_session', ?)", (session_year,)
        )
    con.commit()
    store.rebuild_fts(con)
    counts.update(store.db_stats(con))
    con.close()
    return counts


def import_law_from_bulk(
    zip_path: str | os.PathLike[str],
    db_path: str | os.PathLike[str],
) -> dict:
    """Import the statutory codes straight from the official archive (XML content).

    This is the higher-fidelity alternative to the plain-text mirror: it keeps the
    Legislature's own division/title/part/chapter/article fields.
    """
    con = store.connect(db_path, fast_build=True)
    store.init_db(con)
    counts: dict[str, int] = {}
    with open_bulk(zip_path) as archive:
        try:
            counts["codes"] = store.load_bill_records(
                con,
                "codes",
                (
                    {
                        "abbr": r["code"],
                        "name": r["title"].lstrip("* ").strip(),
                        "source": "bulk:CODES_TBL.dat",
                    }
                    for r in _rows(archive, "CODES_TBL.dat")
                ),
            )
        except FileNotFoundError as exc:
            LOG.warning("skipping CODES_TBL.dat: %s", exc)

        def sections() -> Iterable[dict]:
            from .parse_bulk import iter_law_sections

            for index, row in enumerate(iter_law_sections(archive), start=1):
                yield {
                    "kind": "section",
                    "uid": f"{row['law_code']}:{row['section_num']}",
                    "code": row["law_code"],
                    "section": row["section_num"],
                    "citation": f"{row['law_code']} § {row['section_num']}",
                    "ordinal": index,
                    "text": row["content"],
                    "history": row.get("history", ""),
                    "repealed": 0,
                    "division": row.get("division"),
                    "part": row.get("part"),
                    "title": row.get("title"),
                    "chapter": row.get("chapter"),
                    "article": row.get("article"),
                    "path": " > ".join(
                        p for p in (row.get("division"), row.get("part"), row.get("chapter"), row.get("article")) if p
                    ),
                    "char_count": row["char_count"],
                }
                if index % 25000 == 0:
                    LOG.info("  %s law sections imported...", f"{index:,}")

        counts["law_sections"] = store.load_law_records(con, sections())

    con.commit()
    store.rebuild_fts(con)
    counts.update(store.db_stats(con))
    con.close()
    return counts
