#!/usr/bin/env bash
set -euo pipefail

rm -rf public/data public/ai-corpus
mkdir -p public/data/law public/ai-corpus

python3 scripts/build-research-index.py

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
