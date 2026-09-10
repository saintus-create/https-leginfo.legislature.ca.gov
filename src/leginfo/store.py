"""SQLite storage for the California Legislative Information dataset.

The database is the queryable form of the data: one file (``data/leginfo.sqlite``)
holding the 29 codes plus the Constitution, and — once the official bulk feed has
been imported — the bill tables as well.

Full-text search uses SQLite's FTS5 in *external content* mode, so the index
stores pointers into ``law_sections`` instead of a second copy of the statutory
text. If a Python build lacks FTS5, :func:`search_law` falls back to a LIKE scan
and says so, rather than failing.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable, Iterator

from .util import get_logger, read_jsonl_gz

__all__ = [
    "SCHEMA",
    "connect",
    "init_db",
    "load_law_records",
    "load_bill_records",
    "rebuild_fts",
    "search_law",
    "search_bills",
    "get_section",
    "get_bill",
    "db_stats",
    "fts_enabled",
]

LOG = get_logger()

SCHEMA = """
-- Metadata: source provenance, build time, row counts.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- The 29 statutory codes plus the Constitution.
CREATE TABLE IF NOT EXISTS codes (
    abbr          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    display_order INTEGER,
    source        TEXT,
    updated       TEXT,          -- "Last Updated by State of California"
    section_count INTEGER,
    heading_count INTEGER,
    char_count    INTEGER
);

