# California Legislative Information — dataset

A local, queryable copy of the data behind **<https://leginfo.legislature.ca.gov>**:
the 29 California statutory codes plus the Constitution, structured section by
section, with full-text search — and a repeatable pipeline that can also pull
every bill since 1999 from the Legislature's official bulk feed.

The data is public domain. Pursuant to [Government Code § 10248.5], information
described in Gov. Code § 10248 and published on the site is in the public domain
and the State of California retains no copyright in it.

[Government Code § 10248.5]: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=10248.5

## What's in the box today

| | |
|---|---|
| **Codes** | 30 (29 statutory codes + the California Constitution) |
| **Sections of law** | **162,324** |
| **Table-of-contents nodes** | 24,233 (division / part / title / chapter / article) |
| **Statutory text** | 190,142,578 characters (~190 MB of law) |
| **Committed snapshot** | `data/law/*.jsonl.gz` — 51 MB, one gzip file per code |
| **Upstream "last updated"** | per code, most between Jul–Sep 2026 |

Largest codes: Government (21,863 sections), Health & Safety (17,730), Education
(11,569), Business & Professions (10,521), Water (10,131).

Bills are **not** in the committed snapshot — only because the sandbox this was
built in cannot reach `downloads.leginfo.legislature.ca.gov`. The importer is
written and tested against the published schema; one command fills it in (below).

## Quickstart

```bash
# 1. Structured snapshot + manifest (downloads the law text, parses it)
python3 -m leginfo collect-law

# 2. Queryable database with full-text search (data/leginfo.sqlite)
python3 -m leginfo build-db

# 3. Use it
python3 -m leginfo search "public records act" --limit 5
python3 -m leginfo section GOV 7921.000
python3 -m leginfo stats
python3 -m leginfo verify
```

No install step is required — the pipeline is standard-library Python 3.9+.
(`make law`, `make db`, `make search Q="..."` do the same thing; `make test`
runs the suite, which does need `pytest`.)

```python
from leginfo import store

con = store.connect("data/leginfo.sqlite")
for hit in store.search_law(con, "imminent peril of death", code="PEN", limit=5):
    print(hit.citation, hit.snippet)
```

### Adding the bills

From any machine that can reach the Legislature's download site:

```bash
python3 -m leginfo import-bills                 # current session (~764 MB download)
python3 -m leginfo import-bills --session 2023  # a specific session
python3 -m leginfo import-bills --zip ~/pubinfo_2025.zip --no-text   # metadata only
```

That fills `bills`, `bill_versions` (with full bill text), `bill_actions`,
`bill_votes`, `bill_vote_details`, `bill_authors`, `bill_analyses`,
`legislators`, `locations` and `motions`, and extends full-text search to bills.

## Repository layout

```
src/leginfo/
  config.py             code metadata, session years, upstream URLs
  sources.py            downloaders (official bulk ZIP, GitHub law-text mirror)
  parse_codes_text.py   plain-text code → structured sections + TOC
  parse_bulk.py         official bulk archive: .dat tables + CAML bill/statute XML
  store.py              SQLite schema, loaders, FTS5 search
  pipeline.py           end-to-end steps (snapshot, database, bill import)
  cli.py                `python -m leginfo …`
data/
  law/<CODE>.jsonl.gz   committed snapshot: one JSON Lines record per line
  MANIFEST.json         provenance, per-code counts, SHA-256 of every snapshot
  leginfo.sqlite        derived database (gitignored, rebuilt in ~45 s)
docs/DATA.md            schema and query recipes
docs/SOURCES.md         where the data comes from and what to watch out for
tests/                  27 tests, including every parsing edge case found so far
```

## How the parsing works

The law text is not a tidy machine format, so `parse_codes_text.py` is a
paragraph-level state machine rather than a line splitter. Details worth knowing:

* **Nesting is learned, not assumed.** The Education Code starts at Title, the
  Evidence Code at Division, so each file's heading depth is inferred from the
  order heading kinds first appear.
* **History trailers are separated from law text.** All 162,432 trailers in the
  corpus open with `(History:` — matching that literal keeps body text like
  `(a) This section shall become operative...` out of the history field.
* **Format variants are handled:** section numbers with or without a trailing
  full stop, six-digit numbers (PUC 100000+), headings wrapped in brackets with
  the range on the next line, lettered Constitution articles (`ARTICLE XIII B`),
  fractional section numbers (`SEC. 6½.`), and interstate compacts restated
  inside a section with their own `ARTICLE` headings.
* **Nothing silently disappears.** 294 of ~1.1 M paragraphs are unclassified
  (mostly the Penal Code's uncodified 1872 preamble); 36 verbatim duplicate
  sections dropped; 658 collisions where two different bills created the same
  section number kept as `GOV:985` and `GOV:985#2`.

## Status of the bill importer

`parse_bulk.py` implements the real `pubinfo_<session>.zip` layout — flat
backtick-quoted `.dat` tables plus CAML XML content files referenced by relative
path — with column orders taken from the Legislature's own load scripts and
cross-checked against Open States' CA importer. It is exercised by tests against
synthetic archives built to that layout, but it has **not** yet been run against
a live download (this sandbox's egress is restricted to PyPI/npm/GitHub).
Expect to run `python3 -m leginfo import-bills --limit 50` once before trusting
a full import, and see `docs/SOURCES.md` for the schema cross-references.
