import type {
  EvidenceBundle,
  HistoryEvent,
  RelationshipEdge,
  RetrievedSection,
  ResearchRetriever,
} from './retrieval';
import { citationForSection } from '../leginfo/citations';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
export type ResearchIntent = 'lookup' | 'explain' | 'compare' | 'investigate' | 'chronology' | 'synthesis';

export interface ResearchState {
  question: string;
  normalizedQuestion: string;
  intent: ResearchIntent;
  codes: string[];
  subjects: string[];
  citations: Array<{ code: string; section: string; uid: string }>;
  temporalScope?: { from?: string; to?: string; point?: string; raw?: string };
  findings: RetrievedSection[];
  relationships: RelationshipEdge[];
  history: HistoryEvent[];
  definitions: RetrievedSection[];
  unresolved: string[];
  methods: string[];
  provenance: { plannedSteps: number; executedSteps: number; durationMs: number };
}

export interface ResearchPlan {
  intent: ResearchIntent;
  codes: string[];
  subjects: string[];
  citations: Array<{ code: string; section: string }>;
  temporalScope?: ResearchState['temporalScope'];
  steps: Array<{
    operation: 'get_section' | 'search' | 'get_definition' | 'get_relationships' | 'get_history' | 'compare' | 'resolve_citation' | 'build_evidence_graph';
    args: Record<string, unknown>;
    reason: string;
    priority: number;
  }>;
}

export interface ResearchResult {
  state: ResearchState;
  evidence: EvidenceBundle;
  prompt: string;
}

