#!/usr/bin/env bash
set -euo pipefail

BUCKET="${R2_BUCKET:-r2objectstorage}"
SOURCE="${1:-autorag}"

if [[ ! -d "$SOURCE" ]]; then
  echo "Missing corpus directory: $SOURCE" >&2
  exit 1
fi

# AI Search can index Markdown directly from an R2-backed data source.
# Upload the source files while preserving the corpus-relative paths.
find "$SOURCE" -type f -name '*.md' -print0 |
  xargs -0 -n1 -P8 bash -c '
    file="$1"
    key="${file#'"$SOURCE"'/}"
    echo "Uploading $key"
    npx wrangler r2 object put "'"$BUCKET"'/$key" --file "$file" --remote --content-type text/markdown >/dev/null
  ' _

echo "R2 corpus upload complete: $SOURCE -> $BUCKET"
