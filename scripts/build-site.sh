#!/usr/bin/env bash
set -euo pipefail

mkdir -p public/data/law
for file in data/law/*.jsonl.gz; do
  name="$(basename "$file" .gz)"
  gzip -dc "$file" > "public/data/law/$name"
done

astro build
