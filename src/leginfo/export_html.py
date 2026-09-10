"""Generate a crawlable static HTML site from the law JSONL snapshots."""

from __future__ import annotations

import gzip
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from .config import CODES


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _slug(value: str) -> str:
    return quote(value, safe=".-_")


def _text(value: str | None) -> str:
    """Escape plain text while preserving paragraph breaks."""
    return "<br>\n".join(_esc(p) for p in (value or "").splitlines())


def _layout(title: str, canonical: str, body: str, description: str = "") -> str:
    desc = _esc(description or title)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{_esc(canonical)}">
<style>
:root {{ color-scheme: light; --ink:#17202a; --muted:#5d6d7e; --link:#145da0; --line:#d9e2ec; --paper:#fff; --bg:#f5f7fa; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif; }}
header,main,footer {{ max-width:960px; margin:auto; padding:1rem 1.25rem; }} header {{ border-bottom:1px solid var(--line); }}
main {{ background:var(--paper); margin-top:1.25rem; margin-bottom:1.25rem; padding:2rem 1.5rem; }}
a {{ color:var(--link); }} h1 {{ line-height:1.2; }} h2 {{ margin-top:2rem; }} .crumbs {{ color:var(--muted); font-size:.92rem; }}
.law-text {{ white-space:normal; }} .history {{ color:var(--muted); border-left:3px solid var(--line); padding-left:1rem; }}
.card {{ border:1px solid var(--line); border-radius:6px; padding:.8rem 1rem; margin:.65rem 0; }} footer {{ color:var(--muted); font-size:.85rem; }}
</style>
</head>
<body><header><a href="/">California Legislative Information</a></header><main>{body}</main><footer>Public-domain California statutory and constitutional text. Source: California Legislative Information.</footer></body>
</html>'''


def _records(path: Path) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def _section_url(code: str, section: str) -> str:
    return f"/codes/{_slug(code)}/{_slug(section)}.html"


def export_html(data_dir: str | Path, output_dir: str | Path, *, base_url: str = "") -> dict[str, int]:
    """Write a static site and return counts. Existing output is replaced."""
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    law_dir = data_dir / "law"
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("**/*"):
        if path.is_file():
            path.unlink()
    (output_dir / "codes").mkdir(parents=True, exist_ok=True)

    urls: list[str] = ["/"]
    code_cards: list[str] = []
    section_count = 0
    for code_meta in sorted(CODES, key=lambda c: c.order):
        code = code_meta.abbr
        records = list(_records(law_dir / f"{code}.jsonl.gz"))
        sections = [r for r in records if r.get("kind") == "section"]
        headings = [r for r in records if r.get("kind") != "section"]
        code_name = code_meta.name
        links: list[str] = []
        for row in sections:
            url = _section_url(code, row["section"])
            links.append(f'<div class="card"><a href="{url}"><strong>{_esc(row["citation"])}</strong></a></div>')
            body = f'''<div class="crumbs"><a href="/">Home</a> / <a href="/codes/{_slug(code)}.html">{_esc(code_name)}</a></div>
<h1>{_esc(row["citation"])}</h1>
<p><strong>Code:</strong> {_esc(code_name)}<br><strong>Location:</strong> {_esc(row.get("path") or "")}</p>
<article class="law-text"><h2>Text</h2><p>{_text(row.get("text"))}</p></article>'''
            if row.get("history"):
                body += f'<h2>History</h2><p class="history">{_text(row["history"])}</p>'
            previous = sections[row["ordinal"] - 1] if isinstance(row.get("ordinal"), int) and row["ordinal"] > 0 and row["ordinal"] - 1 < len(sections) else None
            if previous:
                body += f'<p><a rel="prev" href="{_section_url(code, previous["section"])}">Previous section</a></p>'
            section_path = output_dir / "codes" / code / f'{_slug(row["section"])}.html'
            section_path.parent.mkdir(parents=True, exist_ok=True)
            section_path.write_text(_layout(row["citation"], base_url.rstrip("/") + url, body, row.get("text", "")[:155]), encoding="utf-8")
            urls.append(url)
            section_count += 1
        code_url = f"/codes/{_slug(code)}.html"
        body = f'''<div class="crumbs"><a href="/">Home</a> / {_esc(code_name)}</div><h1>{_esc(code_name)} ({_esc(code)})</h1>
<p>{len(sections):,} sections. Browse the complete statutory text below.</p>{"".join(links)}'''
        (output_dir / "codes" / f"{code}.html").write_text(_layout(f"{code_name} ({code})", base_url.rstrip("/") + code_url, body), encoding="utf-8")
        urls.append(code_url)
        code_cards.append(f'<div class="card"><a href="{code_url}"><strong>{_esc(code_name)}</strong></a> ({code}) — {len(sections):,} sections</div>')

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = f'''<h1>California Legislative Information</h1><p>Crawlable, section-by-section HTML for the California Constitution and statutory codes.</p>
<p><strong>{section_count:,}</strong> sections across <strong>{len(CODES)}</strong> codes.</p><h2>Codes</h2>{"".join(code_cards)}
<p class="crumbs">Generated {generated}. The repository's compressed JSONL snapshots are the canonical source.</p>'''
    (output_dir / "index.html").write_text(_layout("California Legislative Information", base_url.rstrip("/") + "/", body), encoding="utf-8")
    (output_dir / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + base_url.rstrip("/") + "/sitemap-index.xml\n", encoding="utf-8")

    chunk_size = 45000
    sitemap_files: list[str] = []
    for i in range(0, len(urls), chunk_size):
        name = f"sitemap-{i // chunk_size + 1}.xml"
        sitemap_files.append(name)
        entries = "".join(f"<url><loc>{_esc(base_url.rstrip('/') + u)}</loc></url>" for u in urls[i:i + chunk_size])
        (output_dir / name).write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>\n', encoding="utf-8")
    indexes = "".join(f"<sitemap><loc>{_esc(base_url.rstrip('/') + '/' + name)}</loc></sitemap>" for name in sitemap_files)
    (output_dir / "sitemap-index.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{indexes}</sitemapindex>\n', encoding="utf-8")
    return {"codes": len(CODES), "sections": section_count, "urls": len(urls), "sitemaps": len(sitemap_files)}


__all__ = ["export_html"]
