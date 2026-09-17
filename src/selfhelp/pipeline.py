"""Build the structured Self-Help Guide snapshot from fetched pages.

Two input modes:

* **Markdown cache.** Reads one ``.md`` file per page (the markdown-rendered
  text returned by the platform's ``fetch_page`` tool) from a directory.
  This is the mode used inside the Arena sandbox, where direct TLS to
  selfhelp.courts.ca.gov is blocked.

* **Live crawl.** Iterates seed URLs, fetches HTML directly (where network
  allows), converts to markdown via a bundled HTML->markdown converter if
  ``markdownify`` is installed, parses, and follows internal links up to a
  page cap. Used by ``python -m selfhelp collect --live``.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import urlsplit

from leginfo.util import atomic_write, get_logger, human_bytes, write_json, write_jsonl_gz
from .config import SELFHELP_BASE_URL, SOURCE_NAME
from .parse_page import PageRecord, is_selfhelp_url, parse_page, slug_from_url
from .sources import seed_urls

LOG = get_logger("selfhelp")


# ---------------------------------------------------------------------------
# Markdown-cache mode
# ---------------------------------------------------------------------------

def _iter_markdown_cache(cache_dir: Path) -> Iterator[tuple[str, str, dict]]:
    """Yield (url, markdown_text, meta) tuples from a directory cache.

    Cache layout::

        cache_dir/
            _index.jsonl          – one JSON object per cached page:
                                   {"url": "...", "title": "...", "fetched_at": "...",
                                    "status": 200, "file": "<slug>.md"}
            <slug>.md             – the markdown text of that page
    """
    index = cache_dir / "_index.jsonl"
    if not index.exists():
        # Fall back: one file named <url-encoded-path>.md; url = SELFHELP_BASE_URL/stem
        for md in sorted(cache_dir.glob("*.md")):
            slug = md.stem
            url = SELFHELP_BASE_URL + "/" + slug.replace("__home__", "")
            text = md.read_text(encoding="utf-8")
            yield url, text, {"file": md.name}
        return
    with open(index, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            meta = json.loads(line)
            url = meta["url"]
            md_path = cache_dir / meta["file"]
            if not md_path.exists():
                LOG.warning("cache: missing %s (listed in index)", md_path.name)
                continue
            text = md_path.read_text(encoding="utf-8")
            yield url, text, meta


def build_snapshot_from_cache(
    cache_dir: str | Path,
    out_dir: str | Path,
) -> dict:
    """Build data/selfhelp/pages.jsonl.gz + MANIFEST.json from a markdown cache."""
    cache_dir = Path(cache_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    total_chars = 0
    form_set: set[str] = set()
    seen_slugs: set[str] = set()

    for url, md_text, meta in _iter_markdown_cache(cache_dir):
        fetched_at = meta.get("fetched_at", datetime.now(timezone.utc).isoformat())
        title = meta.get("title", "")
        status = int(meta.get("status", 200))
        lang = meta.get("lang", "en")
        rec = parse_page(url, md_text, title=title, fetched_at=fetched_at, status=status, lang=lang)
        if rec.slug in seen_slugs:
            continue
        seen_slugs.add(rec.slug)
        d = rec.to_dict()
        records.append(d)
        total_chars += d["char_count"]
        form_set.update(d["forms_referenced"])

    # Sort by path for stable ordering.
    records.sort(key=lambda r: r["path"])

    pages_path = out_dir / "pages.jsonl.gz"
    write_jsonl_gz(pages_path, records)

    # Topic index: group by top-level path segment.
    topics: dict[str, int] = {}
    for r in records:
        top = r["path"].strip("/").split("/", 1)[0] or "__home__"
        topics[top] = topics.get(top, 0) + 1

    manifest = {
        "source": SELFHELP_BASE_URL + "/",
        "source_name": SOURCE_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": "markdown-cache",
        "cache_dir": str(cache_dir),
        "license_note": (
            "Public information published by the Judicial Branch of California; "
            "see https://www.courts.ca.gov/conditions.htm. As a work of the "
            "California state government, content is in the public domain in "
            "the United States (Cal. Gov. Code § 10248.5; 17 U.S.C. § 105)."
        ),
        "pages": len(records),
        "total_chars": total_chars,
        "forms_referenced": sorted(form_set),
        "topic_counts": dict(sorted(topics.items())),
        "snapshot_bytes": pages_path.stat().st_size,
    }
    write_json(out_dir / "MANIFEST.json", manifest)
    LOG.info(
        "selfhelp snapshot: %d pages, %s chars, %s on disk, %d forms referenced",
        manifest["pages"],
        f"{total_chars:,}",
        human_bytes(manifest["snapshot_bytes"]),
        len(manifest["forms_referenced"]),
    )
    return manifest


# ---------------------------------------------------------------------------
# Live-crawl mode
# ---------------------------------------------------------------------------

def _html_to_markdown(html_bytes: bytes) -> str:
    """Convert HTML to markdown. Uses markdownify if installed, else falls back
    to a very small stdlib stripper."""
    try:
        from markdownify import markdownify as md  # type: ignore
        return md(html_bytes.decode("utf-8", errors="replace"), heading_style="ATX")
    except ImportError:
        LOG.warning("markdownify not installed; using regex HTML stripper (install markdownify for better output)")
        text = html_bytes.decode("utf-8", errors="replace")
        text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<nav[\s\S]*?</nav>", " ", text, flags=re.I)
        text = re.sub(r"<header[\s\S]*?</header>", " ", text, flags=re.I)
        text = re.sub(r"<footer[\s\S]*?</footer>", " ", text, flags=re.I)
        text = re.sub(r"<h([1-6])[^>]*>([\s\S]*?)</h\1>", lambda m: "\n\n" + "#"*int(m.group(1)) + " " + re.sub(r"<[^>]+>", "", m.group(2)) + "\n\n", text, flags=re.I)
        text = re.sub(r"<li[^>]*>([\s\S]*?)</li>", lambda m: "\n- " + re.sub(r"<[^>]+>", "", m.group(1)), text, flags=re.I)
        text = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>([\s\S]*?)</a>", lambda m: f"[{re.sub(r'<[^>]+>','',m.group(2))}]({m.group(1)})", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text)
        return text


def crawl_live(
    out_dir: str | Path,
    *,
    max_pages: int = 1500,
    politeness: float = 0.5,
) -> dict:
    from collections import deque
    import time
    from urllib.parse import urldefrag, urljoin

    from .sources import fetch_direct

    out_dir = Path(out_dir)
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    seeds = seed_urls()
    seen: set[str] = set()
    q: deque[str] = deque(seeds)
    for s in seeds:
        seen.add(s.rstrip("/") or "/")

    index_fh = open(cache_dir / "_index.jsonl", "w", encoding="utf-8")
    fetched = 0
    total_chars = 0
    while q and fetched < max_pages:
        url = q.popleft()
        url_clean = url.rstrip("/") or "/"
        try:
            html = fetch_direct(url)
        except Exception as exc:
            LOG.warning("fetch failed: %s (%s)", url, exc)
            continue
        md = _html_to_markdown(html)
        # Extract <title>
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html.decode("utf-8", "replace"), flags=re.I)
        title = title_match.group(1).strip() if title_match else ""
        slug = slug_from_url(url)
        (cache_dir / f"{slug}.md").write_text(md, encoding="utf-8")
        meta = {
            "url": url_clean,
            "title": title,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status": 200,
            "file": f"{slug}.md",
        }
        index_fh.write(json.dumps(meta) + "\n")
        index_fh.flush()
        fetched += 1
        total_chars += len(md)

        # Enqueue internal links from the HTML (href="/foo")
        for href in re.findall(rb'''href=["']([^"']+)["']''', html):
            try:
                h = href.decode("utf-8", "replace")
            except Exception:
                continue
            if h.startswith("#") or h.startswith("mailto:") or h.startswith("javascript:"):
                continue
            full = urljoin(url, h)
            full, _ = urldefrag(full)
            if not is_selfhelp_url(full):
                continue
            if re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip|jpg|png|gif|css|js|ico|xml|rss)(\?|$)", full, re.I):
                continue
            p = urlsplit(full).path
            if p.startswith("/es/") or p.startswith("/sites/"):
                continue
            key = full.rstrip("/") or "/"
            if key not in seen:
                seen.add(key)
                q.append(full)
        if fetched % 25 == 0:
            LOG.info("crawled %d pages, q=%d, chars=%s", fetched, len(q), f"{total_chars:,}")
        time.sleep(politeness)
    index_fh.close()
    LOG.info("live crawl done: %d pages cached to %s", fetched, cache_dir)
    return build_snapshot_from_cache(cache_dir, out_dir)


# ---------------------------------------------------------------------------
# Database loader (for selfhelp)
# ---------------------------------------------------------------------------

def build_database(out_dir: str | Path, db_path: str | Path) -> dict:
    """Load pages.jsonl.gz into a SQLite database with FTS for search."""
    import sqlite3
    out_dir = Path(out_dir)
    db_path = Path(db_path)
    pages_path = out_dir / "pages.jsonl.gz"
    if not pages_path.exists():
        raise FileNotFoundError(f"no snapshot at {pages_path}; build one first")

    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE pages (
            slug TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            path TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            char_count INTEGER,
            fetched_at TEXT,
            lang TEXT,
            sha256 TEXT,
            status INTEGER
        );
        CREATE TABLE page_forms (
            slug TEXT NOT NULL,
            form TEXT NOT NULL,
            PRIMARY KEY (slug, form)
        );
        CREATE TABLE page_links (
            slug TEXT NOT NULL,
            target_url TEXT NOT NULL,
            label TEXT,
            kind TEXT NOT NULL   -- 'internal' or 'external'
        );
        CREATE TABLE page_terms (
            slug TEXT NOT NULL,
            term TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE pages_fts USING fts5(
            title, text, forms,
            tokenize='unicode61 remove_diacritics 2'
        );
        """
    )
    pages = 0
    forms = 0
    links = 0
    terms = 0
    import gzip as _gzip
    with _gzip.open(pages_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            con.execute(
                "INSERT INTO pages(slug,url,path,title,text,char_count,fetched_at,lang,sha256,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["slug"], r["url"], r["path"], r["title"], r["text"], r["char_count"], r["fetched_at"], r["lang"], r["sha256"], r["status"]),
            )
            rowid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            for f in r.get("forms_referenced", []):
                con.execute("INSERT INTO page_forms(slug,form) VALUES (?,?)", (r["slug"], f))
                forms += 1
            for l in r.get("internal_links", []):
                con.execute("INSERT INTO page_links(slug,target_url,label,kind) VALUES (?,?,?,?)", (r["slug"], l["url"], l.get("label", ""), "internal"))
                links += 1
            for l in r.get("external_links", []):
                con.execute("INSERT INTO page_links(slug,target_url,label,kind) VALUES (?,?,?,?)", (r["slug"], l["url"], l.get("label", ""), "external"))
                links += 1
            for t in r.get("glossary_terms", []):
                con.execute("INSERT INTO page_terms(slug,term) VALUES (?,?)", (r["slug"], t))
                terms += 1
            con.execute(
                "INSERT INTO pages_fts(rowid,title,text,forms) VALUES (?,?,?,?)",
                (rowid, r["title"], r["text"], " ".join(r.get("forms_referenced", []))),
            )
            pages += 1
    con.commit()
    con.close()
    return {"pages": pages, "form_refs": forms, "links": links, "glossary_terms": terms, "db_bytes": db_path.stat().st_size}
