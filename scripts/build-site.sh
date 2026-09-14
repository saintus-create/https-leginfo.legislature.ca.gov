#!/usr/bin/env bash
set -euo pipefail

rm -rf public/data public/ai-corpus
mkdir -p public/data/law public/ai-corpus

python3 scripts/build-research-index.py

for file in data/law/*.jsonl.gz; do
  code="$(basename "$file" .jsonl.gz)"
  tmp="public/data/law/${code}.jsonl"
  gzip -dc "$file" > "$tmp"
  split -b 10m -d -a 3 "$tmp" "public/data/law/${code}.part-"
  rm "$tmp"
done

{
  printf '{\n'
  first_code=1
  for file in data/law/*.jsonl.gz; do
    code="$(basename "$file" .jsonl.gz)"
    if [ "$first_code" -eq 0 ]; then printf ',\n'; fi
    first_code=0
    printf '  "%s": [' "$code"
    first_part=1
    for part in public/data/law/${code}.part-*; do
      if [ "$first_part" -eq 0 ]; then printf ', '; fi
      first_part=0
      printf '"%s"' "$(basename "$part")"
    done
    printf ']'
  done
  printf '\n}\n'
} > public/data/law/manifest.json

{
  printf '<!doctype html><html><head><meta charset="utf-8"><title>California Legislative Information corpus</title></head><body><h1>California Legislative Information corpus</h1><p>Machine-readable statute records for Cloudflare AI Search.</p><ul>\n'
  for part in public/data/law/*.part-*; do
    name="$(basename "$part")"
    printf '<li><a href="../data/law/%s">%s</a></li>\n' "$name" "$name"
  done
  printf '</ul></body></html>\n'
} > public/ai-corpus/index.html

astro build
