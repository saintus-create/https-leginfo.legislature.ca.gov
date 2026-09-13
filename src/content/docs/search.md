---
title: Search
sidebar:
  order: 3
description: Search the California Legislative Information corpus locally.
---

# Search

The repository includes SQLite FTS5 search over the structured law snapshot.

```bash
python3 -m leginfo build-db
python3 -m leginfo search "public records act" --limit 5
```

Search can also be narrowed to a code:

```bash
python3 -m leginfo search "imminent peril of death" --code PEN --limit 5
```

To inspect a known section directly:

```bash
python3 -m leginfo section GOV 7921.000
```

The database is derived data. Rebuild it from the committed JSONL snapshot whenever the snapshot changes.
