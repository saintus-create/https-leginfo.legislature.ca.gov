#!/usr/bin/env python3
"""Build deterministic research metadata and a compact lexical index from the law corpus."""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAW = ROOT / "data" / "law"
OUT = ROOT / "public" / "data" / "research-index.json"
# Keep this in sync with build-site.sh's `split -C 10m`: GNU split treats
# the lowercase `m` suffix as 1,000,000 bytes, not 1,048,576 (MiB).
PART_BYTES = 10_000_000

CODE_NAMES = {
    "BPC": "Business and Professions Code", "CIV": "Civil Code", "CCP": "Code of Civil Procedure",
    "COM": "Commercial Code", "CORP": "Corporations Code", "EDC": "Education Code",
    "ELEC": "Elections Code", "EVID": "Evidence Code", "FAM": "Family Code", "FIN": "Financial Code",
    "FGC": "Fish and Game Code", "FAC": "Food and Agricultural Code", "GOV": "Government Code",
    "HNC": "Harbors and Navigation Code", "HSC": "Health and Safety Code", "INS": "Insurance Code",
    "LAB": "Labor Code", "MVC": "Military and Veterans Code", "PEN": "Penal Code", "PROB": "Probate Code",
    "PCC": "Public Contract Code", "PRC": "Public Resources Code", "PUC": "Public Utilities Code",
    "RTC": "Revenue and Taxation Code", "SHC": "Streets and Highways Code", "UIC": "Unemployment Insurance Code",
    "VEH": "Vehicle Code", "WAT": "Water Code", "WIC": "Welfare and Institutions Code", "CONS": "California Constitution",
}

BOUNDARY = re.compile(r"(?<=[.!?])(?:[\"'”’\)\]]*)\s+(?=[A-Z0-9\"'“‘\(\[])" )
ABBREV = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|No|Nos|Sec|Secs|Cal|U\.S|e\.g|i\.e)\.$", re.I)
TOKEN = re.compile(r"[a-z0-9][a-z0-9._-]{2,}", re.I)
STOP = {
    "the", "and", "for", "that", "this", "with", "from", "shall", "may", "must", "such", "which",
    "into", "upon", "under", "there", "their", "them", "than", "then", "where", "when", "what",
    "have", "has", "had", "not", "any", "all", "each", "other", "more", "only", "section", "sections",
}


def sentences(text: str):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return
    start = 0
    for match in BOUNDARY.finditer(text):
        candidate = text[start:match.start() + 1].strip()
        if candidate and not ABBREV.search(candidate[-12:]):
            yield candidate
            start = match.end()
    tail = text[start:].strip()
    if tail:
        yield tail


def words(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text, re.UNICODE))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = {"version": 3, "partBytes": PART_BYTES, "codes": {}, "terms": {}, "locations": {}}
    term_candidates: dict[str, list[list[object]]] = defaultdict(list)

    files = sorted(LAW.glob("*.jsonl.gz"))
    for path in files:
        code = path.name.split(".")[0].upper()
        best_words = None
        best_chars = None
        section_count = 0
        uncompressed_offset = 0
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line_bytes = len(line.encode("utf-8"))
                # GNU split -C keeps a line that crosses a boundary in the
                # current part; the next line begins the next part. Assign
                # from the line's starting byte offset to mirror that rule.
                part_number = uncompressed_offset // PART_BYTES
                current_part = f"{code}.part-{part_number:03d}"
                uncompressed_offset += line_bytes
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("kind") != "section":
                    continue
                section_count += 1
                section = str(rec.get("section") or "")
                uid = str(rec.get("uid") or f"{code}:{section}")
                result["locations"][uid] = current_part
                text = rec.get("text") or ""
                for sent in sentences(text):
                    candidate = {
                        "uid": uid,
                        "citation": rec.get("citation") or f"{code} § {section}",
                        "section": section,
                        "text": sent,
                        "wordCount": words(sent),
                        "charCount": len(sent),
                    }
                    if best_words is None or candidate["wordCount"] > best_words["wordCount"]:
                        best_words = candidate
                    if best_chars is None or candidate["charCount"] > best_chars["charCount"]:
                        best_chars = candidate

                counts = Counter(t.lower() for t in TOKEN.findall(f"{rec.get('title') or ''} {text}") if t.lower() not in STOP)
                for token, count in counts.most_common():
                    bucket = term_candidates[token]
                    bucket.append([uid, count])
                    if len(bucket) > 16:
                        bucket.sort(key=lambda x: (-int(x[1]), str(x[0])))
                        del bucket[12:]

        result["codes"][code] = {
            "name": CODE_NAMES.get(code, code),
            "sectionCount": section_count,
            "longestSentenceByWords": best_words,
            "longestSentenceByChars": best_chars,
        }
        print(f"research-index: {code} {section_count:,} sections")

    result["terms"] = {
        token: [uid for uid, _count in sorted(items, key=lambda x: (-int(x[1]), str(x[0])))[:12]]
        for token, items in term_candidates.items()
    }
    # GNU split's oversized-line behavior cannot be reconstructed reliably
    # from source offsets. When deployed parts exist, use the actual files.
    deployed = ROOT / "public" / "data" / "law"
    parts = sorted(deployed.glob("*.part-*") if deployed.exists() else [])
    if parts:
        deployed_locations = {}
        for part in parts:
            with part.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("kind") == "section" and rec.get("uid"):
                        deployed_locations[str(rec["uid"])] = part.name
        if deployed_locations:
            result["locations"] = deployed_locations
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"research-index: wrote {OUT} ({OUT.stat().st_size:,} bytes; {len(result['terms']):,} terms)")


if __name__ == "__main__":
    main()
