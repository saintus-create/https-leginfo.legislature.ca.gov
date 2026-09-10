"""Storage tests: schema creation, loading, and full-text search."""

from __future__ import annotations

import sqlite3

import pytest

from leginfo import store

RECORDS = [
    {
        "kind": "section",
        "uid": "GOV:7921.000",
        "code": "GOV",
        "section": "7921.000",
        "citation": "GOV § 7921.000",
        "ordinal": 0,
        "text": "In enacting this division, the Legislature finds and declares that access "
        "to information concerning the conduct of the people's business is a "
        "fundamental and necessary right of every person in this state.",
        "history": "(History: Added by Stats. 2021, Ch. 614, Sec. 2. (AB 473).)",
        "repealed": 0,
        "division": "1. GENERAL",
        "part": None,
        "title": "1. GENERAL",
        "chapter": "10. ACCESS TO PUBLIC RECORDS",
        "article": None,
        "path": "1. GENERAL > 10. ACCESS TO PUBLIC RECORDS",
        "char_count": 180,
    },
    {
        "kind": "section",
        "uid": "PEN:187",
        "code": "PEN",
        "section": "187",
        "citation": "PEN § 187",
        "ordinal": 1,
        "text": "(a) Murder is the unlawful killing of a human being, or a fetus, "
        "with malice aforethought.",
        "history": "(History: Amended by Stats. 2023, Ch. 260, Sec. 14. (SB 345).)",
        "repealed": 0,
        "division": "8. OF CRIMES AGAINST THE PERSON",
        "part": "1. Homicide",
        "title": None,
        "chapter": None,
        "article": None,
        "path": "8. OF CRIMES AGAINST THE PERSON > 1. Homicide",
        "char_count": 90,
    },
    {
        "kind": "heading",
        "code": "GOV",
        "number": "10",
        "title": "ACCESS TO PUBLIC RECORDS",
        "kind_label": "chapter",
        "range_start": "7920.000",
        "range_end": "7931.000",
        "path": "1. GENERAL > 10. ACCESS TO PUBLIC RECORDS",
        "ordinal": 0,
    },
]

# The heading fixture above uses "kind" for the discriminator, so give the
# toc record the column layout the loader expects.
TOC_RECORD = dict(RECORDS[2], kind="chapter")


@pytest.fixture()
def db(tmp_path):
    con = store.connect(tmp_path / "test.sqlite")
    store.init_db(con, drop=True)
    yield con
    con.close()


def test_load_and_query(db):
    count = store.load_law_records(db, RECORDS[:2] + [TOC_RECORD])
    assert count == 2

    row = store.get_section(db, "GOV", "7921.000")
    assert row is not None
    assert "conduct of the people's business" in row["text"]
    assert row["path"].endswith("ACCESS TO PUBLIC RECORDS")

    assert store.get_section(db, "GOV", "9999") is None
    assert db.execute("SELECT COUNT(*) FROM law_toc").fetchone()[0] == 1


def test_search_returns_ranked_hits(db):
    store.load_law_records(db, RECORDS[:2] + [TOC_RECORD])
    store.rebuild_fts(db)

    hits = list(store.search_law(db, "murder"))
    assert hits, "expected at least one hit for 'murder'"
    assert hits[0].citation == "PEN § 187"
    assert "<mark>" in hits[0].snippet or "Murder" in hits[0].snippet

    scoped = list(store.search_law(db, "murder", code="GOV"))
    assert scoped == []

    public = list(store.search_law(db, "conduct of the people's business"))
    assert any(h.code == "GOV" for h in public)


def test_search_handles_operator_syntax(db):
    store.load_law_records(db, RECORDS[:2] + [TOC_RECORD])
    store.rebuild_fts(db)
    hits = list(store.search_law(db, "murder ORwidget", limit=5))
    assert isinstance(hits, list)


def test_stats(db):
    store.load_law_records(db, RECORDS[:2] + [TOC_RECORD])
    stats = store.db_stats(db)
    assert stats["law_sections"] == 2
    assert stats["law_toc"] == 1
    assert stats["statute_chars"] == 270
    assert stats["fts"] in {"yes", "no"}


def test_bill_roundtrip(db):
    from leginfo import store as store_module

    store_module.load_bill_records(
        db,
        "bills",
        [
            {
                "bill_id": "202520260AB1",
                "session_year": "2025",
                "session_num": "2026",
                "measure_type": "AB",
                "measure_num": "1",
                "measure_state": "I",
                "current_status": "In Committee",
            }
        ],
    )
    bill = store.get_bill(db, "202520260AB1")
    assert bill is not None
    assert bill["bill"]["measure_type"] == "AB"
    assert bill["versions"] == [] and bill["actions"] == []


def test_unknown_bill_table_rejected(db):
    with pytest.raises(KeyError):
        store.load_bill_records(db, "not_a_table", [{"x": 1}])


def test_init_db_is_idempotent(db):
    store.init_db(db)
    store.init_db(db)
    assert db.execute("SELECT COUNT(*) FROM law_sections").fetchone()[0] == 0
    assert isinstance(db, sqlite3.Connection)
