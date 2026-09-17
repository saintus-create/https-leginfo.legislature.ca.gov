# Self-Help Guide data source

The `data/selfhelp/` snapshot is a structured local copy of the **California
Courts Self-Help Guide**, published by the Judicial Branch of California at
<https://selfhelp.courts.ca.gov/>.

While `data/law/` holds the statutes themselves (the *black-letter law*),
the Self-Help Guide is the court system's plain-language companion: it explains
**how to navigate court procedure** — what form to file, how to serve papers,
what to expect at a hearing, which deadlines apply, when you can ask for a fee
waiver. It is the resource that self-represented litigants actually read
before walking into a courthouse.

## Source

* **Publisher:** Judicial Branch of California / California Courts
* **URL:** <https://selfhelp.courts.ca.gov/>
* **Sitemap:** <https://selfhelp.courts.ca.gov/sitemap.xml> (two sitemap pages, ~1,000+ English URLs)
* **Licence:** As a work of the California state government made available on
  the Judicial Branch website, content is in the public domain in the United
  States (17 U.S.C. § 105; Cal. Gov. Code § 10248.5). Site terms of use:
  <https://www.courts.ca.gov/conditions.htm>.
* **Last snapshot:** recorded in `data/selfhelp/MANIFEST.json`.

## Snapshot layout

```
data/selfhelp/
├── MANIFEST.json          # dataset metadata, page count, char count, form index
├── pages.jsonl.gz         # one JSON record per page (gzip-compressed JSONL)
├── selfhelp.sqlite        # SQLite database with pages, forms, links, FTS5 index (build-db)
└── cache/                 # source markdown cache the snapshot was built from
    ├── _index.jsonl       # url -> .md file mapping with fetch metadata
    └── <slug>.md          # markdown-rendered content per page
```

### Page record schema

Each line in `pages.jsonl.gz` is a JSON object:

| field | type | description |
|---|---|---|
| `kind` | string | Always `"selfhelp-guide-page"`. |
| `url` | string | Canonical URL of the page. |
| `path` | string | URL path component (e.g. `/divorce/start-divorce`). |
| `slug` | string | Filesystem-safe slug derived from the path. |
| `title` | string | Page `<h1>`/`<title>` text. |
| `text` | string | Clean plain-text body (markdown links/formatting stripped). |
| `headings` | array | `{level, title}` pairs extracted from ATX headings. |
| `internal_links` | array | `{label, url}` links to other selfhelp.courts.ca.gov pages. |
| `external_links` | array | `{label, url}` links off-site (courts.ca.gov, external PDFs, etc.). |
| `forms_referenced` | array | Judicial Council form numbers mentioned (e.g. `FL-300`, `DV-100`). |
| `glossary_terms` | array | Inline-defined terms the site bolds with four asterisks. |
| `sha256` | string | SHA-256 digest of the cleaned plain-text body. |
| `fetched_at` | string | ISO-8601 timestamp of the fetch. |
| `lang` | string | `"en"` (Spanish `/es/` pages are excluded). |
| `status` | int | HTTP status code of the fetch. |
| `char_count` | int | Length of `text` in characters. |

## Collection

The snapshot is built by `python -m selfhelp collect`. Two modes:

```bash
# 1. From a local markdown cache (used inside restricted-egress environments).
#    Populate data/selfhelp/cache/_index.jsonl + <slug>.md files, then:
make selfhelp

# 2. Live crawl — where outbound HTTPS to selfhelp.courts.ca.gov is permitted,
#    the crawler will BFS the site from seed URLs, converting HTML to markdown,
#    and following internal links up to a page cap.
make selfhelp-live            # defaults to 1,500 pages; set MAX_PAGES to change
```

The live crawler requires the optional `markdownify` package for best results,
falling back to a regex-based HTML stripper when it isn't installed:

```bash
pip install markdownify
```

Building the queryable database and searching:

```bash
make selfhelp-db
make search-selfhelp Q="fee waiver"
python -m selfhelp page /divorce
```

## Network notes (sandbox)

In this repository's build environment (Arena/E2B), outbound TLS to most
Fastly/Pantheon hosts — including selfhelp.courts.ca.gov — is blocked at the
network level. Direct `curl`/Python `requests` calls fail with
`SSL_ERROR_SYSCALL`. The committed cache was populated by fetching pages
through the platform's `fetch_page` proxy and includes ~40 seed pages (topic
landing pages and the highest-traffic step pages). The live crawler is included
for users running the repository outside the sandbox, or when egress is opened.

## Related datasets

* `data/law/` — California statutory codes (29 codes + the Constitution).
* The Judicial Council forms themselves live on
  <https://www.courts.ca.gov/forms.htm> (PDFs) and are not bundled in this
  snapshot; `forms_referenced` gives you the form numbers to look up.
* The docketx/us-pro-se Hugging Face dataset is a parallel cross-state pro-se
  corpus that includes the California Self-Help Guide content as a subset.
