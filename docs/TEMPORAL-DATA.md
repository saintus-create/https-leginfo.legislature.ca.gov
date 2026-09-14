# Temporal and Legislative-History Data Architecture

## Purpose

The research system must answer two different temporal questions without conflating them:

1. **What text existed in a particular corpus snapshot?**
2. **What legislative events changed, enacted, repealed, or otherwise affected that provision?**

`law_sections` remains the current retrieval surface. `law_section_versions` is the immutable historical text surface. `legislative_history_events` records events. `legislative_sources` records the primary source objects behind those events.

## D1 model

```text
corpus_versions
    |
    +---- law_section_versions (uid + corpus_version_id)
    |          |
    |          +---- section_version_sources ---- legislative_sources
    |
    +---- legislative_history_events ----> bill/chapter/source metadata
```

A section UID identifies the legal provision across time. `corpus_version_id` identifies the snapshot containing a particular textual representation. `valid_from` and `valid_to` describe the known legal-effective interval when that interval is established by source data. They must not be inferred merely from the date on which the crawler captured a page.

`content_hash` permits exact detection of unchanged text across snapshots. An unchanged section can therefore be linked across corpus versions without pretending that every snapshot represents a legislative amendment.

## R2 object layout

R2 stores source artifacts and larger immutable documents. D1 stores searchable metadata and relationships. Generated AI artifacts are kept separate from source objects.

Recommended key layout:

```text
source/corpus/{corpusVersionId}/manifest.json
source/corpus/{corpusVersionId}/law/{LAW_CODE}.jsonl.gz
source/history/{sourceId}/{filename}
source/bills/{session}/{billId}/{documentType}.{ext}
source/chapters/{session}/{chapter}.{ext}

artifact/derived/{artifactType}/{corpusVersionId}/{uid}.{ext}
artifact/ai/{artifactType}/{corpusVersionId}/{uid}.{ext}
```

The `source/` namespace is authoritative input. The `artifact/` namespace is derived output and must never be presented as primary legislative text.

Each source object should have a stable content hash recorded in D1. The object key is an address, not evidence by itself. Evidence requires the D1 metadata record plus the underlying source object or official source URL.

## Version ingestion rules

1. Create a new `corpus_versions` record for each imported official snapshot.
2. Store the raw source snapshot in R2 under a versioned key.
3. Normalize each provision into `law_section_versions` with the snapshot ID and content hash.
4. Update `law_sections` only for the selected current corpus snapshot.
5. Extract explicit legislative-history events into `legislative_history_events`.
6. Register every history source in `legislative_sources`.
7. Link affected section versions to their source records through `section_version_sources`.
8. Never overwrite an old section version to make it look current.

## `get_history()` contract

`get_history(uid)` should return chronological events and their source identity, not a generated narrative. The AI may synthesize those events into prose only after retrieval.

A history result should make it possible to distinguish:

- amendment
- enactment
- repeal
- renumbering
- operative/effective-date change
- chapter or bill action
- historical source record
- unknown or unresolved event

The system should preserve unknown dates rather than manufacture precision. A capture date is not an effective date, because apparently even dates need evidence.

## Temporal reasoning

For a question such as `What did this section provide in 2018?`, the orchestrator should:

1. resolve the section UID;
2. identify the requested temporal point;
3. retrieve section versions whose known effective interval contains that point;
4. retrieve adjacent history events needed to establish the transition;
5. compare candidate versions if the interval is ambiguous;
6. cite the historical source/version used;
7. explicitly mark any unresolved temporal gap.

For `What changed?`, retrieve both versions and the intervening events, then use structured comparison. Do not ask the language model to infer the historical change from two unrelated current pages.
