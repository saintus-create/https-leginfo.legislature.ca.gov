# AI Stronghold — Beyond Word Match

This document describes the hardened AI implementation that replaces naive keyword matching with orchestrated, evidence-grounded reasoning.

## Problem with word match

A word-match system:
- tokenizes query into words
- counts occurrences in corpus
- concatenates top passages
- asks LLM to summarize

It fails on:
- synonyms (custody vs custodial)
- cross-references (GOV § 7921 references other sections)
- definitions (statutory "means" controls interpretation)
- temporal questions (what did section say in 2019?)
- comparisons (similar vocabulary ≠ legal relationship)
- verification (no check that citations exist in evidence)

## Stronghold principles

### 1. Evidence is authoritative, AI is reasoning

```
User question
  ↓
Orchestrator: intent, citations, temporal scope, concepts
  ↓
Adaptive research plan: bounded tool operations
  ↓
Retrieval substrate: deterministic corpus
  ↓
Evidence state: findings, relationships, history, definitions
  ↓
AI synthesis: draft answer from evidence
  ↓
Verifier: removes unsupported claims
  ↓
Answer + citations + limits
```

Corpus determines facts. Model chooses operations. Conversation is context, not evidence.

### 2. Orchestrator – not a search endpoint

`src/worker/orchestrator.ts` implements:

- **Full code registry**: 30 codes (BPC, CIV, CCP, COM, CORP, EDC, ELEC, EVID, FAM, FIN, FGC, FAC, GOV, HNC, HSC, INS, LAB, MVC, PEN, PROB, PCC, PRC, PUC, RTC, SHC, UIC, VEH, WAT, WIC, CONS)
- **Order-preserving code resolution**: preserves appearance order in query (Family Code and Government Code → [FAM, GOV])
- **Citation extraction**: GOV § 7921.000, FAM section 3044, etc.
- **Temporal scope**: detects history, amended, effective, before/after, years
- **Intent classification**: lookup, explain, compare, investigate, chronology, synthesis – using multiple signals, not single regex
- **Adaptive planning**:
  - lookup: exact section + relationships + history if temporal
  - explain: primary retrieval + concept expansion + definition + relationship probes
  - compare: independent retrieval per code to avoid conflation + probe definitions, scope, authority, enforcement, exception
  - investigate: search + cross-reference expansion + definitions
  - chronology: search + history + version lineage
  - synthesis: broader search + evidence graph
- **Multi-round retrieval**: after initial findings, extracts referenced UIDs from text and pulls them (cross-reference expansion)
- **Evidence graph**: traverses relationships for multi-authority questions
- **Verification**: draft → verifier that checks every citation exists in evidence

System prompts enforce:
- Distinguish DIRECT TEXT, DIRECT COMPARISON, INFERENCE
- Never invent citations, URLs, history, intent
- When insufficient evidence, say so
- Preserve subdivisions (a)(1)(A), dates, defined terms

### 3. Retrieval – beyond FTS

`src/worker/retrieval.ts` (D1):

- **Query rewriting**: removes question scaffolding, expands synonyms (custody → custodial, parenting), generates rewrites
- **Hybrid ranking**: BM25 + title boost + phrase boost + proximity + length normalization
- **Exact citation first**: tries UID lookup before FTS
- **Definition search**: searches for "X means", "definition", "includes" patterns
- **Relationship traversal**: bounded depth 1-3, node caps, deduplication, both directions
- **History**: versioned table with fallback to parsing history field
- **Tools**: getDefinition, compare, resolveCitation, buildEvidenceGraph, analyzeDocument – provider-independent

`src/worker/static-retrieval.ts` (ASSETS fallback):

- **Semantic scoring**: TF saturation log(1+hits), title boost 3.5×, phrase boost 15, proximity boost, intent-aware boost for definitions
- **Concept extraction**: stopword removal, tokenization, phrase preservation
- **Candidate pruning via research-index**: uses terms → UIDs but as filter, not sole source
- **Same tool contract** as D1 for parity

`src/worker/ai-search.ts` (Hybrid):

- **Chunk parsing**: handles multiple key formats, metadata variations, preserves citation object via citationForSection
- **Relevance normalization**: reranking_score vs vector score
- **RRF fusion**: reciprocal rank fusion with k=60, weighted by original score – stronger than concatenation
- **Deduplication**: across primary and AI Search
- **Query rewrite tracking**: surfaces rewrites in retrieval metadata
- **Fallback handling**: if one side fails, other still returns

### 4. Worker – AI-first endpoints

`src/worker.ts`:

- **Retriever factory**: D1 if available, else static corpus, then hybrid with AI Search if bound
- **Endpoints**:
  - POST /api/research – orchestrated evidence only (no LLM), returns state + evidence + provenance
  - POST /api/answer – research + draft + verification, returns answer + state + evidence; supports streaming
  - POST /api/search – evidence bundle (search tool)
  - POST /api/analyze – document analysis
  - GET /api/citation?uid= – canonical citation
  - GET /api/health – capabilities, bindings, model
- **Validation**: max query 2000 chars, max limit 30, message sanitization, CORS hardened
- **Streaming**: if stream=true, does research synchronously, then streams LLM via SSE
- **Deterministic fallback**: if AI binding missing, returns evidence synthesis, not failure
- **Provenance**: plannedSteps, executedSteps, durationMs tracked

### 5. Frontend – AI reasoning visible

`ResearchBox.astro` and `CodeExplorer.astro`:

- Call /api/answer first (strong AI), fallback to /api/research (evidence-only), final fallback to static corpus with improved scoring
- Display intent, methods, provenance, duration
- Evidence with canonical LegInfo URLs, relevance, matchType
- Relationships, definitions, history, limits as separate collapsible sections
- Capabilities disclosure: explains how this is not word match

### 6. Tool contract

`src/worker/tools.ts` defines provider-independent tools:

- search, get_section, get_definition, get_relationships, get_history, compare, analyze_document, resolve_citation, build_evidence_graph

Application owns semantics, limits, provenance. Provider adapters (OpenAI, Anthropic, Cloudflare) map to native function calling.

## Verification

- `bun test` – orchestrator resolves comparison, executes evidence pipeline
- Build: `astro build` succeeds, research-index built with semantic terms
- Health endpoint lists capabilities: research-orchestration, evidence-graph, definition-search, relationship-traversal, temporal-history, document-analysis, citation-resolution, verification-pass, rrf-fusion, query-rewrite, streaming

## What "strongholding" means

- **Not decorative AI**: every AI capability must perform useful reasoning over authoritative evidence
- **Bounded**: traversal depth, node caps, result caps explicit
- **Auditable**: answer → evidence → citation → LegInfo URL chain inspectable
- **Resilient**: D1 → static → AI Search hybrid chain, with deterministic fallback
- **Secure**: input validation, sanitization, no fabricated URLs, citation integrity check

A longer answer is not evidence of deeper research. A deeper system is one that can identify what must be retrieved, retrieve it through distinct operations, reason over evidence, recognize what remains unknown, and preserve the path from conclusion back to source.
