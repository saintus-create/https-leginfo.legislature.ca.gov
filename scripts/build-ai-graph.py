#!/usr/bin/env python3
"""Export a compact relationship graph from the canonical SQLite corpus."""
from __future__ import annotations
import json
import re
import sqlite3
from pathlib import Path

DATA = Path('data')
OUT = Path('public/data/research-graph.json')
CODES = 'BPC|CIV|CCP|COM|CORP|EDC|ELEC|EVID|FAM|FIN|FGC|FAC|GOV|HNC|HSC|INS|LAB|MVC|PEN|PROB|PCC|PRC|PUC|RTC|SHC|UIC|VEH|WAT|WIC|CONS'
REF = re.compile(rf'\b({CODES})\s*(?:§|section)\s*([A-Za-z0-9][A-Za-z0-9.\-]*)\b', re.I)


def add(edges, source, target, relationship, reference='', confidence=1.0):
    key = (source, target, relationship, reference)
    if key in edges: return
    edges[key] = {'sourceUid': source, 'targetUid': target, 'relationship': relationship, 'referenceText': reference or None, 'confidence': confidence}


def main():
    db = sqlite3.connect(DATA / 'leginfo.sqlite')
    db.row_factory = sqlite3.Row
    edges = {}
    nodes = {}

    for r in db.execute('SELECT uid, code, section, title FROM law_sections'):
        nodes[r['uid']] = {'type':'section','code':r['code'],'section':r['section'],'title':r['title']}

    bill_rows = db.execute('SELECT bill_id, session_year, measure_type, measure_num, current_status, chapter_year, chapter_type, chapter_num FROM bills').fetchall()
    for r in bill_rows:
        label = f"{r['measure_type']} {r['measure_num']}"
        nodes[r['bill_id']] = {'type':'bill','label':label,'session':r['session_year'],'status':r['current_status'],'chapter': f"{r['chapter_type']} {r['chapter_num']}" if r['chapter_num'] else None}
        if r['chapter_num']:
            add(edges, r['bill_id'], f"chapter:{r['chapter_year']}:{r['chapter_type']}:{r['chapter_num']}", 'became-chapter', f"Chapter {r['chapter_num']} ({r['chapter_year']})")

    # Bill version lineage and section citations found in bill text.
    for r in db.execute('SELECT v.bill_version_id, v.bill_id, v.version_num, v.action_date, v.text FROM bill_versions v WHERE v.text IS NOT NULL AND length(v.text) > 0'):
        vid = f"bill-version:{r['bill_version_id']}"
        nodes[vid] = {'type':'bill-version','billId':r['bill_id'],'version':r['version_num'],'date':r['action_date']}
        add(edges, r['bill_id'], vid, 'has-version', f"Version {r['version_num']} ({r['action_date'] or 'undated'})")
        text = r['text']
        seen = set()
        for m in REF.finditer(text):
            uid = f"{m.group(1).upper()}:{m.group(2)}"
            if uid not in nodes: continue
            if uid in seen: continue
            seen.add(uid)
            add(edges, uid, r['bill_id'], 'referenced-by-bill', f"Bill {nodes[r['bill_id']]['label']}; version {r['version_num']}; {r['action_date'] or 'undated'}", 0.95)

    # Bill authors.
    for r in db.execute('''SELECT DISTINCT b.bill_id, a.name, a.type, a.house FROM bill_authors a JOIN bill_versions v ON v.bill_version_id=a.bill_version_id JOIN bills b ON b.bill_id=v.bill_id WHERE a.name IS NOT NULL AND a.name != '' '''):
        aid = f"author:{r['name']}"
        nodes[aid] = {'type':'author','name':r['name'],'house':r['house'],'authorType':r['type']}
        add(edges, r['bill_id'], aid, 'has-author', r['type'] or '')

    # Committees from legislative analyses.
    for r in db.execute('''SELECT DISTINCT bill_id, committee_name, committee_code FROM bill_analyses WHERE committee_name IS NOT NULL AND committee_name != '' '''):
        cid = f"committee:{r['committee_code'] or r['committee_name']}"
        nodes[cid] = {'type':'committee','name':r['committee_name'],'code':r['committee_code']}
        add(edges, r['bill_id'], cid, 'analyzed-by', r['committee_name'])

    # Legislative history gives bills/actions/timing to the graph.
    for r in db.execute('SELECT bill_id, action_date, action, primary_location, secondary_location FROM bill_actions WHERE bill_id IS NOT NULL'):
        if r['bill_id'] not in nodes: continue
        ref = ' | '.join(x for x in (r['action_date'], r['action'], r['primary_location'], r['secondary_location']) if x)
        add(edges, r['bill_id'], f"date:{r['action_date'] or 'unknown'}", 'has-legislative-event', ref)

    payload = {
        'version': 1,
        'generatedFrom': 'data/leginfo.sqlite',
        'nodes': list(nodes.values()) and [{'uid': k, **v} for k,v in nodes.items()] or [],
        'edges': list(edges.values()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"nodes={len(payload['nodes'])} edges={len(payload['edges'])} bytes={OUT.stat().st_size}")
    db.close()

if __name__ == '__main__': main()
