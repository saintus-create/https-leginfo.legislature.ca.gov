---
title: California Legislative Information
sidebar:
  order: 1
---

# California Legislative Information

A local, queryable copy of California statutory law and legislative data, presented in a documentation-style interface.

<div class="stat-grid">
  <div><strong>30</strong><span>codes</span></div>
  <div><strong>162,324</strong><span>sections</span></div>
  <div><strong>24,233</strong><span>TOC nodes</span></div>
  <div><strong>190M+</strong><span>characters</span></div>
</div>

## Start with the law

Browse the code index, search the corpus, or read about how the data is collected and structured.

- [Browse Codes](/https-leginfo.legislature.ca.gov/codes/)
- [Search the corpus](/https-leginfo.legislature.ca.gov/search/)
- [Data and provenance](/https-leginfo.legislature.ca.gov/data/)

:::note
This project is a structured local copy of information published by the California Legislature. The dataset is intended for research and reproducible analysis; consult the official source for authoritative current text.
:::

## What this project contains

The repository stores section-level structured records for the California Constitution and the 29 California statutory codes. It also includes a repeatable pipeline for importing legislative bills from the Legislature's official bulk archive.

The canonical snapshot is JSON Lines, compressed one file per code. A SQLite database and retrieval-ready Markdown corpus can be generated from that source of truth.
