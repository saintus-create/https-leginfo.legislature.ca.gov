# AI System Architecture

The application is an AI-first interface to an authoritative California legislative corpus. It is not an ordinary legislative search site with an AI search box attached.

## Core principle

The corpus is deterministic and auditable. The AI sits above the corpus and performs retrieval, synthesis, comparison, explanation, analysis, and conversation. AI output must remain traceable to the underlying legislative evidence.

```text
User conversation
      |
      v
AI orchestration
  |       |       |
  |       |       +--> citation/source resolver
  |       +----------> analysis/comparison tools
  +------------------> retrieval
                          |
                          v
                 authoritative corpus
                          |
                          v
                 section-level evidence
```

## AI surfaces

AI should be used wherever it adds analytical value:

- conversational legislative research
- semantic and keyword search
- plain-language explanation of statutes
- section-to-section comparison
- statutory relationship mapping
- definition and cross-reference discovery
- source-grounded legal-text analysis
- document analysis against the legislative corpus
- legislative-history synthesis where source records exist
- citation generation and source resolution
- multi-step conversational investigation
- follow-up questions that preserve relevant evidence context
- synthesis across multiple retrieved provisions

These are separate capabilities even when they share the same retrieval foundation. The product should not reduce all of them to a single generic `/api/search` operation.

## Evidence boundary

The system must preserve a hard distinction between:

1. **Corpus data**: authoritative legislative records and their normalized metadata.
2. **Retrieval**: selection of corpus records relevant to a user request.
3. **AI reasoning**: synthesis, explanation, comparison, and analysis performed from retrieved evidence.
4. **Citation**: a human-readable legal citation resolved to the official California Legislative Information source.
5. **Conversation state**: user questions, selected evidence, and prior analytical context.

An internal UID is not a legal citation. AI responses should expose section-level citations that resolve to the official source URL whenever a source can be identified.

## Grounding requirements

For source-grounded responses:

- retrieve evidence before making substantive corpus claims;
- retain the source record associated with each retrieved passage;
- preserve the legislative code and section identifier;
- resolve citations through the canonical source resolver;
- distinguish quoted/source text from AI-generated analysis;
- do not fabricate statutory sections, citations, legislative history, or source URLs;
- when evidence is insufficient, state that the corpus does not establish the proposition rather than filling the gap with unsupported synthesis.

## Conversation model

A conversation should be able to accumulate an evidence context. A follow-up such as `How does that differ from section 6320?` should reuse the relevant prior section and retrieve the comparison target rather than treating the message as an isolated search query.

Conversation state should not become authoritative evidence. It is context for retrieval and reasoning. The corpus remains the source of record.

## Analysis model

The AI layer should support distinct analytical operations rather than one undifferentiated prompt:

- **Explain**: restate a provision at a requested level of complexity.
- **Compare**: identify textual similarities and differences between provisions or versions.
- **Connect**: identify explicit cross-references and corpus relationships.
- **Analyze**: reason from retrieved text while identifying the provisions supporting each material conclusion.
- **Investigate**: conduct iterative retrieval based on prior findings and user follow-ups.
- **Document analysis**: extract propositions from an uploaded document and compare them against retrieved legislative authority.
- **Synthesize**: combine multiple authoritative records into a coherent answer while preserving individual citations.

## Citation object

The stable interface between AI reasoning and source presentation should carry both machine identity and human source identity:

```ts
interface LegislativeCitation {
  uid: string;
  lawCode: string;
  sectionNum: string;
  label: string;
  url: string;
}
```

`uid` identifies the internal corpus record. `lawCode`, `sectionNum`, `label`, and `url` identify the source that a human can inspect.

## Product direction

The desired user experience is an AI research environment for California legislation, not a static code browser. Static browsing remains available because authoritative text must remain inspectable without trusting the model. The AI layer should nevertheless be the primary means of discovering, understanding, relating, and analyzing that text.

New AI capabilities should be evaluated against one question: **does this use AI to perform useful reasoning over authoritative legislative evidence, or is it merely decorative?** Prefer the former.
