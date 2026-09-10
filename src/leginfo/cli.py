"""Command line entry point: ``python -m leginfo <command>``.

    collect-law     download the law text (mirror by default, official bulk with --bulk)
    build-db        load the JSONL snapshots into SQLite + full-text indexes
    import-bills    import bills from the official bulk archive
    stats           row counts for the database
    search          full-text search over statutes
    section         print one section, e.g. GOV 6250
    verify          sanity-check the parsed dataset
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import pipeline, store
from .config import CODES, CODES_BY_ABBR, bulk_zip_url, session_start_year
from .util import get_logger

LOG = get_logger()

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _data_dir(args: argparse.Namespace) -> Path:
    return Path(args.data_dir) if getattr(args, "data_dir", None) else DEFAULT_DATA_DIR


def cmd_collect_law(args: argparse.Namespace) -> int:
    """Download law text and write the structured JSONL snapshot."""
    data_dir = _data_dir(args)
    codes_dir = Path(args.codes_dir) if args.codes_dir else data_dir / "raw" / "mirror"

    if args.from_dir:
        codes_dir = Path(args.from_dir)
    elif args.bulk:
        from .sources import fetch_bulk

        zip_path = fetch_bulk(data_dir / "raw", session_year=args.session, force=args.force)
        from .parse_bulk import open_bulk
        from .sources import extract_bulk

        codes_dir = extract_bulk(zip_path, data_dir / "raw" / f"pubinfo_{args.session}")
    else:
        from .sources import fetch_mirror

        codes_dir = fetch_mirror(codes_dir.parent, force=args.force)

    manifest = pipeline.build_law_snapshot(
        codes_dir,
        data_dir / "law",
        codes=args.codes,
        source_label=(
            "bulk:downloads.leginfo.legislature.ca.gov"
            if args.bulk or args.from_dir and args.bulk
            else "mirror:johnakelly-yahoo-com/california-codes"
        ),
    )
    pipeline.write_manifest(manifest, data_dir / "MANIFEST.json")
    total_sections = sum(c["sections"] for c in manifest["codes"])
    total_chars = sum(c["char_count"] for c in manifest["codes"])
    LOG.info("snapshot: %s codes, %s sections, %s chars", len(manifest["codes"]), f"{total_sections:,}", f"{total_chars:,}")
    return 0


def cmd_build_db(args: argparse.Namespace) -> int:
    """Build the SQLite database from the JSONL snapshots."""
    data_dir = _data_dir(args)
    manifest_path = data_dir / "MANIFEST.json"
    manifest = None
    if manifest_path.exists():
        import json

        manifest = json.loads(manifest_path.read_text())
    stats = pipeline.build_database(data_dir, data_dir / "leginfo.sqlite", manifest=manifest)
    print(f"{'table':<20}{'rows':>14}")
    for key, value in stats.items():
        print(f"{key:<20}{value if isinstance(value, str) else format(value, ','):>14}")
    return 0


def cmd_import_bills(args: argparse.Namespace) -> int:
    """Import bills from the official bulk archive."""
    data_dir = _data_dir(args)
    if args.zip:
        zip_path = Path(args.zip)
    else:
        from .sources import fetch_bulk

        zip_path = fetch_bulk(data_dir / "raw", session_year=args.session, force=args.force)
    counts = pipeline.import_bills(
        zip_path,
        data_dir / "leginfo.sqlite",
        session_year=str(args.session) if args.session else None,
        with_text=not args.no_text,
        limit=args.limit,
    )
    for key, value in counts.items():
        print(f"{key:<20}{value if isinstance(value, str) else format(value, ','):>14}")
    return 0


def cmd_import_law_bulk(args: argparse.Namespace) -> int:
    """Import statutes directly from the official archive (higher fidelity)."""
    data_dir = _data_dir(args)
    if args.zip:
        zip_path = Path(args.zip)
    else:
        from .sources import fetch_bulk

        zip_path = fetch_bulk(data_dir / "raw", session_year=args.session, force=args.force)
    counts = pipeline.import_law_from_bulk(zip_path, data_dir / "leginfo.sqlite")
    for key, value in counts.items():
        print(f"{key:<20}{value if isinstance(value, str) else format(value, ','):>14}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Print database row counts."""
    data_dir = _data_dir(args)
    db = data_dir / "leginfo.sqlite"
    if not db.exists():
        print(f"no database at {db} — run: python -m leginfo build-db", file=sys.stderr)
        return 1
    con = store.connect(db)
    for key, value in store.db_stats(con).items():
        print(f"{key:<20}{value if isinstance(value, str) else format(value, ','):>14}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Full-text search the statutes."""
    data_dir = _data_dir(args)
    con = store.connect(data_dir / "leginfo.sqlite")
    hits = list(store.search_law(con, args.query, code=args.code, limit=args.limit))
    if not hits:
        print("no matches")
        return 1
    for hit in hits:
        print(f"{hit.citation}  (score {hit.score:.2f})")
        print(f"  {hit.snippet}\n")
    return 0


def cmd_section(args: argparse.Namespace) -> int:
    """Print a single section of law."""
    data_dir = _data_dir(args)
    con = store.connect(data_dir / "leginfo.sqlite")
    row = store.get_section(con, args.code, args.section)
    if row is None:
        print(f"{args.code} § {args.section} not found", file=sys.stderr)
        return 1
    print(f"{row['citation']}   {row['path']}")
    print("-" * 72)
    print(row["text"])
    if row["history"]:
        print(f"\n{row['history']}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Sanity-check the dataset: counts, spot checks, parse coverage."""
    data_dir = _data_dir(args)
    con = store.connect(data_dir / "leginfo.sqlite")
    problems: list[str] = []

    stats = store.db_stats(con)
    if stats["codes"] == 0:
        problems.append("no codes loaded")
    if stats["law_sections"] < 100_000:
        problems.append(f"suspiciously few sections: {stats['law_sections']}")

    missing_history = con.execute(
        "SELECT COUNT(*) FROM law_sections WHERE history IS NULL OR history = ''"
    ).fetchone()[0]
    empty_text = con.execute(
        "SELECT COUNT(*) FROM law_sections WHERE text IS NULL OR text = ''"
    ).fetchone()[0]
    dupes = con.execute(
        "SELECT COUNT(*) FROM (SELECT uid FROM law_sections GROUP BY uid HAVING COUNT(*) > 1)"
    ).fetchone()[0]

    print(f"{'check':<28}{'value':>14}")
    for key, value in stats.items():
        print(f"{key:<28}{value if isinstance(value, str) else format(value, ','):>14}")
    print(f"{'sections without history':<28}{missing_history:>14,}")
    print(f"{'sections with empty text':<28}{empty_text:>14,}")
    print(f"{'duplicate uids':<28}{dupes:>14,}")

    # Spot-check well-known sections.
    # GOV 6250 (the old Public Records Act) was recodified to 7921.000 by the
    # CPRA Recodification Act of 2021, so 7921.000 is the live section.
    spot_checks = [("GOV", "7921.000"), ("PEN", "187"), ("CIV", "1714"), ("VEH", "23152"), ("EVID", "352")]
    print("\nspot checks:")
    for code, section in spot_checks:
        row = store.get_section(con, code, section)
        ok = row is not None and len(row["text"] or "") > 40
        print(f"  {code} § {section:<8} {'ok' if ok else 'MISSING'}  {(row['text'][:56] + '…') if row and row['text'] else ''}")
        if not ok:
            problems.append(f"missing section {code} {section}")

    if empty_text:
        problems.append(f"{empty_text} sections have no text")
    if dupes:
        problems.append(f"{dupes} duplicate section uids")

    if problems:
        print("\nPROBLEMS:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nall checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m leginfo",
        description="Build and query a local copy of California Legislative Information data.",
    )
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("LEGINFO_DATA_DIR", str(DEFAULT_DATA_DIR)),
        help="dataset directory (default: ./data)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("collect-law", help="download law text and build the JSONL snapshot")
    p.add_argument("--bulk", action="store_true", help="use the official bulk archive instead of the mirror")
    p.add_argument("--from-dir", help="parse an existing directory of CA Code text files")
    p.add_argument("--codes-dir", help="where to cache downloaded source files")
    p.add_argument("--codes", nargs="*", choices=[c.abbr for c in CODES], help="limit to these codes")
    p.add_argument("--session", type=int, default=session_start_year(), help="session year for --bulk")
    p.add_argument("--force", action="store_true", help="re-download even if cached")
    p.set_defaults(func=cmd_collect_law)

    p = sub.add_parser("build-db", help="load snapshots into SQLite and build full-text indexes")
    p.set_defaults(func=cmd_build_db)

    p = sub.add_parser("import-bills", help="import bills from the official bulk archive")
    p.add_argument("--zip", help="path to an existing pubinfo_<session>.zip")
    p.add_argument("--session", type=int, default=session_start_year(), help="session start year")
    p.add_argument("--no-text", action="store_true", help="skip bill XML text (much faster)")
    p.add_argument("--limit", type=int, help="stop after N bills")
    p.add_argument("--force", action="store_true", help="re-download the archive")
    p.set_defaults(func=cmd_import_bills)

    p = sub.add_parser("import-law-bulk", help="import statutes from the official bulk archive")
    p.add_argument("--zip", help="path to an existing pubinfo_<session>.zip")
    p.add_argument("--session", type=int, default=session_start_year())
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_import_law_bulk)

    p = sub.add_parser("stats", help="database row counts")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("search", help="full-text search over statutes")
    p.add_argument("query")
    p.add_argument("--code", help="restrict to one code, e.g. GOV")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("section", help="print one section, e.g. `section GOV 6250`")
    p.add_argument("code")
    p.add_argument("section")
    p.set_defaults(func=cmd_section)

    p = sub.add_parser("verify", help="sanity-check the built dataset")
    p.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
