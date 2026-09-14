#!/usr/bin/env python3
"""Export the imported bill database into a crawlable static bill browser."""
from __future__ import annotations

import html
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

DB = Path(os.environ.get("LEGINFO_DB", "data/leginfo.sqlite"))
OUT = Path(os.environ.get("LEGINFO_BILLS_OUT", "public/bills"))
BASE = os.environ.get("SITE_BASE", "/https-leginfo.legislature.ca.gov").rstrip("/")


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def slug(value: str) -> str:
    return quote(value, safe="-._")


def page(title: str, body: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} | California Legislative Information</title><meta name="description" content="California legislative bill record"><style>:root{{color-scheme:dark;--bg:#0f1217;--panel:#171c23;--text:#f8fafc;--muted:#a8b1bd;--line:#303946;--link:#8bb8e8}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}main,header,footer{{max-width:1120px;margin:auto;padding:1rem 1.25rem}}header{{border-bottom:1px solid var(--line)}}footer{{color:var(--muted);font-size:.85rem;border-top:1px solid var(--line);margin-top:3rem}}a{{color:var(--link)}}h1{{font-size:clamp(2rem,5vw,3.5rem);line-height:1.1;letter-spacing:-.03em}}h2{{margin-top:2.5rem;border-top:1px solid var(--line);padding-top:1.25rem}}.meta{{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem;margin:1.5rem 0}}.meta div,.card{{border:1px solid var(--line);background:var(--panel);border-radius:.45rem;padding:.8rem 1rem}}.meta small,.muted{{display:block;color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}}.bill-text{{white-space:pre-wrap;font:15px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--panel);border:1px solid var(--line);padding:1.25rem;border-radius:.45rem;overflow:auto}}.row{{padding:.75rem 0;border-bottom:1px solid var(--line)}}input,select{{font:inherit;background:var(--panel);color:var(--text);border:1px solid var(--line);padding:.7rem;border-radius:.35rem}}.toolbar{{display:flex;gap:.75rem;flex-wrap:wrap;margin:1rem 0 1.5rem}}@media(max-width:700px){{.meta{{grid-template-columns:1fr}}}}</style></head><body><header><a href="{BASE}/">California Legislative Information</a> · <a href="{BASE}/legislation/">Legislation</a></header><main>{body}</main><footer>Source: California Legislative Information official public bulk data. Records are reproduced for research and reference.</footer></body></html>'''


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"missing database: {DB}")
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    bills = con.execute("""
        SELECT b.*, v.title AS latest_title, v.subject AS latest_subject,
               v.action_date AS latest_version_date, v.action AS latest_version_action,
               v.digest AS latest_digest, v.text AS latest_text
        FROM bills b
        LEFT JOIN bill_versions v ON v.bill_version_id = b.latest_bill_version_id
        ORDER BY CAST(b.session_year AS INTEGER) DESC, b.measure_type, CAST(b.measure_num AS INTEGER)
    """).fetchall()

    sessions: dict[str, list[sqlite3.Row]] = {}
    for bill in bills:
        sessions.setdefault(str(bill["session_year"] or "unknown"), []).append(bill)

    index = []
    session_links = []
    for session, rows in sorted(sessions.items(), reverse=True):
        session_dir = OUT / session
        session_dir.mkdir(parents=True, exist_ok=True)
        session_items = []
        for bill in rows:
            measure = f"{bill['measure_type']}-{bill['measure_num']}"
            href = f"{BASE}/bills/{slug(session)}/{slug(measure)}/"
            title = bill["latest_title"] or bill["latest_subject"] or measure
            record = {
                "bill_id": bill["bill_id"], "session_year": session,
                "measure_type": bill["measure_type"], "measure_num": bill["measure_num"],
                "measure": measure, "title": title, "status": bill["current_status"],
                "location": bill["current_location"], "house": bill["current_house"],
                "chapter": f"{bill['chapter_type']} {bill['chapter_num']}" if bill["chapter_num"] else None,
                "href": href,
            }
            index.append(record)
            session_items.append(record)

            authors = con.execute("""
                SELECT DISTINCT a.name, a.type, a.house, a.contribution
                FROM bill_authors a JOIN bill_versions v ON v.bill_version_id = a.bill_version_id
                WHERE v.bill_id = ? ORDER BY a.primary_author_flg DESC, a.name
            """, (bill["bill_id"],)).fetchall()
            actions = con.execute("SELECT action_date, action, primary_location, secondary_location, end_status FROM bill_actions WHERE bill_id = ? ORDER BY action_date, action_sequence", (bill["bill_id"],)).fetchall()
            votes = con.execute("SELECT vote_date_time, location_code, ayes, noes, abstain, vote_result FROM bill_votes WHERE bill_id = ? ORDER BY vote_date_time", (bill["bill_id"],)).fetchall()
            versions = con.execute("SELECT bill_version_id, version_num, action_date, action, title, subject, digest, char_count FROM bill_versions WHERE bill_id = ? ORDER BY version_num", (bill["bill_id"],)).fetchall()
            analyses = con.execute("SELECT analysis_date, house, analysis_type, committee_name, text FROM bill_analyses WHERE bill_id = ? ORDER BY analysis_date", (bill["bill_id"],)).fetchall()

            meta = f'''<div class="meta"><div><small>Session</small>{esc(session)}</div><div><small>Measure</small>{esc(measure)}</div><div><small>Status</small>{esc(bill["current_status"] or "")}</div><div><small>House</small>{esc(bill["current_house"] or "")}</div><div><small>Location</small>{esc(bill["current_location"] or "")}</div><div><small>Chapter</small>{esc(record["chapter"] or "Not chaptered")}</div></div>'''
            author_html = "".join(f'<div class="row"><strong>{esc(a["name"])}</strong> <span class="muted">{esc(a["type"])} {esc(a["house"])}</span></div>' for a in authors)
            action_html = "".join(f'<div class="row"><strong>{esc(a["action_date"])}</strong> — {esc(a["action"])} <span class="muted">{esc(a["primary_location"] or "")}</span></div>' for a in actions)
            vote_html = "".join(f'<div class="row"><strong>{esc(v["vote_date_time"])}</strong> — {esc(v["vote_result"])} · Ayes {esc(v["ayes"])} · Noes {esc(v["noes"])} · Abstain {esc(v["abstain"])}</div>' for v in votes)
            version_html = "".join(f'<div class="row"><strong>Version {esc(v["version_num"])}</strong> — {esc(v["action_date"])} — {esc(v["action"])}<br><span class="muted">{esc(v["title"] or v["subject"] or "")}</span></div>' for v in versions)
            analysis_html = "".join(f'<details class="row"><summary><strong>{esc(a["analysis_date"])}</strong> — {esc(a["house"])} — {esc(a["analysis_type"])} — {esc(a["committee_name"])}</summary><div class="bill-text">{esc(a["text"] or "")}</div></details>' for a in analyses)
            body = f'''<p class="muted">California Legislature · {esc(session)}</p><h1>{esc(measure)}</h1><p>{esc(title)}</p>{meta}<h2>Bill text</h2><div class="bill-text">{esc(bill["latest_text"] or "Bill text was not present in the imported version record.")}</div><h2>Authors</h2>{author_html or '<p class="muted">No author records.</p>'}<h2>Versions</h2>{version_html or '<p class="muted">No version records.</p>'}<h2>Legislative history</h2>{action_html or '<p class="muted">No action records.</p>'}<h2>Votes</h2>{vote_html or '<p class="muted">No vote summary records.</p>'}<h2>Analyses</h2>{analysis_html or '<p class="muted">No analysis records.</p>'}'''
            bill_dir = session_dir / slug(measure)
            bill_dir.mkdir(parents=True, exist_ok=True)
            (bill_dir / "index.html").write_text(page(f"{measure} — {title}", body), encoding="utf-8")

        session_body = f'''<p class="muted">Legislative session</p><h1>{esc(session)}</h1><p>{len(rows):,} imported measures.</p><div class="toolbar"><input id="q" placeholder="Search bills by number or title" oninput="filterBills()"></div><div id="bills">{''.join(f'<div class="card bill" data-search="{esc((r["measure"]+" "+str(r["title"])).lower())}"><a href="{esc(r["href"])}"><strong>{esc(r["measure"])}</strong></a> — {esc(r["title"])}<br><span class="muted">{esc(r["status"] or "")}</span></div>' for r in session_items)}</div><script>function filterBills(){{const q=document.getElementById('q').value.toLowerCase();document.querySelectorAll('.bill').forEach(e=>e.hidden=!e.dataset.search.includes(q));}}</script>'''
        (session_dir / "index.html").write_text(page(f"California legislation {session}", session_body), encoding="utf-8")
        session_links.append(f'<div class="card"><a href="{BASE}/bills/{slug(session)}/"><strong>{esc(session)}</strong></a> — {len(rows):,} measures</div>')

    OUT.joinpath("index.html").write_text(page("California legislation", f'<h1>California legislation</h1><p>{len(bills):,} imported measures across {len(sessions)} session(s).</p>{"".join(session_links)}'), encoding="utf-8")
    OUT.joinpath("index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"exported {len(bills):,} bills across {len(sessions)} sessions to {OUT}")


if __name__ == "__main__":
    main()
