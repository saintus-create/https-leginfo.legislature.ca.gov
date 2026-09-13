---
title: Data and provenance
sidebar:
  order: 4
description: Structure, provenance, and reproducibility of the law corpus.
---

# Data and provenance

The repository's canonical law snapshot is stored as compressed JSON Lines under `data/law/`, one file per code. The SQLite database and Markdown retrieval export are reproducible derivatives.

## Current snapshot

- 30 codes: 29 statutory codes plus the California Constitution
- 162,324 sections
- 24,233 table-of-contents nodes
- about 190 million characters of statutory text
- about 51 MB compressed in the committed law snapshot

## Reproducible pipeline

```bash
python3 -m leginfo collect-law
python3 -m leginfo build-db
python3 -m leginfo verify
python3 -m leginfo export-markdown --output autorag
```

## Public-domain status

The repository README identifies the published legislative information as public-domain material under Government Code § 10248.5.

For provenance and source caveats, see [Sources](/https-leginfo.legislature.ca.gov/sources/).
