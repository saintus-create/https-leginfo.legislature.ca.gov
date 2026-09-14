# AI Research Orchestrator Specification

## 1. Purpose

The orchestrator is the reasoning coordinator between the user and the deterministic legislative research substrate. It is not a search endpoint and it is not itself the source of legal facts.

Its job is to turn a natural-language research problem into a bounded sequence of research operations, inspect the returned evidence, determine what remains unresolved, and produce an answer whose material claims can be traced to retrieved authority.

```text
USER
  |
  v
ORCHESTRATOR
  |  intent / references / temporal scope / research plan
  v
RESEARCH TOOLS
  |-- search
  |-- get_section
  |-- get_definition
  |-- get_relationships
  |-- get_history
  |-- compare
  |-- analyze_document
  |-- resolve_citation
  |-- build_evidence_graph
  v
EVIDENCE STATE
  |  sources / relations / versions / findings / gaps
  v
REASONING
  |  synthesis / comparison / qualification / contradiction
  v
ANSWER
     analysis + citations + unresolved questions
```

## 2. Core rule

The model chooses research operations. The corpus determines factual evidence.

The orchestrator must never treat model memory, conversation history, generated summaries, or prior AI answers as equivalent to corpus evidence.

## 3. Research lifecycle

Every substantive research request follows this lifecycle, with steps skipped only when the orchestrator can establish that they are unnecessary.

### Understand

Parse the user's actual problem rather than blindly searching the complete message.

Extract:

- requested task: explain, compare, connect, investigate, analyze, reconstruct, or synthesize;
- legal/informational concepts;
- explicit section, code, bill, chapter, or other references;
- ambiguous references such as `that section` or `the exception`;
- actors or entities;
- temporal scope;
- jurisdiction or corpus scope;
- requested output form;
- claims that require external evidence not contained in the legislative corpus.

### Plan

Construct a research plan consisting of bounded tool operations. The plan is adaptive. Retrieval results can add or remove subsequent operations.

Example:

```text
Question: Does X create an exception to Y?

1. resolve X and Y
2. retrieve X and Y
3. retrieve operative definitions
4. retrieve explicit cross-references
5. traverse relevant relationships
6. retrieve exceptions/qualifications
7. retrieve historical versions if temporal context matters
8. compare controlling language
9. build evidence graph
10. identify supported conclusions and unresolved propositions
11. resolve citations
12. synthesize answer
```

### Retrieve

Use the narrowest operation that can establish the needed fact.

- Exact reference -> `get_section`
- Candidate authorities -> `search`
- Operative terminology -> `get_definition`
- Statutory dependencies -> `get_relationships`
- Temporal question -> `get_history` and versioned `get_section`
- Textual difference -> `compare`
- User document -> `analyze_document`
- Source presentation -> `resolve_citation`
- Multi-authority structure -> `build_evidence_graph`

Broad search is a discovery mechanism, not a substitute for exact retrieval once an authority is identified.

### Evaluate

For each material proposition, maintain one of three states:

```text
SUPPORTED
    Retrieved source directly establishes the proposition.

INFERRED
    The proposition is analytical synthesis from identified sources.

UNRESOLVED
    Available evidence does not establish the proposition.
```

An inferred proposition must retain links to the evidence from which the inference was made. An unresolved proposition must not be silently converted into a conclusion.

### Verify

Before final synthesis:

- verify every material legal citation;
- verify that cited text corresponds to the claimed provision/version;
- check that historical claims use historical evidence rather than current text;
- check that relationship claims have an explicit relationship record or source text;
- distinguish statutory text from AI characterization;
- identify missing evidence;
- remove unsupported factual claims.

## 4. Evidence state

The orchestrator maintains structured research state across turns:

```ts
interface ResearchState {
  userQuestion: string;
  normalizedQuestion?: string;
  intent?: string;
  temporalScope?: { from?: string; to?: string; point?: string };
  authorities: string[];
  definitions: string[];
  relationships: string[];
  versions: string[];
  findings: Array<{
    proposition: string;
    status: 'supported' | 'inferred' | 'unresolved';
    evidenceIds: string[];
  }>;
  unresolved: string[];
  citations: string[];
}
```

State is contextual memory, not authoritative evidence. Every evidence ID resolves back to a retrieved source record.

## 5. Tool contract

Tools must be provider-independent. A model provider can expose them through its native function-calling interface, but tool semantics remain application-owned.

