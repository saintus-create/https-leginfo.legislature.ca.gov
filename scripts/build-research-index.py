#!/usr/bin/env python3
"""Build a compact deterministic research index from the law corpus."""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAW = ROOT / "data" / "law"
OUT = ROOT / "public" / "data" / "research-index.json"

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

# Split only on sentence-ending punctuation followed by whitespace/capitalization.
# This deliberately avoids treating decimal points and common abbreviations as boundaries.
BOUNDARY = re.compile(r"(?<=[.!?])(?:[\"'”’\)\]]*)\s+(?=[A-Z0-9\"'“‘\(\[])" )
ABBREV = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|No|Nos|Sec|Secs|Cal|U\.S|e\.g|i\.e)\.$", re.I)


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
    result = {"version": 1, "codes": {}}
    files = sorted(LAW.glob("*.jsonl.gz"))
    for path in files:
        code = path.name.split(".")[0].upper()
        best_words = None
        best_chars = None
        section_count = 0
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("kind") != "section":
                    continue
                section_count += 1
                text = rec.get("text") or ""
                for sent in sentences(text):
                    candidate = {
                        "citation": rec.get("citation") or f"{code} § {rec.get('section', '')}",
                        "section": rec.get("section"),
                        "text": sent,
                        "wordCount": words(sent),
                        "charCount": len(sent),
                    }
                    if best_words is None or candidate["wordCount"] > best_words["wordCount"]:
                        best_words = candidate
                    if best_chars is None or candidate["charCount"] > best_chars["charCount"]:
                        best_chars = candidate
        result["codes"][code] = {
            "name": CODE_NAMES.get(code, code),
            "sectionCount": section_count,
            "longestSentenceByWords": best_words,
            "longestSentenceByChars": best_chars,
        }
        print(f"research-index: {code} {section_count:,} sections")
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"research-index: wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
