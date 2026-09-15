#!/usr/bin/env bash
set -euo pipefail

SITE_BASE="${SITE_BASE:-/https-leginfo.legislature.ca.gov}"

rm -rf public/data public/ai-corpus
mkdir -p public/data/law public/ai-corpus

# GitHub Pages only needs the canonical statutory corpus, research index,
# integrity manifest, and Astro/Starlight site. Database/bill/AI exports are
# deliberately kept out of this critical deployment path.
PYTHONPATH=src python3 scripts/build-research-index.py

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
  printf '<!doctype html><html><head><meta charset="utf-8"><title>California Legislative Information corpus</title></head><body><h1>California Legislative Information corpus</h1><p>Machine-readable statutory records.</p><ul>\n'
  for part in public/data/law/*.part-*; do
    name="$(basename "$part")"
    printf '<li><a href="../data/law/%s">%s</a></li>\n' "$name" "$name"
  done
  printf '</ul></body></html>\n'
} > public/ai-corpus/index.html

SITE_BASE="$SITE_BASE" npx astro build