-- One row per numbered section of law.
CREATE TABLE IF NOT EXISTS law_sections (
    uid        TEXT PRIMARY KEY,   -- "GOV:6250" / "CONS:I-1"
    code       TEXT NOT NULL,      -- "GOV"
    section    TEXT NOT NULL,      -- "6250"
    citation   TEXT,               -- "GOV § 6250"
    ordinal    INTEGER,            -- position within the code
    text       TEXT,
    history    TEXT,               -- "(History: Amended by Stats. ...)"
    repealed   INTEGER DEFAULT 0,
    division   TEXT,
    part       TEXT,
    title      TEXT,
    chapter    TEXT,
    article    TEXT,
    path       TEXT,               -- "Division 7 > Chapter 3.5"
    char_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_law_sections_code ON law_sections(code);
CREATE INDEX IF NOT EXISTS idx_law_sections_section ON law_sections(code, section);

-- Structural table of contents (division / part / title / chapter / article).
CREATE TABLE IF NOT EXISTS law_toc (
    code        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    number      TEXT,
    title       TEXT,
    range_start TEXT,
    range_end   TEXT,
    path        TEXT,
    ordinal     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_law_toc_code ON law_toc(code);

-- ---------------------------------------------------------------- bills
CREATE TABLE IF NOT EXISTS bills (
    bill_id               TEXT PRIMARY KEY,   -- "202520260AB1"
    session_year          TEXT,
    session_num           TEXT,
    measure_type          TEXT,               -- "AB", "SB", ...
    measure_num           TEXT,
    measure_state         TEXT,
    chapter_year          TEXT,
    chapter_type          TEXT,
    chapter_num           TEXT,
    latest_bill_version_id TEXT,
    active_flg            TEXT,
    current_location      TEXT,
    current_house         TEXT,
    current_status        TEXT,
    days_31st_in_print    TEXT,
    trans_update          TEXT
);
CREATE INDEX IF NOT EXISTS idx_bills_session ON bills(session_year, measure_type, measure_num);

CREATE TABLE IF NOT EXISTS bill_versions (
    bill_version_id TEXT PRIMARY KEY,
    bill_id         TEXT NOT NULL,
    version_num     INTEGER,
    action_date     TEXT,
    action          TEXT,
    request_num     TEXT,
    subject         TEXT,
    vote_required   TEXT,
    appropriation   TEXT,
    fiscal_committee TEXT,
    local_program   TEXT,
    substantive_changes TEXT,
    urgency         TEXT,
    taxlevy         TEXT,
    title           TEXT,
    digest          TEXT,
    text            TEXT,
    char_count      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_bill_versions_bill ON bill_versions(bill_id);

CREATE TABLE IF NOT EXISTS bill_actions (
    bill_history_id TEXT,
    bill_id         TEXT NOT NULL,
    action_date     TEXT,
    action          TEXT,
    action_sequence TEXT,
    action_code     TEXT,
    action_status   TEXT,
    primary_location TEXT,
    secondary_location TEXT,
    ternary_location TEXT,
    end_status      TEXT
);
CREATE INDEX IF NOT EXISTS idx_bill_actions_bill ON bill_actions(bill_id, action_date);

CREATE TABLE IF NOT EXISTS bill_votes (
    bill_id       TEXT NOT NULL,
    location_code TEXT,
    vote_date_time TEXT,
    vote_date_seq TEXT,
    motion_id     TEXT,
    ayes          INTEGER,
    noes          INTEGER,
    abstain       INTEGER,
    vote_result   TEXT,
    file_item_num TEXT,
    session_date  TEXT
);
CREATE INDEX IF NOT EXISTS idx_bill_votes_bill ON bill_votes(bill_id);

CREATE TABLE IF NOT EXISTS bill_vote_details (
    bill_id         TEXT NOT NULL,
    location_code   TEXT,
    legislator_name TEXT,
    vote_date_time  TEXT,
    vote_date_seq   TEXT,
    vote_code       TEXT,
    motion_id       TEXT,
    member_order    INTEGER,
    session_date    TEXT
);
CREATE INDEX IF NOT EXISTS idx_bill_vote_details_bill ON bill_vote_details(bill_id);

CREATE TABLE IF NOT EXISTS bill_authors (
    bill_version_id TEXT NOT NULL,
    type            TEXT,
    house           TEXT,
    name            TEXT,
    contribution    TEXT,
    committee_members TEXT,
    primary_author_flg TEXT
);
CREATE INDEX IF NOT EXISTS idx_bill_authors_version ON bill_authors(bill_version_id);

CREATE TABLE IF NOT EXISTS bill_analyses (
    analysis_id     TEXT,
    bill_id         TEXT NOT NULL,
    house           TEXT,
    analysis_type   TEXT,
    committee_code  TEXT,
    committee_name  TEXT,
    analysis_date   TEXT,
    amendment_date  TEXT,
    page_num        TEXT,
    text            TEXT
);
CREATE INDEX IF NOT EXISTS idx_bill_analyses_bill ON bill_analyses(bill_id);

CREATE TABLE IF NOT EXISTS legislators (
    district        TEXT,
    session_year    TEXT,
    legislator_name TEXT,
    house_type      TEXT,
    author_name     TEXT,
    first_name      TEXT,
    last_name       TEXT,
    party           TEXT,
    active_flg      TEXT
);

CREATE TABLE IF NOT EXISTS locations (
    session_year    TEXT,
    location_code   TEXT,
    location_type   TEXT,
    description     TEXT,
    long_description TEXT,
    active_flg      TEXT
);

CREATE TABLE IF NOT EXISTS motions (
    motion_id   TEXT PRIMARY KEY,
    motion_text TEXT
);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS law_fts USING fts5(
    code, section, text, history,
    content='law_sections', content_rowid='rowid',
    tokenize='porter unicode61'
);
CREATE VIRTUAL TABLE IF NOT EXISTS bill_fts USING fts5(
    bill_id, subject, title, text,
    content='bill_versions', content_rowid='rowid',
    tokenize='porter unicode61'
);
"""


def _has_fts5(con: sqlite3.Connection) -> bool:
    try:
        con.execute("CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x)")
        con.execute("DROP TABLE temp._fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def connect(path: str | os.PathLike[str], *, fast_build: bool = False) -> sqlite3.Connection:
    """Open (creating if needed) the dataset database."""
    path = os.fspath(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=OFF" if fast_build else "PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-262144")  # 256 MB
    return con


def init_db(con: sqlite3.Connection, *, drop: bool = False) -> None:
    """Create the schema. With ``drop``, start from an empty database."""
    if drop:
        con.executescript(
            """
            DROP TABLE IF EXISTS law_fts;
            DROP TABLE IF EXISTS bill_fts;
            DROP TABLE IF EXISTS law_sections;
            DROP TABLE IF EXISTS law_toc;
            DROP TABLE IF EXISTS codes;
            DROP TABLE IF EXISTS bill_versions;
            DROP TABLE IF EXISTS bill_actions;
            DROP TABLE IF EXISTS bill_votes;
            DROP TABLE IF EXISTS bill_vote_details;
            DROP TABLE IF EXISTS bill_authors;
            DROP TABLE IF EXISTS bill_analyses;
            DROP TABLE IF EXISTS bills;
            DROP TABLE IF EXISTS legislators;
            DROP TABLE IF EXISTS locations;
            DROP TABLE IF EXISTS motions;
            DROP TABLE IF EXISTS meta;
            """
        )
    con.executescript(SCHEMA)
    try:
        con.executescript(_FTS_SCHEMA)
    except sqlite3.OperationalError as exc:  # pragma: no cover - depends on build
        LOG.warning("FTS5 unavailable (%s); falling back to LIKE search", exc)
    con.commit()


def fts_enabled(con: sqlite3.Connection) -> bool:
    """True when the FTS5 virtual tables exist."""
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('law_fts','bill_fts')"
    ).fetchall()
    return len(row) > 0


def load_law_records(con: sqlite3.Connection, records: Iterable[dict]) -> int:
    """Insert parsed law sections/headings. Returns the number of sections."""
    sections = 0
    headings = 0
    insert_section = """
        INSERT OR REPLACE INTO law_sections
        (uid, code, section, citation, ordinal, text, history, repealed,
         division, part, title, chapter, article, path, char_count)
        VALUES (:uid, :code, :section, :citation, :ordinal, :text, :history, :repealed,
                :division, :part, :title, :chapter, :article, :path, :char_count)
    """
    insert_heading = """
        INSERT INTO law_toc (code, kind, number, title, range_start, range_end, path, ordinal)
        VALUES (:code, :kind, :number, :title, :range_start, :range_end, :path, :ordinal)
    """
    for record in records:
        if record.get("kind") == "section":
            con.execute(insert_section, record)
            sections += 1
        else:
            con.execute(insert_heading, record)
            headings += 1
    con.commit()
    LOG.info("loaded %s sections, %s toc nodes", f"{sections:,}", f"{headings:,}")
    return sections


def load_law_directory(con: sqlite3.Connection, directory: str | os.PathLike[str]) -> int:
    """Load every ``<CODE>.jsonl.gz`` snapshot in ``directory``."""
    directory = os.fspath(directory)
    total = 0
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".jsonl.gz"):
            continue
        code = name.split(".")[0]
        records = list(read_jsonl_gz(os.path.join(directory, name)))
        total += load_law_records(con, records)
        LOG.info("  %s: %s records", code, f"{len(records):,}")
    return total


_BILL_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "bills": (
        "bill_id", "session_year", "session_num", "measure_type", "measure_num",
        "measure_state", "chapter_year", "chapter_type", "chapter_num",
        "latest_bill_version_id", "active_flg", "current_location", "current_house",
        "current_status", "days_31st_in_print", "trans_update",
    ),
    "bill_versions": (
        "bill_version_id", "bill_id", "version_num", "action_date", "action",
        "request_num", "subject", "vote_required", "appropriation", "fiscal_committee",
        "local_program", "substantive_changes", "urgency", "taxlevy", "title",
        "digest", "text", "char_count",
    ),
    "bill_actions": (
        "bill_history_id", "bill_id", "action_date", "action", "action_sequence",
        "action_code", "action_status", "primary_location", "secondary_location",
        "ternary_location", "end_status",
    ),
    "bill_votes": (
        "bill_id", "location_code", "vote_date_time", "vote_date_seq", "motion_id",
        "ayes", "noes", "abstain", "vote_result", "file_item_num", "session_date",
    ),
    "bill_vote_details": (
        "bill_id", "location_code", "legislator_name", "vote_date_time",
        "vote_date_seq", "vote_code", "motion_id", "member_order", "session_date",
    ),
    "bill_authors": (
        "bill_version_id", "type", "house", "name", "contribution",
        "committee_members", "primary_author_flg",
    ),
    "bill_analyses": (
        "analysis_id", "bill_id", "house", "analysis_type", "committee_code",
        "committee_name", "analysis_date", "amendment_date", "page_num", "text",
    ),
    "legislators": (
        "district", "session_year", "legislator_name", "house_type", "author_name",
        "first_name", "last_name", "party", "active_flg",
    ),
    "locations": (
        "session_year", "location_code", "location_type", "description",
        "long_description", "active_flg",
    ),
    "motions": ("motion_id", "motion_text"),
}


def load_bill_records(con: sqlite3.Connection, table: str, records: Iterable[dict]) -> int:
    """Bulk-insert rows into one of the bill tables."""
    columns = _BILL_TABLE_COLUMNS.get(table)
    if columns is None:
        raise KeyError(f"unknown bill table: {table}")
    sql = "INSERT OR REPLACE INTO {tbl} ({cols}) VALUES ({placeholders})".format(
        tbl=table,
        cols=", ".join(columns),
        placeholders=", ".join(f":{c}" for c in columns),
    )
    count = 0
    batch: list[dict] = []
    for record in records:
        row = {c: record.get(c) for c in columns}
        batch.append(row)
        if len(batch) >= 5000:
            con.executemany(sql, batch)
            count += len(batch)
            batch.clear()
    if batch:
        con.executemany(sql, batch)
        count += len(batch)
    con.commit()
    return count


def rebuild_fts(con: sqlite3.Connection) -> None:
    """(Re)build the full-text indexes from the content tables."""
    if not fts_enabled(con):
        LOG.warning("FTS5 not available — skipping index build")
        return
    con.execute("INSERT INTO law_fts(law_fts) VALUES('rebuild')")
    con.execute("INSERT INTO bill_fts(bill_fts) VALUES('rebuild')")
    con.execute("INSERT INTO law_fts(law_fts) VALUES('optimize')")
    con.commit()
    LOG.info("full-text indexes rebuilt")


@dataclass
class LawHit:
    """One full-text search result."""

    uid: str
    code: str
    section: str
    citation: str
    snippet: str
    score: float


def _match_expression(query: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression."""
    query = query.strip()
    if not query:
        return '""'
    if re.search(r'\b(AND|OR|NOT|NEAR)\b|"|\*', query):
        return query
    terms = [t for t in re.split(r"\s+", query) if t]
    return " ".join(f'"{t.replace(chr(34), "")}"' for t in terms)


def search_law(
    con: sqlite3.Connection,
    query: str,
    *,
    code: str | None = None,
    limit: int = 20,
) -> Iterator[LawHit]:
    """Full-text search over statutory text (falls back to LIKE without FTS5)."""
    limit = max(1, min(limit, 200))
    if fts_enabled(con):
        sql = """
            SELECT s.uid, s.code, s.section, s.citation,
                   snippet(law_fts, 2, '<mark>', '</mark>', ' … ', 40) AS snippet,
                   bm25(law_fts, 4.0, 1.0, 1.0, 0.5) AS score
            FROM law_fts
            JOIN law_sections s ON s.rowid = law_fts.rowid
            WHERE law_fts MATCH ?
        """
        params: list = [_match_expression(query)]
        if code:
            sql += " AND s.code = ?"
            params.append(code.upper())
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        for row in con.execute(sql, params):
            yield LawHit(
                uid=row["uid"],
                code=row["code"],
                section=row["section"],
                citation=row["citation"],
                snippet=row["snippet"],
                score=row["score"],
            )
        return

    # Fallback: slow but always available.
    like = f"%{query}%"
    sql = "SELECT * FROM law_sections WHERE text LIKE ?"
    params = [like]
    if code:
        sql += " AND code = ?"
        params.append(code.upper())
    sql += " LIMIT ?"
    params.append(limit)
    for row in con.execute(sql, params):
        yield LawHit(
            uid=row["uid"],
            code=row["code"],
            section=row["section"],
            citation=row["citation"],
            snippet=row["text"][:240],
            score=0.0,
        )


def search_bills(
    con: sqlite3.Connection,
    query: str,
    *,
    session_year: str | None = None,
    limit: int = 20,
) -> Iterator[sqlite3.Row]:
    """Full-text search over bill subjects, titles and text."""
    limit = max(1, min(limit, 200))
    if not fts_enabled(con):
        raise RuntimeError("bill search requires FTS5 support in this SQLite build")
    sql = """
        SELECT v.bill_id, v.bill_version_id, v.subject, v.title,
               snippet(bill_fts, 3, '<mark>', '</mark>', ' … ', 40) AS snippet,
               bm25(bill_fts, 1.0, 2.0, 2.0, 1.0) AS score
        FROM bill_fts
        JOIN bill_versions v ON v.rowid = bill_fts.rowid
        WHERE bill_fts MATCH ?
    """
    params: list = [_match_expression(query)]
    if session_year:
        sql += " AND v.bill_id LIKE ?"
        params.append(f"{session_year}%")
    sql += " ORDER BY score LIMIT ?"
    params.append(limit)
    yield from con.execute(sql, params)


def get_section(con: sqlite3.Connection, code: str, section: str) -> sqlite3.Row | None:
    """Fetch one section, e.g. ``get_section(con, "GOV", "6250")``."""
    return con.execute(
        "SELECT * FROM law_sections WHERE code = ? AND section = ?",
        (code.upper(), section),
    ).fetchone()


def get_bill(con: sqlite3.Connection, bill_id: str) -> dict | None:
    """Fetch a bill with its versions, actions and vote summaries."""
    bill = con.execute("SELECT * FROM bills WHERE bill_id = ?", (bill_id,)).fetchone()
    if bill is None:
        return None
    return {
        "bill": dict(bill),
        "versions": [
            dict(r)
            for r in con.execute(
                "SELECT * FROM bill_versions WHERE bill_id = ? ORDER BY version_num", (bill_id,)
            )
        ],
        "actions": [
            dict(r)
            for r in con.execute(
                "SELECT * FROM bill_actions WHERE bill_id = ? ORDER BY action_date, action_sequence",
                (bill_id,),
            )
        ],
        "votes": [
            dict(r)
            for r in con.execute(
                "SELECT * FROM bill_votes WHERE bill_id = ? ORDER BY vote_date_time", (bill_id,)
            )
        ],
    }


def db_stats(con: sqlite3.Connection) -> dict[str, int | str]:
    """Row counts and database size — the headline numbers for the dataset."""
    def count(table: str) -> int:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    stats = {
        "codes": count("codes"),
        "law_sections": count("law_sections"),
        "law_toc": count("law_toc"),
        "bills": count("bills"),
        "bill_versions": count("bill_versions"),
        "bill_actions": count("bill_actions"),
        "bill_votes": count("bill_votes"),
        "bill_vote_details": count("bill_vote_details"),
        "bill_authors": count("bill_authors"),
        "bill_analyses": count("bill_analyses"),
        "legislators": count("legislators"),
        "fts": "yes" if fts_enabled(con) else "no",
    }
    stats["statute_chars"] = con.execute("SELECT COALESCE(SUM(char_count), 0) FROM law_sections").fetchone()[0]
    return stats
