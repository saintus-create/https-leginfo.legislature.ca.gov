#!/usr/bin/env bash
set -euo pipefail

# California's official bulk directory publishes session archives beginning in
# 1989. This intentionally runs one archive at a time so the database is built
# incrementally and the large ZIP files never enter Git history.
SESSIONS="${LEGINFO_SESSIONS:-1989 1991 1993 1995 1997 1999 2001 2003 2005 2007 2009 2011 2013 2015 2017 2019 2021 2023 2025}"
DATA_DIR="${LEGINFO_DATA_DIR:-data}"

python3 -m leginfo build-db
for session in $SESSIONS; do
  echo "== importing California legislative session $session =="
  python3 -m leginfo import-bills --session "$session"
done
python3 -m leginfo stats
SITE_BASE="${SITE_BASE:-/https-leginfo.legislature.ca.gov}" python3 scripts/export-bills.py
