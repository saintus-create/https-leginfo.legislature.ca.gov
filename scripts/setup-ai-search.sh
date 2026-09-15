#!/usr/bin/env bash
set -euo pipefail

INSTANCE="${AI_SEARCH_INSTANCE:-leginfo-search}"
BUCKET="${R2_BUCKET:-r2objectstorage}"

# Creates the modern AI Search instance if it does not already exist.
# Wrangler performs the R2 service-token registration needed by AI Search.
if npx wrangler ai-search get "$INSTANCE" --json >/dev/null 2>&1; then
  echo "AI Search instance already exists: $INSTANCE"
else
  npx wrangler ai-search create "$INSTANCE" \
    --type r2 \
    --source "$BUCKET" \
    --embedding-model '@cf/qwen/qwen3-embedding-0.6b' \
    --generation-model '@cf/meta/llama-3.3-70b-instruct-fp8-fast' \
    --chunk-size 900 \
    --chunk-overlap 120 \
    --max-num-results 12 \
    --reranking \
    --reranking-model '@cf/baai/bge-reranker-base' \
    --hybrid-search \
    --cache
fi

npx wrangler ai-search stats "$INSTANCE"
