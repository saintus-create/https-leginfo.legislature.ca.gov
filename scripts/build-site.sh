#!/usr/bin/env bash
set -euo pipefail

SESSION="${LEGINFO_SESSION:-2025}"
SITE_BASE="${SITE_BASE:-/https-leginfo.legislature.ca.gov}"

rm -rf public/data public/ai-corpus public/bills
mkdir -p public/data/law public/ai-corpus

# The law snapshot is committed and remains the canonical statutory source.
python3 scripts/build-research-index.py

# Build the queryable database, then import the official bill archive for the
# current legislative session. The official 2025 archive is ~1.2 GB, so it is
# deliberately downloaded in CI rather than committed to Git.
python3 -m leginfo build-db
python3 -m leginfo import-bills --session "$SESSION"
SITE_BASE="$SITE_BASE" python3 scripts/export-bills.py

for file in data/law/*.jsonl.gz; do
  code="$(basename "$file" .jsonl.gz)"
  tmp="public/data/law/${code}.jsonl"
  gzip -dc "$file" > "$tmp"
  split -C 10m -d -a 3 "$tmp" "public/data/law/${code}.part-"
  rm "$tmp"
done

node scripts/build-corpus-manifest.mjs
node scripts/verify-built-corpus.mjs

{
  printf '<!doctype html><html><head><meta charset="utf-8"><title>California Legislative Information corpus</title></head><body><h1>California Legislative Information corpus</h1><p>Machine-readable statute records for Cloudflare AI Search.</p><ul>\n'
  for part in public/data/law/*.part-*; do
    name="$(basename "$part")"
    printf '<li><a href="../data/law/%s">%s</a></li>\n' "$name" "$name"
  done
  printf '</ul></body></html>\n'
} > public/ai-corpus/index.html

astro build