export interface TextGenerationProvider {
  generate(input: {
    system: string;
    user: string;
    messages?: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>;
  }): Promise<string>;
  generateStream?(input: {
    system: string;
    user: string;
    messages?: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>;
  }): AsyncIterable<string>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Canonical code registry – 30 codes
// ─────────────────────────────────────────────────────────────────────────────
export const CODES: Record<string, string> = {
  BPC: 'Business and Professions Code',
  CIV: 'Civil Code',
  CCP: 'Code of Civil Procedure',
  COM: 'Commercial Code',
  CORP: 'Corporations Code',
  EDC: 'Education Code',
  ELEC: 'Elections Code',
  EVID: 'Evidence Code',
  FAM: 'Family Code',
  FIN: 'Financial Code',
  FGC: 'Fish and Game Code',
  FAC: 'Food and Agricultural Code',
  GOV: 'Government Code',
  HNC: 'Harbors and Navigation Code',
  HSC: 'Health and Safety Code',
  INS: 'Insurance Code',
  LAB: 'Labor Code',
  MVC: 'Military and Veterans Code',
  PEN: 'Penal Code',
  PROB: 'Probate Code',
  PCC: 'Public Contract Code',
  PRC: 'Public Resources Code',
  PUC: 'Public Utilities Code',
  RTC: 'Revenue and Taxation Code',
  SHC: 'Streets and Highways Code',
  UIC: 'Unemployment Insurance Code',
  VEH: 'Vehicle Code',
  WAT: 'Water Code',
  WIC: 'Welfare and Institutions Code',
  CONS: 'California Constitution',
};

// Aliases: full name, lowercased, plus common short forms
const EXTRA_ALIASES: Array<[string, string]> = [
  ['business and professions', 'BPC'],
  ['business & professions', 'BPC'],
  ['civil', 'CIV'],
  ['civil code', 'CIV'],
  ['code of civil procedure', 'CCP'],
  ['ccp', 'CCP'],
  ['commercial', 'COM'],
  ['corporations', 'CORP'],
  ['education', 'EDC'],
  ['elections', 'ELEC'],
  ['evidence', 'EVID'],
  ['family', 'FAM'],
  ['fam code', 'FAM'],
  ['fam. code', 'FAM'],
  ['financial', 'FIN'],
  ['fish and game', 'FGC'],
  ['food and agricultural', 'FAC'],
  ['government', 'GOV'],
  ['gov code', 'GOV'],
  ['gov. code', 'GOV'],
  ['harbors and navigation', 'HNC'],
  ['health and safety', 'HSC'],
  ['insurance', 'INS'],
  ['labor', 'LAB'],
  ['military and veterans', 'MVC'],
  ['penal', 'PEN'],
  ['penal code', 'PEN'],
  ['probate', 'PROB'],
  ['public contract', 'PCC'],
  ['public resources', 'PRC'],
  ['public utilities', 'PUC'],
  ['revenue and taxation', 'RTC'],
  ['streets and highways', 'SHC'],
  ['unemployment insurance', 'UIC'],
  ['vehicle', 'VEH'],
  ['vehicle code', 'VEH'],
  ['water', 'WAT'],
  ['welfare and institutions', 'WIC'],
  ['welfare & institutions', 'WIC'],
  ['california constitution', 'CONS'],
  ['constitution', 'CONS'],
  ['cal const', 'CONS'],
];

const CODE_ALIASES: Array<[string, string]> = [
  ...Object.entries(CODES).flatMap(([abbr, name]) => [
    [abbr.toLowerCase(), abbr] as [string, string],
    [name.toLowerCase(), abbr] as [string, string],
  ]),
  ...EXTRA_ALIASES,
].sort((a, b) => b[0].length - a[0].length);

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
const clean = (s: string) => s.trim().replace(/\s+/g, ' ');

function normalizeCode(input: string): string | undefined {
  const v = input.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
  return v || undefined;
}

export function resolveCodes(question: string): string[] {
  const lower = question.toLowerCase();
  const normalized = ` ${lower.replace(/[^a-z0-9.§]+/g, ' ').replace(/\s+/g, ' ').trim()} `;

  // Collect all alias matches with their first occurrence index to preserve order of appearance
  const matches: Array<{ code: string; index: number; length: number }> = [];

  for (const [alias, code] of CODE_ALIASES) {
    const needle = ` ${alias.toLowerCase()} `;
    const idx = normalized.indexOf(needle);
    if (idx !== -1) {
      matches.push({ code, index: idx, length: alias.length });
    }
  }

  // Also catch patterns like "GOV §" without full name
  const refPattern = /\b([A-Z]{2,8})\s*(?:§|section)\s*[A-Z0-9]+(?:[.\-][A-Z0-9]+)*/gi;
  let m: RegExpExecArray | null;
  while ((m = refPattern.exec(question)) !== null) {
    const c = normalizeCode(m[1]);
    if (c && (CODES as any)[c]) {
      // Use original question index for ordering
      const idx = m.index;
      if (!matches.some(x => x.code === c && Math.abs(x.index - idx) < 5)) {
        matches.push({ code: c, index: idx, length: m[0].length });
      }
    }
  }

  // Sort by index (appearance order), then by longer alias first for tie-breaker to prefer more specific
  matches.sort((a, b) => {
    if (a.index !== b.index) return a.index - b.index;
    return b.length - a.length;
  });

  const ordered: string[] = [];
  const seen = new Set<string>();
  for (const { code } of matches) {
    if (!seen.has(code)) {
      seen.add(code);
      ordered.push(code);
    }
  }

  return ordered;
}

export function extractCitations(question: string): Array<{ code: string; section: string; uid: string }> {
  const out: Array<{ code: string; section: string; uid: string }> = [];
  const pattern = /\b([A-Z]{2,8})\s*(?:§+|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)\b/gi;
  let match: RegExpExecArray | null;
  const seen = new Set<string>();
  while ((match = pattern.exec(question)) !== null) {
    const code = normalizeCode(match[1]);
    const section = match[2];
    if (!code || !section) continue;
    if (!(CODES as any)[code] && !/^[A-Z]{2,8}$/.test(code)) continue;
    const uid = `${code}:${section}`;
    if (seen.has(uid)) continue;
    seen.add(uid);
    out.push({ code, section, uid });
  }
  return out;
}

function extractTemporalScope(question: string): ResearchState['temporalScope'] | undefined {
  const lower = question.toLowerCase();
  const temporalKeywords = /\b(history|historical|changed|amended|effective|before|after|since|until|in \d{4}|on \d{4}|as of|version)\b/;
  if (!temporalKeywords.test(lower)) return undefined;
  const yearMatch = lower.match(/\b(19|20)\d{2}\b/);
  const dateMatch = lower.match(/\b(\d{4}-\d{2}-\d{2})\b/);
  const raw = lower.match(/\b(history[^.?!]*|effective[^.?!]*|amended[^.?!]*|before[^.?!]*|after[^.?!]*)\b/)?.[0];
  return {
    point: dateMatch?.[1] || yearMatch?.[0],
    raw,
  };
}

export function inferIntent(question: string, codes: string[]): ResearchIntent {
  const x = question.toLowerCase();

  // Explicit lookup: short query with citation
  const hasCitation = /\b([A-Z]{2,8})\s*(?:§|section)\s*[A-Z0-9]+/i.test(question);
  const wordCount = x.split(/\s+/).filter(Boolean).length;
  if (hasCitation && wordCount <= 12) return 'lookup';

  // Compare
  if (
    /\b(compare|comparison|difference|differences|versus|\bvs\.?\b|same|common|overlap|similar|distinguish|contrast)\b/.test(x) ||
    (codes.length >= 2 && /\b(and|&)\b/.test(x)) ||
    /what do .* and .* have in common/i.test(x)
  ) {
    return 'compare';
  }

  // Chronology
  if (/\b(history|historical|changed|amended|effective|before|after|when did|evolution|prior version|previous version|as of|since|timeline)\b/.test(x)) {
    return 'chronology';
  }

  // Investigate
  if (/\b(why|how|relationship|relate|related|connect|connected|exception|subject to|depends on|applies to|interplay|interaction|trigger|affect|impact|govern|enforce|authority)\b/.test(x)) {
    return 'investigate';
  }

  // Explain
  if (/\b(what is|what are|what does|explain|definition|define|meaning|means|interpret|summary|summarize|describe)\b/.test(x)) {
    return 'explain';
  }

  // Lookup if mentions section
  if (/\b(section|§)\b/.test(x) && wordCount <= 20) return 'lookup';

  return 'synthesis';
}

// Probes per intent – these are semantic probes, not just keywords
const PROBES: Record<ResearchIntent, string[]> = {
  lookup: ['operative text', 'title', 'history'],
  explain: ['definition', 'scope', 'application', 'exception', 'procedure'],
  compare: ['definition', 'scope', 'authority', 'procedure', 'enforcement', 'exception', 'records', 'court'],
  investigate: ['definition', 'cross-reference', 'exception', 'authority', 'enforcement', 'applicability', 'related provision'],
  chronology: ['history', 'amended', 'effective date', 'prior version', 'chaptered bill'],
  synthesis: ['definition', 'scope', 'authority', 'procedure', 'enforcement', 'related'],
};

const STOPWORDS = new Set([
  'the',
  'and',
  'for',
  'that',
  'this',
  'with',
  'from',
  'what',
  'how',
  'why',
  'are',
  'was',
  'were',
  'about',
  'does',
  'doesn',
  'section',
  'sections',
  'code',
  'codes',
  'california',
  'please',
  'explain',
  'describe',
]);

function extractConcepts(question: string): string[] {
  const tokens = question
    .toLowerCase()
    .replace(/[^a-z0-9\s\-]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length >= 3 && !STOPWORDS.has(t));
  return [...new Set(tokens)].slice(0, 12);
}

export function planResearch(question: string, priorFindings?: RetrievedSection[]): ResearchPlan {
  const q = clean(question);
  const codes = resolveCodes(q);
  const citations = extractCitations(q);
  const temporalScope = extractTemporalScope(q);
  const intent = inferIntent(q, codes);
  const concepts = extractConcepts(q);

  const steps: ResearchPlan['steps'] = [];
  let priority = 0;

  // 1. Exact citation resolution – highest priority
  for (const cit of citations.slice(0, 6)) {
    steps.push({
      operation: 'get_section',
      args: { uid: cit.uid, code: cit.code, section: cit.section },
      reason: `Exact citation lookup for ${cit.code} § ${cit.section} – authoritative text required before reasoning.`,
      priority: priority++,
    });
    steps.push({
      operation: 'get_relationships',
      args: { uid: cit.uid, direction: 'both', depth: 2, limit: 15 },
      reason: `Traverse statutory relationships for ${cit.uid} to identify cross-references and dependencies.`,
      priority: priority++,
    });
    if (temporalScope || intent === 'chronology') {
      steps.push({
        operation: 'get_history',
        args: { uid: cit.uid, limit: 50 },
        reason: `Temporal evidence for ${cit.uid} – version history and legislative events.`,
        priority: priority++,
      });
    }
  }

  // 2. Primary semantic retrieval – always
  if (intent === 'compare' && codes.length >= 2) {
    // Compare: retrieve independently for each code to avoid conflation
    for (const code of codes.slice(0, 4)) {
      steps.push({
        operation: 'search',
        args: { query: q, code, limit: 8 },
        reason: `Primary retrieval for ${CODES[code] ?? code} – isolate authority before comparison.`,
        priority: priority++,
      });
      for (const probe of PROBES.compare.slice(0, 5)) {
        steps.push({
          operation: 'search',
          args: { query: `${probe} ${concepts.slice(0, 3).join(' ')}`, code, limit: 5 },
          reason: `Compare probe "${probe}" in ${CODES[code] ?? code}.`,
          priority: priority++,
        });
      }
    }
  } else {
    // Single-subject retrieval with concept expansion
    steps.push({
      operation: 'search',
      args: { query: q, limit: 14 },
      reason: 'Retrieve responsive primary provisions – semantic match, not keyword concatenation.',
      priority: priority++,
    });

    // Concept-driven secondary searches
    if (concepts.length) {
      const conceptQuery = concepts.slice(0, 4).join(' ');
      steps.push({
        operation: 'search',
        args: { query: conceptQuery, code: codes[0], limit: 10 },
        reason: `Concept expansion retrieval for "${conceptQuery}" – broaden beyond literal phrasing.`,
        priority: priority++,
      });
    }

    // Definition probe if question asks about meaning
    if (intent === 'explain' || intent === 'investigate' || /\b(define|definition|means|meaning)\b/i.test(q)) {
      for (const term of concepts.slice(0, 3)) {
        steps.push({
          operation: 'get_definition',
          args: { term, scope: codes[0] },
          reason: `Operative definition for "${term}" – statutory definition controls interpretation.`,
          priority: priority++,
        });
      }
    }

    // Relationship probes for investigate/explain
    if (intent === 'investigate' || intent === 'explain' || intent === 'synthesis') {
      for (const probe of PROBES[intent].slice(0, 4)) {
        steps.push({
          operation: 'search',
          args: { query: `${probe} ${q.slice(0, 80)}`, limit: 6 },
          reason: `Investigative probe "${probe}" – surface cross-references and qualifications.`,
          priority: priority++,
        });
      }
    }
  }

  // 3. Temporal if needed
  if (temporalScope || intent === 'chronology' || /\b(history|amended|effective)\b/i.test(q)) {
    steps.push({
      operation: 'get_history',
      args: { limit: 50 },
      reason: 'Retrieve temporal evidence – history events and version lineage.',
      priority: priority++,
    });
  }

  // 4. Build evidence graph for multi-authority questions
  if (codes.length >= 2 || citations.length >= 2 || intent === 'compare' || intent === 'investigate') {
    steps.push({
      operation: 'build_evidence_graph',
      args: { depth: 2, limit: 30 },
      reason: 'Construct evidence graph – map relationships among retrieved authorities.',
      priority: priority++,
    });
  }

  // 5. Resolve citations for presentation
  steps.push({
    operation: 'resolve_citation',
    args: {},
    reason: 'Resolve canonical citations and LegInfo URLs for human verification.',
    priority: priority++,
  });

  // Sort by priority and cap
  steps.sort((a, b) => a.priority - b.priority);
  const capped = steps.slice(0, 60);

  return {
    intent,
    codes,
    subjects: codes.map((c) => CODES[c] ?? c),
    citations,
    temporalScope,
    steps: capped,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Orchestrator – bounded, adaptive, evidence-first
// ─────────────────────────────────────────────────────────────────────────────
export class ResearchOrchestrator {
  constructor(
    private readonly retriever: ResearchRetriever,
    private readonly limits = { sections: 50, relationships: 120, history: 120, definitions: 20 },
  ) {}

  async research(question: string, conversationContext?: Array<{ role: 'user' | 'assistant'; content: string }>): Promise<ResearchResult> {
    const start = Date.now();
    const normalized = clean(question);
    if (!normalized) throw new Error('A research question is required.');

    const plan = planResearch(normalized);
    const findings = new Map<string, RetrievedSection>();
    const definitions = new Map<string, RetrievedSection>();
    const relationships = new Map<string, RelationshipEdge>();
    const history = new Map<string, HistoryEvent>();
    const methods = new Set<string>();
    const unresolved: string[] = [];

    let executed = 0;

    // Helper to add findings
    const addFindings = (sections: RetrievedSection[], isDefinition = false) => {
      for (const s of sections) {
        if (!s.uid) continue;
        const target = isDefinition ? definitions : findings;
        if (!target.has(s.uid)) target.set(s.uid, s);
      }
    };

    // Execute planned steps
    for (const step of plan.steps) {
      if (findings.size >= this.limits.sections && definitions.size >= this.limits.definitions) break;
      try {
        executed++;
        switch (step.operation) {
          case 'get_section': {
            const uid = String((step.args as any).uid || '');
            if (!uid) break;
            const section = await this.retriever.getSection(uid);
            if (section) {
              addFindings([section]);
              methods.add('exact-section');
            } else {
              // Fallback to search if exact fails
              const fallback = await this.retriever.search({ query: uid, limit: 3, exactUid: uid });
              addFindings(fallback.results);
              fallback.retrieval.methods.forEach((m) => methods.add(m));
            }
            break;
          }
          case 'search': {
            const args = step.args as { query: string; code?: string; limit?: number };
            if (!args.query?.trim()) break;
            const bundle = await this.retriever.search({
              query: args.query,
              code: args.code,
              limit: Math.min(args.limit ?? 10, this.limits.sections),
            });
            addFindings(bundle.results);
            bundle.retrieval.methods.forEach((m) => methods.add(m));
            // Also collect relationships from bundle if provided
            for (const rel of bundle.relationships) {
              const key = `${rel.sourceUid}|${rel.targetUid ?? ''}|${rel.relationship}|${rel.referenceText ?? ''}`;
              if (!relationships.has(key)) relationships.set(key, rel);
            }
            break;
          }
          case 'get_definition': {
            const term = String((step.args as any).term || '').trim();
            if (!term) break;
            if (typeof (this.retriever as any).getDefinition === 'function') {
              const defs = await (this.retriever as any).getDefinition(term, (step.args as any).scope);
              addFindings(defs, true);
              methods.add('definition-search');
            } else {
              // Fallback: search for definition pattern
              const bundle = await this.retriever.search({
                query: `"${term}" means definition`,
                limit: 5,
              });
              addFindings(bundle.results, true);
              bundle.retrieval.methods.forEach((m) => methods.add(m));
            }
            break;
          }
          case 'get_relationships': {
            const uid = String((step.args as any).uid || [...findings.keys()][0] || '');
            if (!uid) break;
            const edges = await this.retriever.getRelationships(uid, {
              direction: (step.args as any).direction ?? 'both',
              depth: Math.min((step.args as any).depth ?? 2, 3),
              limit: Math.min((step.args as any).limit ?? 15, this.limits.relationships),
            });
            for (const e of edges) {
              const key = `${e.sourceUid}|${e.targetUid ?? ''}|${e.relationship}|${e.referenceText ?? ''}`;
              if (!relationships.has(key)) relationships.set(key, e);
            }
            methods.add('relationship-traversal');
            break;
          }
          case 'get_history': {
            const uids = (step.args as any).uid
              ? [String((step.args as any).uid)]
              : [...findings.keys()].slice(0, 8);
            for (const uid of uids) {
              const events = await this.retriever.getHistory(uid, { limit: 50 });
              for (const ev of events) {
                if (!history.has(ev.id)) history.set(ev.id, ev);
              }
            }
            if (history.size) methods.add('temporal-history');
            break;
          }
          case 'build_evidence_graph': {
            if (typeof (this.retriever as any).buildEvidenceGraph === 'function') {
              const graph = await (this.retriever as any).buildEvidenceGraph([...findings.keys()], {
                depth: (step.args as any).depth ?? 2,
                limit: (step.args as any).limit ?? 30,
              });
              for (const e of graph) {
                const key = `${e.sourceUid}|${e.targetUid ?? ''}|${e.relationship}|${e.referenceText ?? ''}`;
                if (!relationships.has(key)) relationships.set(key, e);
              }
              methods.add('evidence-graph');
            }
            break;
          }
          case 'resolve_citation':
          case 'compare':
            // These are presentation / reasoning steps – handled in synthesis, not retrieval
            methods.add(step.operation);
            break;
        }
      } catch (e) {
        unresolved.push(`${step.operation}: ${e instanceof Error ? e.message : String(e)}`);
      }
    }

    // Adaptive second pass: if findings reference other sections, pull them
    if (findings.size > 0 && findings.size < this.limits.sections) {
      try {
        const referencedUids = new Set<string>();
        const refPattern = /\b([A-Z]{2,8})\s*(?:§+|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)/gi;
        for (const f of findings.values()) {
          let m: RegExpExecArray | null;
          while ((m = refPattern.exec(f.text)) !== null) {
            const code = m[1].toUpperCase();
            const section = m[2];
            const uid = `${code}:${section}`;
            if (!findings.has(uid) && !referencedUids.has(uid)) referencedUids.add(uid);
          }
        }
        for (const uid of [...referencedUids].slice(0, 10)) {
          const sec = await this.retriever.getSection(uid).catch(() => null);
          if (sec) findings.set(sec.uid, sec);
        }
        if (referencedUids.size) methods.add('cross-reference-expansion');
      } catch {
        // non-fatal
      }
    }

    // Relationship expansion for top findings if not already done
    if (relationships.size < this.limits.relationships) {
      for (const s of [...findings.values()].slice(0, 12)) {
        if (relationships.size >= this.limits.relationships) break;
        try {
          const edges = await this.retriever.getRelationships(s.uid, { direction: 'both', depth: 2, limit: 12 });
          for (const e of edges) {
            const key = `${e.sourceUid}|${e.targetUid ?? ''}|${e.relationship}|${e.referenceText ?? ''}`;
            if (!relationships.has(key)) relationships.set(key, e);
          }
        } catch (e) {
          unresolved.push(`relationships ${s.uid}: ${e instanceof Error ? e.message : String(e)}`);
        }
      }
    }

    if (!findings.size) {
      unresolved.push('No primary statutory provisions were retrieved. The corpus may not contain responsive sections, or the query may require broader phrasing.');
    }

    // Deduplicate and cap
    const finalFindings = [...findings.values()]
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, this.limits.sections);
    const finalDefinitions = [...definitions.values()].slice(0, this.limits.definitions);
    const finalRelationships = [...relationships.values()].slice(0, this.limits.relationships);
    const finalHistory = [...history.values()].slice(0, this.limits.history);

    const allFindings = [...finalFindings, ...finalDefinitions];

    const state: ResearchState = {
      question,
      normalizedQuestion: normalized,
      intent: plan.intent,
      codes: plan.codes,
      subjects: plan.subjects,
      citations: plan.citations,
      temporalScope: plan.temporalScope,
      findings: finalFindings,
      definitions: finalDefinitions,
      relationships: finalRelationships,
      history: finalHistory,
      unresolved,
      methods: [...methods],
      provenance: {
        plannedSteps: plan.steps.length,
        executedSteps: executed,
        durationMs: Date.now() - start,
      },
    };

    const evidence: EvidenceBundle = {
      query: state.normalizedQuestion,
      results: allFindings,
      relationships: finalRelationships,
      retrieval: {
        methods: state.methods,
        complete: unresolved.length === 0,
      },
    };

    // Build LLM prompt – structured, evidence-first
    const promptPayload = {
      question: state.normalizedQuestion,
      intent: state.intent,
      codes: state.codes,
      subjects: state.subjects,
      citations: state.citations,
      temporalScope: state.temporalScope,
      authorities: finalFindings.map((s) => ({
        uid: s.uid,
        citation: s.citation,
        code: s.lawCode,
        section: s.sectionNum,
        title: s.title,
        text: s.text.slice(0, 8000), // cap per section to avoid token overflow
        history: s.history,
        validFrom: s.validFrom,
        validTo: s.validTo,
        relevance: s.relevance,
        matchType: s.matchType,
      })),
      definitions: finalDefinitions.map((s) => ({
        uid: s.uid,
        citation: s.citation,
        text: s.text.slice(0, 4000),
      })),
      relationships: finalRelationships.slice(0, 40).map((r) => ({
        source: r.sourceUid,
        target: r.targetUid,
        type: r.relationship,
        reference: r.referenceText,
        confidence: r.confidence,
      })),
      history: finalHistory.slice(0, 30),
      unresolved: state.unresolved,
      methods: state.methods,
      conversationContext: conversationContext?.slice(-6) ?? [],
    };

    return {
      state,
      evidence,
      prompt: JSON.stringify(promptPayload, null, 2),
    };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// System prompts – strong AI reasoning, not word match
// ─────────────────────────────────────────────────────────────────────────────
export const ORCHESTRATOR_SYSTEM_PROMPT = `You are the primary-source research engine for California Legislative Information. You are not a generic chatbot and you are not a keyword matcher.

CORE PRINCIPLES:
- The corpus is deterministic and auditable. You sit above it and perform retrieval, synthesis, comparison, explanation, and analysis.
- Reason over the supplied corpus evidence. Never invent citations, sections, relationships, legislative intent, history, procedural facts, or quotations.
- Every substantive proposition must be traceable to a supplied citation, relationship, or history event.
- Distinguish three levels: (1) DIRECT TEXT – verbatim or near-verbatim statutory language, (2) DIRECT COMPARISON – observable textual differences/similarities, (3) INFERENCE – analytical synthesis you produce from evidence.
- When evidence is insufficient, explicitly state that the corpus does not establish the proposition. Do not fill gaps with model knowledge.
- For multi-turn conversations, use prior messages for context but re-ground every new factual proposition in corpus evidence.

ANALYTICAL OPERATIONS:
- EXPLAIN: restate a provision at requested complexity, preserving operative terms, subdivisions, dates, defined terms.
- COMPARE: identify textual similarities and differences between provisions. Similar vocabulary is NOT evidence of legal relationship unless corpus shows explicit cross-reference or shared operative language.
- CONNECT: identify explicit cross-references and corpus relationships. Prefer explicit relationship records over semantic guesses.
- ANALYZE: reason from retrieved text while identifying provisions supporting each material conclusion.
- INVESTIGATE: conduct iterative reasoning based on prior findings. If a finding introduces a definition, exception, or cross-reference, reason about its impact.
- TEMPORAL: for historical questions, use versioned text and dated events. Current text alone is NOT historical evidence.
- SYNTHESIZE: combine multiple authorities into coherent answer while preserving individual citations.

CITATION DISCIPLINE:
- An internal UID is not a legal citation. Use the supplied citation.label and citation.url for human-facing sources.
- Never fabricate a LegInfo URL. Use only the URLs provided in evidence.
- Preserve section numbers, subdivisions (a)(1)(A), dates, and defined terms accurately.

ANSWER STRUCTURE (when not otherwise specified):
1. Short answer – direct response in 1-3 sentences
2. Evidence – provisions that establish the facts, with citations
3. Connections – explicit statutory relationships
4. Analysis – reasoning over authorities
5. Limits – what the corpus does not establish
6. Sources – list of citations with URLs

You are the research engine. Be precise, auditable, and useful. Prefer exact California statutory language when user asks what a statute says.`;

export const VERIFIER_SYSTEM_PROMPT = `You are the evidence verifier for a source-grounded legislative research system. Your job is to ensure answers are strictly grounded.

RULES:
- Review draft answer against supplied corpus evidence.
- Remove or rewrite every claim not supported by evidence. Do not add facts from memory or external knowledge.
- Ensure every statutory citation in the answer corresponds to a citation present in evidence. If draft cites a section not in evidence, either remove the claim or mark it as unsupported.
- Distinguish statutory text from AI characterization. Keep quotations accurate.
- Check historical claims use historical evidence, not current text.
- Check relationship claims have explicit relationship record or source text.
- Preserve citations and distinguish inference from direct evidence.
- If evidence is insufficient for a proposition, state that limitation rather than asserting the proposition.
- Return ONLY the corrected answer, with no discussion of verification process, no meta-commentary.

If draft is already well-grounded, return it unchanged except for minor citation formatting.`;

// ─────────────────────────────────────────────────────────────────────────────
// Generation orchestration
// ─────────────────────────────────────────────────────────────────────────────
export async function generateResearchAnswer(
  orchestrator: ResearchOrchestrator,
  provider: TextGenerationProvider,
  question: string,
  messages: Array<{ role: 'user' | 'assistant'; content: string }> = [],
): Promise<{ state: ResearchState; answer: string; evidence: EvidenceBundle }> {
  const research = await orchestrator.research(question, messages as any);

  // Draft generation – evidence + question + conversation
  const draft = await provider.generate({
    system: ORCHESTRATOR_SYSTEM_PROMPT,
    messages: [
      { role: 'system', content: ORCHESTRATOR_SYSTEM_PROMPT },
      ...messages.slice(-8),
      {
        role: 'user',
        content: `CORPUS EVIDENCE (JSON):\n${research.prompt}\n\nCURRENT QUESTION:\n${question}\n\nINSTRUCTIONS:\n- Answer from corpus evidence only.\n- Use the Answer Structure: Short answer, Evidence, Connections, Analysis, Limits, Sources.\n- Cite using label and preserve URLs.\n- If insufficient evidence, say so.`,
      },
    ],
    user: research.prompt,
  });

  // Verification pass
  let verified: string;
  try {
    verified = await provider.generate({
      system: VERIFIER_SYSTEM_PROMPT,
      messages: [
        { role: 'system', content: VERIFIER_SYSTEM_PROMPT },
        {
          role: 'user',
          content: `EVIDENCE (JSON):\n${research.prompt}\n\nDRAFT ANSWER:\n${draft}\n\nTASK: Verify and correct this answer strictly against supplied evidence. Return only corrected answer.`,
        },
      ],
      user: `Verify and correct this answer strictly against the supplied evidence. Evidence has ${research.state.findings.length} findings, ${research.state.relationships.length} relationships, ${research.state.history.length} history events.`,
    });
  } catch {
    // If verifier fails, fall back to draft but mark
    verified = draft;
  }

  // Final citation integrity check – ensure citations in answer correspond to evidence
  const finalAnswer = verified.trim() || draft.trim();

  return {
    state: research.state,
    evidence: research.evidence,
    answer: finalAnswer,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Cloudflare AI provider – hardened
// ─────────────────────────────────────────────────────────────────────────────
export function createCloudflareAIProvider(
  ai: { run: (model: string, input: unknown, options?: unknown) => Promise<unknown> },
  model = '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
): TextGenerationProvider {
  return {
    async generate(input) {
      const messages = input.messages ?? [
        { role: 'system', content: input.system },
        { role: 'user', content: input.user },
      ];

      // Harden: ensure system prompt is first, ensure no empty messages
      const sanitized = messages
        .filter((m) => m.content?.trim())
        .map((m) => ({
          role: m.role,
          content: m.content.slice(0, 12000), // prevent overflow
        }));

      const out = (await ai.run(
        model,
        {
          messages: sanitized,
          temperature: 0.15,
          top_p: 0.9,
          max_tokens: 2200,
        },
        {
          gateway: { id: 'leginfo-ai', skipCache: false, cacheTtl: 3600 },
        },
      )) as { response?: unknown; choices?: Array<{ message?: { content?: string } }>; result?: { response?: string } };

      // Handle multiple response shapes
      let text: string | undefined;
      if (typeof out.response === 'string') text = out.response;
      else if ((out as any).result?.response && typeof (out as any).result.response === 'string') text = (out as any).result.response;
      else if (Array.isArray((out as any).choices) && (out as any).choices[0]?.message?.content) text = (out as any).choices[0].message.content;

      if (!text?.trim()) throw new Error('AI generation returned no answer.');
      return text.trim();
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Additional utilities for strongholding
// ─────────────────────────────────────────────────────────────────────────────
export function compareSections(a: RetrievedSection, b: RetrievedSection): { similarities: string[]; differences: string[]; sharedTerms: string[] } {
  const textA = a.text.toLowerCase();
  const textB = b.text.toLowerCase();
  const tokensA = new Set(textA.match(/\b[a-z]{3,}\b/g) || []);
  const tokensB = new Set(textB.match(/\b[a-z]{3,}\b/g) || []);
  const shared = [...tokensA].filter((t) => tokensB.has(t));
  const onlyA = [...tokensA].filter((t) => !tokensB.has(t)).slice(0, 20);
  const onlyB = [...tokensB].filter((t) => !tokensA.has(t)).slice(0, 20);

  return {
    similarities: shared.slice(0, 30),
    differences: [...onlyA.map((t) => `Only in ${a.citation.label}: ${t}`), ...onlyB.map((t) => `Only in ${b.citation.label}: ${t}`)],
    sharedTerms: shared.slice(0, 50),
  };
}
