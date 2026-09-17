"""Command line entry point: ``python -m selfhelp <command>``.

    collect         build pages.jsonl.gz from a markdown cache (use --live to crawl the site directly)
    build-db        load pages.jsonl.gz into SQLite + FTS
    stats           database and snapshot statistics
    search          full-text search over the Self-Help Guide
    page            print one page by path (e.g. /divorce)
    verify          sanity-check the snapshot
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from leginfo.util import get_logger
from . import pipeline
from .config import SELFHELP_BASE_URL, SOURCE_NAME

DEFAULT_SELFHELP_DIR = Path(__file__).resolve().parents[2] / "data" / "selfhelp"

# Ensure the selfhelp logger is configured at import time.
get_logger("selfhelp")


def _data_dir(args: argparse.Namespace) -> Path:
    return Path(args.data_dir) if getattr(args, "data_dir", None) else DEFAULT_SELFHELP_DIR


def cmd_collect(args: argparse.Namespace) -> int:
    out_dir = _data_dir(args)
    cache_dir = Path(args.cache_dir) if args.cache_dir else out_dir / "cache"
    if args.live:
        pipeline.crawl_live(out_dir, max_pages=args.max_pages, politeness=args.politeness)
    else:
        if not cache_dir.exists():
            print(f"cache directory not found: {cache_dir}", file=sys.stderr)
            print("run with --live to crawl directly (needs network egress) or populate the cache first.", file=sys.stderr)
            return 1
        pipeline.build_snapshot_from_cache(cache_dir, out_dir)
    return 0


def cmd_build_db(args: argparse.Namespace) -> int:
    out_dir = _data_dir(args)
    db_path = Path(args.db) if args.db else out_dir / "selfhelp.sqlite"
    stats = pipeline.build_database(out_dir, db_path)
    print(f"{'table':<22}{'rows':>12}")
    for k, v in stats.items():
        print(f"{k:<22}{v if isinstance(v, str) else format(v, ','):>12}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    out_dir = _data_dir(args)
    manifest_path = out_dir / "MANIFEST.json"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text())
        print(f"source:       {m.get('source')}")
        print(f"generated_at: {m.get('generated_at')}")
        print(f"pages:        {m.get('pages')}")
        print(f"total_chars:  {m.get('total_chars'):,}")
        print(f"forms:        {len(m.get('forms_referenced', []))}")
    db = out_dir / "selfhelp.sqlite"
    if db.exists():
        import sqlite3
        con = sqlite3.connect(db)
        for tbl in ("pages", "page_forms", "page_links", "page_terms"):
            cnt = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"{tbl + ':':<22}{cnt:>12,}")
        con.close()
    return 0


def _fts_query(raw: str) -> str:
    """Convert a plain query string into an FTS5 MATCH expression.

    Multi-word queries use implicit AND; trailing ``*`` enables prefix matching
    on the last token.
    """
    toks = raw.strip().split()
    if not toks:
        return raw
    return " ".join(toks)


def cmd_search(args: argparse.Namespace) -> int:
    out_dir = _data_dir(args)
    db = out_dir / "selfhelp.sqlite"
    if not db.exists():
        print(f"no database at {db} — run: python -m selfhelp build-db", file=sys.stderr)
        return 1
    import sqlite3
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT p.slug, p.url, p.title, snippet(pages_fts, 2, '[', ']', '…', 12) "
            "FROM pages_fts JOIN pages p ON p.rowid = pages_fts.rowid "
            "WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?",
            (_fts_query(args.query), args.limit),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"search error: {exc}", file=sys.stderr)
        return 1
    if not rows:
        print("no matches")
        return 1
    for slug, url, title, snip in rows:
        print(f"{title}  ({slug})")
        print(f"  {url}")
        if snip:
            print(f"  {snip}\n")
    return 0


def cmd_page(args: argparse.Namespace) -> int:
    out_dir = _data_dir(args)
    db = out_dir / "selfhelp.sqlite"
    import sqlite3
    con = sqlite3.connect(db)
    path = args.path if args.path.startswith("/") else "/" + args.path
    row = con.execute("SELECT url, title, text FROM pages WHERE path = ? OR slug = ?", (path, args.path)).fetchone()
    if not row:
        # Try contains
        row = con.execute("SELECT url, title, text FROM pages WHERE path LIKE ? LIMIT 1", (f"%{args.path}%",)).fetchone()
    if not row:
        print(f"no page matching {args.path}", file=sys.stderr)
        return 1
    url, title, text = row
    print(f"# {title}")
    print(url)
    print("-" * 72)
    print(text[: args.chars] if args.chars else text)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    out_dir = _data_dir(args)
    manifest = json.loads((out_dir / "MANIFEST.json").read_text())
    print(f"source:       {manifest['source']}")
    print(f"generated_at: {manifest['generated_at']}")
    print(f"pages:        {manifest['pages']}")
    print(f"total_chars:  {manifest['total_chars']:,}")
    problems = []
    if manifest["pages"] < 25:
        problems.append(f"suspiciously few pages: {manifest['pages']}")
    pages_path = out_dir / "pages.jsonl.gz"
    empty = 0
    short = 0
    with gzip.open(pages_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if not r.get("text"):
                empty += 1
            elif len(r["text"]) < 200:
                short += 1
    print(f"empty:        {empty}")
    print(f"short (<200): {short}")
    if empty:
        problems.append(f"{empty} pages have empty text")
    # Spot checks
    import sqlite3
    db = out_dir / "selfhelp.sqlite"
    if db.exists():
        con = sqlite3.connect(db)
        print("\nspot checks:")
        for want in ("/divorce", "/eviction", "/small-claims", "/child-custody", "/traffic", "/appeals"):
            row = con.execute("SELECT slug, length(text) FROM pages WHERE path = ?", (want,)).fetchone()
            print(f"  {want:<20} {'ok ('+str(row[1])+' chars)' if row else 'MISSING'}")
            if not row:
                problems.append(f"missing expected topic page {want}")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nall checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m selfhelp",
        description=f"Build and query a local snapshot of the {SOURCE_NAME} ({SELFHELP_BASE_URL}).",
    )
    p.add_argument("--data-dir", help=f"dataset directory (default: {DEFAULT_SELFHELP_DIR})")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("collect", help="build pages.jsonl.gz from a cache directory (or crawl --live)")
    c.add_argument("--cache-dir", help="directory with .md page cache (default: data/selfhelp/cache)")
    c.add_argument("--live", action="store_true", help="crawl the site directly (needs network egress)")
    c.add_argument("--max-pages", type=int, default=1500)
    c.add_argument("--politeness", type=float, default=0.5)
    c.set_defaults(func=cmd_collect)

    c = sub.add_parser("build-db", help="load pages.jsonl.gz into SQLite + FTS")
    c.add_argument("--db", help="output SQLite path (default: data/selfhelp/selfhelp.sqlite)")
    c.set_defaults(func=cmd_build_db)

    c = sub.add_parser("stats", help="dataset statistics")
    c.set_defaults(func=cmd_stats)

    c = sub.add_parser("search", help="full-text search over pages")
    c.add_argument("query")
    c.add_argument("--limit", type=int, default=10)
    c.set_defaults(func=cmd_search)

    c = sub.add_parser("page", help="print a page by path/slug")
    c.add_argument("path")
    c.add_argument("--chars", type=int, help="max number of characters to print")
    c.set_defaults(func=cmd_page)

    c = sub.add_parser("verify", help="sanity-check the snapshot")
    c.set_defaults(func=cmd_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
