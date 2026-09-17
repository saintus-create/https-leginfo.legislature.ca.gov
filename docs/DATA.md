# Data dictionary

Two datasets live in `data/`:

* `data/law/` — California statutory codes (29 codes + the Constitution), from LegInfo.
* `data/selfhelp/` — the California Courts **Self-Help Guide** (plain-language
  procedural guidance for self-represented litigants), from selfhelp.courts.ca.gov.

Build the databases from the snapshots (45 s for law, ~1 s for selfhelp):

```bash
make db           # → data/leginfo.sqlite  (~390 MB)
make selfhelp-db  # → data/selfhelp/selfhelp.sqlite  (~250 KB)
```

See `docs/SOURCES.md` and `docs/SELFHELP-SOURCES.md` for upstream provenance.

Everything lives in `data/leginfo.sqlite` (SQLite, ~390 MB, rebuildable from
`data/law/` in ~45 s). The committed snapshot in `data/law/` is the canonical
copy; the database is derived.

## On-disk snapshot format

`data/law/<CODE>.jsonl.gz` — gzip-compressed [JSON Lines], one record per line,
two record types distinguished by `kind`. Section records come first, then the
table-of-contents nodes for that code.

```jsonc
// section
{"kind":"section","code":"GOV","section":"7921.000","uid":"GOV:7921.000",
 "citation":"GOV § 7921.000","ordinal":15872,
 "text":"In enacting this division, the Legislature …",
 "history":"(History: Added by Stats. 2021, Ch. 614, Sec. 2. (AB 473) …)",
 "repealed":false,"division":"1. GENERAL","part":null,"title":"1. GENERAL",
 "chapter":"10. ACCESS TO PUBLIC RECORDS","article":null,
 "path":"1. GENERAL > 10. ACCESS TO PUBLIC RECORDS","char_count":180}

// toc node
{"kind":"chapter","code":"GOV","number":"10","title":"ACCESS TO PUBLIC RECORDS",
 "range_start":"7920.000","range_end":"7931.000",
 "path":"1. GENERAL > 10. ACCESS TO PUBLIC RECORDS","ordinal":412}
```

[JSON Lines]: https://jsonlines.org/

Stream one code without decompressing it to disk:

```bash
gzcat data/law/PEN.jsonl.gz | jq -c 'select(.kind=="section" and .section=="187")'
```

## Tables

### `law_sections` — 162,324 rows

| column | type | notes |
|---|---|---|
| `uid` | TEXT PK | `GOV:7921.000`; Constitution uses the article: `CONS:XIIIB-1` |
| `code` | TEXT | `GOV`, `PEN`, …, `CONS`. See `codes` table |
| `section` | TEXT | `7921.000`, `187`, `6½` |
| `citation` | TEXT | `GOV § 7921.000`, `Cal. Const. art. XIII B, § 1` |
| `ordinal` | INT | position within the code, ordered numerically |
| `text` | TEXT | operative statutory text, paragraphs joined by blank lines |
| `history` | TEXT | `(History: Amended by Stats. 2023, Ch. 260, Sec. 14. (SB 345).)` |
| `repealed` | INT | 1 when the section has no operative text and its history says repealed/expired |
| `division`/`part`/`title`/`chapter`/`article` | TEXT | `"10. ACCESS TO PUBLIC RECORDS"` |
| `path` | TEXT | breadcrumb, ` > ` separated |
| `char_count` | INT | length of `text` |

Indexes: `code`, `(code, section)`. Full-text index: `law_fts` (FTS5, external
content → no second copy of the text), columns `code`, `section`, `text`, `history`.

### `law_toc` — 24,233 rows

Structural nodes with `kind` (`division`, `part`, `title`, `chapter`, `article`,
`subdivision`), `number`, `title`, `range_start`/`range_end`, `path`, `ordinal`.
Useful for rendering a browsable tree before a UI exists.

### `codes` — 30 rows

`abbr`, `name`, `display_order`, `source`, `updated` (the Legislature's own
"Last Updated" stamp), `section_count`, `heading_count`, `char_count`.

### Bill tables (empty until `import-bills` is run)

