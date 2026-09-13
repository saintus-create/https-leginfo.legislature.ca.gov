---
title: Technical notes
sidebar:
  order: 2
description: How the law corpus is parsed, stored, and exported.
---

# Technical notes

The Python package under `src/leginfo/` remains the data layer. Starlight is the documentation and web presentation layer.

## Parsing

The code-text parser uses a paragraph-level state machine. Heading depth is learned from the source instead of assumed globally, and history trailers are separated from substantive law text.

The parser also handles section-number variants, bracketed headings, Constitution article forms, fractional section numbers, and embedded interstate-compacts material.

## Storage

The canonical records are JSONL snapshots compressed with gzip. SQLite is built from those records and uses FTS5 for full-text search.

## Exports

The existing Python exporter can still produce a complete static HTML corpus. The Astro/Starlight application is intentionally separate from that data pipeline so refreshing legislative data does not require rewriting the site architecture.
