---
title: Sources
sidebar:
  order: 1
description: Where the legislative data comes from and how it is processed.
---

# Sources

The corpus is built from California Legislature / Legislative Information sources and preserves provenance in the repository manifest.

## Law text

The law pipeline downloads the code text, parses it section by section, and writes canonical JSONL snapshots. The parser preserves table-of-contents hierarchy, section text, and history trailers rather than treating the source as a simple line-oriented format.

## Bills

The bill importer targets the Legislature's published `pubinfo_<session>.zip` bulk archive. It can populate bill metadata, versions, actions, votes, authors, analyses, legislators, locations, and motions.

## Important distinction

The committed law snapshot is the source of truth for this project. SQLite, HTML, and Markdown exports are generated artifacts. A generated artifact should not be treated as an independent source of legislative truth.