| table | grain | key columns |
|---|---|---|
| `bills` | one row per bill | `bill_id` (`202520260AB1`), `session_year`, `measure_type`, `measure_num`, `chapter_num`, `current_location`, `current_status` |
| `bill_versions` | one row per version | `bill_version_id`, `bill_id`, `version_num`, `action_date`, `subject`, `title`, `digest`, `text` |
| `bill_actions` | one row per action | `bill_id`, `action_date`, `action`, `action_code`, `action_status`, `end_status` |
| `bill_votes` | one row per roll call | `bill_id`, `location_code`, `ayes`, `noes`, `abstain`, `vote_result` |
| `bill_vote_details` | one row per legislator per vote | `bill_id`, `legislator_name`, `vote_code`, `motion_id` |
| `bill_authors` | one row per author | `bill_version_id`, `type`, `house`, `name`, `contribution` |
| `bill_analyses` | one row per committee analysis | `bill_id`, `committee_name`, `analysis_date`, `text` |
| `legislators` | one row per member per session | `legislator_name`, `house_type`, `party`, `district` |
| `locations`, `motions` | lookup tables | `location_code`, `motion_id` |

### `meta`

`built_at`, `law_source`, `schema_version`, `bills_imported_at`, `bills_session`.

## Query recipes

```python
from leginfo import store
con = store.connect("data/leginfo.sqlite")

# full-text search (bm25 ranked, <mark>-highlighted snippets)
hits = store.search_law(con, "public records act", limit=10)

# exact section
row = store.get_section(con, "PEN", "187")

# everything in one chapter
rows = con.execute("""
    SELECT section, citation, text FROM law_sections
    WHERE code = ? AND chapter LIKE ? ORDER BY ordinal
""", ("GOV", "%ACCESS TO PUBLIC RECORDS%")).fetchall()

# codes by size
con.execute("""SELECT code, COUNT(*) n, SUM(char_count) chars
               FROM law_sections GROUP BY code ORDER BY n DESC""").fetchall()

# bills (after import-bills)
store.get_bill(con, "202520260AB1")   # → {"bill": …, "versions": […], "actions": […], "votes": […]}
list(store.search_bills(con, "artificial intelligence", limit=20))
```

Search syntax: plain words are ANDed and stemmed (`"records"` matches
"recording"); FTS5 operators work too — `"public records"`, `records OR files`,
`records NOT tax`, `NEAR(records privacy)`.

If a Python build lacks FTS5, `search_law` falls back to a `LIKE` scan (slower,
no ranking) instead of failing.

## `MANIFEST.json`

Provenance and integrity data for the snapshot: `generated_at`, `source`, and a
per-code entry with section/heading counts, character counts, source and snapshot
byte sizes, `sha256` of each `.jsonl.gz`, the Legislature's `updated_by_state`
stamp, and the parser's own QA counters (`unclassified_paragraphs`,
`duplicate_sections`, `uid_collisions`, `empty_sections`).

Verify integrity after a pull:

```bash
python3 - <<'EOF'
import json, hashlib, pathlib
m = json.load(open("data/MANIFEST.json"))
bad = [c["abbr"] for c in m["codes"]
       if hashlib.sha256(("data/law/" + c["file"]).encode() and
                         pathlib.Path("data/law", c["file"]).read_bytes()).hexdigest() != c["sha256"]]
print("mismatched:", bad or "none")
EOF
```

---

## Self-Help Guide (`data/selfhelp/`)

`data/selfhelp/pages.jsonl.gz` is a gzip-compressed JSON-Lines snapshot of the
California Courts Self-Help Guide. See `docs/SELFHELP-SOURCES.md` for the full
page-record schema. The on-disk snapshot is canonical; `selfhelp.sqlite` is
derived.

### Tables in `selfhelp.sqlite`

| table | rows | description |
|---|---|---|
| `pages` | one per page | `slug` (PK), `url`, `path`, `title`, `text`, `char_count`, `fetched_at`, `lang`, `sha256`, `status` |
| `page_forms` | form reference | `(slug, form)` — Judicial Council form numbers cited on each page (e.g. `FL-300`, `DV-100`, `FW-001`) |
| `page_links` | link | `(slug, target_url, label, kind)` — internal and external links |
| `page_terms` | glossary | `(slug, term)` — terms the site defines inline with boldface glossary markup |
| `pages_fts` | FTS5 index | full-text search over `title`, `text`, and `forms` (unicode61 tokenizer) |

### Query recipes

```bash
# Search
make search-selfhelp Q="fee waiver"
python -m selfhelp page /divorce
```

```python
import sqlite3
con = sqlite3.connect("data/selfhelp/selfhelp.sqlite")

# Full-text search
for row in con.execute("""
    SELECT p.slug, p.title, snippet(pages_fts, 2, '[', ']', '…', 8)
    FROM pages_fts JOIN pages p ON p.rowid = pages_fts.rowid
    WHERE pages_fts MATCH ? ORDER BY rank LIMIT 5
""", ("eviction",)):
    print(row)

# Pages that mention a given form
for row in con.execute("""
    SELECT p.path, p.title FROM pages p
    JOIN page_forms f ON f.slug = p.slug WHERE f.form = ?
""", ("FL-300",)):
    print(row)
```
