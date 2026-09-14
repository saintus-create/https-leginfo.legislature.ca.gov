# Legislative Research Skill

Use this workflow for any natural-language California legislative question.

1. Normalize the question and resolve named codes, sections, dates, actors, and concepts.
2. Classify intent: lookup, explanation, comparison, investigation, chronology, or synthesis.
3. Build a bounded research plan. Prefer exact section lookup when a citation is present; use code-scoped FTS for concepts; traverse section relationships for cross-references; query history for temporal questions.
4. Preserve primary-source evidence separately from AI analysis.
5. For comparisons, retrieve evidence for each subject independently before identifying commonality. Similar vocabulary is not evidence of legal relationship.
6. Cite the exact statutory section supporting each substantive proposition.
7. Mark unsupported propositions as unresolved rather than filling gaps with model knowledge.
8. Keep traversal and result limits explicit so research is deterministic and resource-bounded.
9. Historical answers must use versioned text and dated events. Current text alone is not historical evidence.
10. The final answer should distinguish Short answer, Evidence, Statutory connections, Analysis, Limits, and Sources.

The orchestrator implementation is `src/worker/orchestrator.ts`; retrieval is `src/worker/retrieval.ts`. The public research endpoint is `POST /api/research` with `{ "query": "..." }`.

Production requires a dedicated D1 database containing migrations `0001_legislative_retrieval.sql` and `0002_temporal_history.sql`, plus the Workers AI binding configured in `wrangler.toml`.