```text
search(query, code?, limit?)
get_section(uid, versionId?)
get_definition(term, scope?)
get_relationships(uid, direction?, depth?, limit?)
get_history(uid, versionId?, from?, to?, limit?)
compare(left, right, dimensions?)
analyze_document(document, propositions?)
resolve_citation(uid, versionId?)
build_evidence_graph(uids, depth?)
```

The first implementation phase does not require every tool to have a production backend. The orchestrator contract should exist before provider-specific AI logic so that retrieval and reasoning can evolve independently.

## 6. Adaptive planning

The orchestrator is allowed to perform multiple retrieval rounds.

```text
plan -> retrieve -> inspect evidence -> revise plan -> retrieve -> compare -> verify -> answer
```

A result that introduces a definition, cross-reference, exception, historical transition, or conflicting provision should trigger targeted follow-up retrieval.

The orchestrator must stop when:

- the question is answered with sufficient evidence;
- additional retrieval is unlikely to change the conclusion;
- a bounded tool/resource budget is reached;
- the remaining issue requires evidence outside the legislative corpus.

When stopping because evidence is missing, the answer must identify the missing evidence rather than fabricate closure.

## 7. Relationship traversal policy

Relationship traversal is bounded by depth and node limits. The model should not recursively crawl the entire corpus because humans already invented enough ways to waste computational resources.

Default behavior:

- depth 1 for ordinary relationship inspection;
- depth 2 for dependency analysis;
- depth 3 only for explicit multi-hop research;
- hard node/result caps at the retrieval layer;
- deduplicate visited nodes and edges;
- preserve relationship type and reference text.

The orchestrator should prefer explicit relationships over semantic guesses when both are available.

## 8. Temporal reasoning policy

A temporal question changes the retrieval plan.

For `What did section X say in 2019?` the orchestrator must not answer from today's `law_sections` row. It must retrieve the applicable historical section version and its supporting history events.

For `When did X change?`, it should retrieve candidate versions, compare their text, and retrieve intervening legislative events.

For `Why did X change?`, section history alone is insufficient. The orchestrator should retrieve the relevant bill/chapter/history source records when they exist and mark legislative intent as unresolved when the corpus does not establish it.

## 9. Answer construction

The final answer has four conceptual layers:

1. **Answer**: direct response to the user's question.
2. **Authority**: the provisions and historical sources establishing the relevant facts.
3. **Analysis**: reasoning performed over those authorities.
4. **Limits**: unresolved propositions or evidence outside the corpus.

The model should not dump the research plan into every response. The plan is an internal research process. The answer exposes the evidence and reasoning necessary for auditability.

## 10. Failure handling

Tool failures and evidence absence are different conditions.

- Tool failure: retrieval operation failed technically. Report a retrieval limitation and do not claim the evidence was searched successfully.
- No result: the operation completed and found no matching corpus record. Treat this as evidence absence, not proof that the proposition is false.
- Ambiguous reference: resolve from conversation context or retrieve candidate authorities. Do not silently choose an arbitrary section.
- Conflicting versions: preserve both versions and compare them.
- Conflicting source records: expose the conflict and identify the source records.

## 11. Provider boundary

The orchestrator must not depend on a specific LLM vendor. Provider adapters implement:

```text
model(messages, tools, state) -> tool calls or final response
```

The application owns tool definitions, evidence normalization, citation resolution, limits, provenance, and state transitions.

This keeps the deterministic research substrate replaceable independently of the model provider and prevents a provider's retrieval abstraction from becoming the application's legal data model.

## 12. Non-goals

The orchestrator is not:

- a generic chatbot;
- a replacement for the authoritative source;
- a legal-outcome predictor;
- a citation generator that invents authority;
- a single FTS query wrapped in a prompt;
- an unbounded autonomous crawler;
- a mechanism for turning generated summaries into source records.

## 13. Acceptance criteria

The architecture is working when a complex question can produce an inspectable chain such as:

```text
user question
  -> identified issue
  -> exact authorities
  -> definitions
  -> explicit relationships
  -> relevant history/version
  -> comparison or graph
  -> evidence-backed findings
  -> verified citations
  -> answer
```

A longer answer is not evidence of deeper research. A deeper research system is one that can identify what must be retrieved, retrieve it through distinct operations, reason over the resulting evidence, recognize what remains unknown, and preserve the path from conclusion back to source.
