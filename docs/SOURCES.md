# Where the data comes from

Two upstream sources, both public domain.

## 1. Official bulk feed — `downloads.leginfo.legislature.ca.gov`

<https://downloads.leginfo.legislature.ca.gov/> publishes one ZIP per legislative
session, `pubinfo_<session>.zip` (~764 MB), where `<session>` is the odd-numbered
start year of the two-year cycle (`pubinfo_2025.zip` = the 2025–2026 session).

It is the same database that powers leginfo.legislature.ca.gov and contains both
the statutory codes **and** every bill from 1999 forward.

**Layout**

* Flat, tab-delimited, backtick-quoted tables: `BILL_TBL.dat`,
  `BILL_VERSION_TBL.dat`, `BILL_HISTORY_TBL.dat`, `BILL_SUMMARY_VOTE_TBL.dat`,
  `BILL_DETAIL_VOTE_TBL.dat`, `BILL_VERSION_AUTHORS_TBL.dat`,
  `BILL_ANALYSIS_TBL.dat`, `BILL_MOTION_TBL.dat`, `LEGISLATOR_TBL.dat`,
  `LOCATION_CODE_TBL.dat`, `COMMITTEE_HEARING_TBL.dat`, `DAILY_FILE_TBL.dat`,
  `VETO_MESSAGE_TBL.dat`, `CODES_TBL.dat`, `LAW_TOC_TBL.dat`,
  `LAW_TOC_SECTIONS_TBL.dat`, `LAW_SECTION_TBL.dat`.
* CAML XML content files (`.lob` / `.xml`) for bill versions, committee analyses
  and statute bodies. `BILL_VERSION_TBL.dat` and `LAW_SECTION_TBL.dat` carry a
  column holding the *relative path* of each row's XML file.

**Column orders** used in `src/leginfo/parse_bulk.py` come from the Legislature's
own `pubinfo_load` MySQL scripts and were cross-checked against
[Ingramml/CA_Bills_part2](https://github.com/Ingramml/CA_Bills_part2)
(`Sqlfiles/*.sql`, a full `capublic` DDL dump) and
[Open States' CA importer](https://github.com/openstates/openstates-scrapers/blob/main/scrapers/ca/models.py).

Bill text sits in `//caml:Content` paragraphs; the Legislative Counsel's digest
sits in `//caml:DigestText` and is stored separately so it is not duplicated into
the bill text.

## 2. Nightly mirror — `github.com/johnakelly-yahoo-com/california-codes`

A nightly mirror that runs the script above and publishes the result as plain
text: one file per code in `codes/`, ~214 MB total for all 30. It is derived
entirely from the official feed, so provenance is unchanged — it is simply the
law text without the bills.

This is what the committed snapshot was built from, because the environment this
repo was set up in allows egress only to PyPI/npm/GitHub and cannot reach
`downloads.leginfo.legislature.ca.gov`. Refreshing from the official feed instead
is a one-liner:

```bash
python3 -m leginfo collect-law --bulk        # law text straight from the archive
python3 -m leginfo import-law-bulk           # or import statutes into SQLite directly
```

## What the mirror's text looks like

```
======================================================================
  Evidence Code
  State of California
======================================================================

Source: Official California Legislative Information
        https://downloads.leginfo.legislature.ca.gov/
Last Updated by State of California: November 27, 2025

DIVISION 2. WORDS AND PHRASES DEFINED [100. - 260.]

105.

"Action" includes a civil action and a criminal action.

(History: Enacted by Stats. 1965, Ch. 299.)
-------------------------------------------
```

`parse_codes_text.py` turns that into rows. It is a paragraph state machine, not
a line splitter, because of these real variants in the corpus:

| variant | example | where |
|---|---|---|
| heading range on the next line | `ARTICLE 2. PRESUMPTIONS` / `[600. - 668.]` | several codes |
| heading and range both bracketed | `[PART 1.7. HEALTH FACILITIES DISCLOSURE ACT] [440.10. - 440.50.]` | HSC |
| section number with no full stop | `1568.099` | HSC, GOV |
| six-digit section numbers | `100000.` | PUC, HSC |
| lettered Constitution articles | `ARTICLE XIII B GOVERNMENT SPENDING LIMITATION` | CONS |
| fractional section numbers | `SEC. 6½.` | CONS |
| `SECTION 1.` instead of `SEC. 1.` | first section of a Constitution article | CONS |
| embedded sub-document | Tahoe Compact's own `ARTICLE I.` inside GOV 66801 | GOV |
| bare numbers inside a section | census block lists inside ELEC 21445 | ELEC |

## Known limitations

* **Only active law.** The mirror publishes sections with `active_flg = 'Y'`, so
  repealed sections are absent rather than flagged. Example: the old Public
  Records Act at GOV § 6250 was recodified to § 7921.000 by the CPRA
  Recodification Act of 2021 and only the new number appears.
* **Bills are not in the committed snapshot** (see README). Run `import-bills`
  where the download host is reachable.
* **294 unclassified paragraphs** out of ~1.1 M, mostly the Penal Code's
  uncodified 1872 preamble ("Section One Hundred and Eighty-five. …"). Counted
  per code in `MANIFEST.json`.
* **658 duplicate section numbers** where two bills created the same number —
  both are kept, the second as `GOV:985#2`.
* **Bill importer untested against a live download.** Written to the published
  schema and exercised against synthetic archives; run
  `import-bills --limit 50` first on a machine with network access.

## Licence

Pursuant to Government Code § 10248.5, information described in Gov. Code
§ 10248 and made available on the Legislative Information website is in the
public domain; the State of California retains no copyright or other proprietary
interest in it. The code in this repository is offered under the same spirit.
