#!/usr/bin/env bash
set -euo pipefail

SESSION="${LEGINFO_SESSION:-2025}"
SITE_BASE="${SITE_BASE:-/https-leginfo.legislature.ca.gov}"

rm -rf public/data public/ai-corpus public/bills autorag
mkdir -p public/data/law public/ai-corpus

# Full validation build. Optional database/bill/AI exports may be unavailable in
# CI, but the statutory corpus, manifest, and integrity verification are strict.
PYTHONPATH=src python3 scripts/build-research-index.py
PYTHONPATH=src python3 -m leginfo build-db || echo "build-db skipped (optional)"
PYTHONPATH=src python3 -m leginfo import-bills --session "$SESSION" || echo "import-bills skipped (optional)"
SITE_BASE="$SITE_BASE" PYTHONPATH=src python3 scripts/export-bills.py || echo "export-bills skipped (optional)"
PYTHONPATH=src python3 -m leginfo export-markdown --output autorag || echo "export-markdown skipped (optional)"

for file in data/law/*.jsonl.gz; do
  code="$(basename "$file" .jsonl.gz)"
  tmp="public/data/law/${code}.jsonl"
  gzip -dc "$file" > "$tmp"
  split -C 10m -d -a 3 "$tmp" "public/data/law/${code}.part-"
  rm "$tmp"
done

node scripts/build-corpus-manifest.mjs
PYTHONPATH=src python3 scripts/build-ai-graph.py || echo "build-ai-graph skipped (optional)"
node scripts/verify-built-corpus.mjs

{
  printf '<!doctype html><html><head><meta charset="utf-8"><title>California Legislative Information corpus</title></head><body><h1>California Legislative Information corpus</h1><p>Machine-readable statute records for Cloudflare AI Search.</p><ul>\n'
  for part in public/data/law/*.part-*; do
    name="$(basename "$part")"
    printf '<li><a href="../data/law/%s">%s</a></li>\n' "$name" "$name"
  done
  printf '</ul></body></html>\n'
} > public/ai-corpus/index.html

SITE_BASE="$SITE_BASE" npx astro build
