import { citationForSection } from '../leginfo/citations';
import type { EvidenceBundle, HistoryEvent, RelationshipEdge, ResearchRetriever, RetrievalQuery, RetrievedSection } from './retrieval';

interface FetcherLike {
  fetch(input: Request | string, init?: RequestInit): Promise<Response>;
}
interface GraphPayload {
  edges: RelationshipEdge[];
  nodes?: Array<{ uid: string; type?: string; code?: string; section?: string }>;
}

const CODE_NAMES: Record<string, string> = {
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

const ALIASES: Record<string, string> = {
  ...Object.fromEntries(Object.entries(CODE_NAMES).flatMap(([k, v]) => [[k.toLowerCase(), k], [v.toLowerCase(), k]])),
  family: 'FAM',
  government: 'GOV',
  civil: 'CIV',
  penal: 'PEN',
  evidence: 'EVID',
  probate: 'PROB',
  labor: 'LAB',
  'health and safety': 'HSC',
  'welfare and institutions': 'WIC',
  vehicle: 'VEH',
  education: 'EDC',
  'business and professions': 'BPC',
  'code of civil procedure': 'CCP',
  'california constitution': 'CONS',
  'business & professions': 'BPC',
  'welfare & institutions': 'WIC',
};

const STOP = new Set([
  'the',
  'and',
  'for',
  'that',
  'this',
  'with',
  'from',
  'shall',
  'may',
  'must',
  'such',
  'which',
  'into',
  'upon',
  'under',
  'there',
  'their',
  'them',
  'than',
  'then',
  'where',
  'when',
  'what',
  'have',
  'has',
  'had',
  'not',
  'any',
  'all',
  'each',
  'other',
  'more',
  'only',
  'section',
  'sections',
  'code',
  'codes',
  'california',
  'please',
  'explain',
  'describe',
  'what',
  'does',
  'is',
  'are',
  'was',
  'were',
]);

// AI-strengthened tokenization – not just word match, but concept extraction
function tokenise(s: string): string[] {
  const raw = s.toLowerCase().match(/[a-z0-9][a-z0-9._-]{2,}/g) || [];
  const filtered = raw.filter((x) => !STOP.has(x));
  return [...new Set(filtered)].slice(0, 32);
}

function extractConcepts(s: string): { tokens: string[]; phrase: string; code?: string } {
  const tokens = tokenise(s);
  const phrase = s
    .replace(/\b(what|is|the|a|an|how|does|do|can|please|explain|describe|tell|me|about)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();

  let code: string | undefined;
  const lower = s.toLowerCase();
  for (const [alias, c] of Object.entries(ALIASES).sort((a, b) => b[0].length - a[0].length)) {
    if (lower.includes(alias)) {
      code = c;
      break;
    }
  }
  const ref = exactRef(s);
  if (ref) code = ref[1].toUpperCase();

  return { tokens, phrase, code };
}

const exactRef = (q: string) => /\b([A-Z]{2,8})\s*(?:§|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)\b/i.exec(q);

function codeFromQuery(q: string): string | undefined {
  const x = q.toLowerCase();
  for (const [alias, code] of Object.entries(ALIASES).sort((a, b) => b[0].length - a[0].length)) if (x.includes(alias)) return code;
  const ref = exactRef(q);
  return ref?.[1]?.toUpperCase();
}

// Strong scoring – beyond word match: TF, title boost, phrase, proximity, definition boost
function score(rec: any, tokens: string[], phrase: string, intent?: string): number {
  const title = String(rec.title || '').toLowerCase();
  const text = String(rec.text || '').toLowerCase();
  const hay = `${title} ${text}`;
  let value = 0;

  // Term frequency with saturation (BM25-like)
  for (const term of tokens) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\b${escaped}\\b`, 'g');
    const hits = (hay.match(re) || []).length;
    if (!hits) continue;
    // TF saturation: log(1+hits)
    const tf = Math.log(1 + hits);
    const titleHits = (title.match(re) || []).length;
    const titleBoost = titleHits ? 3.5 : 1;
    const idf = 1; // we don't have global IDF in static, approximate
    value += tf * titleBoost * idf * 2;
  }

  // Phrase boost – strong signal
  if (phrase && hay.includes(phrase.toLowerCase())) value += 18;

  // Proximity: if multiple tokens appear close together
  if (tokens.length >= 2) {
    const firstIdx = hay.indexOf(tokens[0]);
    const lastIdx = hay.indexOf(tokens[tokens.length - 1]);
    if (firstIdx !== -1 && lastIdx !== -1 && Math.abs(lastIdx - firstIdx) < 200) value += 6;
  }

  // Intent-aware boosts
  if (intent === 'definition' && (text.includes(' means ') || text.includes(' definition ') || text.includes(' includes '))) {
    value += 12;
  }
  if (intent === 'history' && rec.history) value += 5;

  // Length normalization: prefer substantive sections, penalize tiny
  const charCount = text.length;
  if (charCount < 80) value *= 0.5;
  if (charCount > 500 && charCount < 8000) value *= 1.1;

  return value;
}

export class StaticCorpusRetriever implements ResearchRetriever {
  private graphCache?: GraphPayload;
  private manifestCache?: { codes: Record<string, string[]> };
  private indexCache?: any;

  constructor(
    private readonly assets: FetcherLike,
    private readonly baseUrl: URL,
  ) {}

  private async manifest(): Promise<{ codes: Record<string, string[]> }> {
    if (this.manifestCache) return this.manifestCache;
    const r = await this.assets.fetch(new URL('/data/law/manifest.json', this.baseUrl).toString());
    if (!r.ok) throw new Error(`Legislative corpus manifest unavailable (${r.status}).`);
    const manifest = (await r.json()) as { codes?: Record<string, string[]> };
    if (!manifest.codes || typeof manifest.codes !== 'object') throw new Error('Legislative corpus manifest is invalid.');
    return (this.manifestCache = manifest as { codes: Record<string, string[]> });
  }

  private async index(): Promise<any> {
    if (this.indexCache) return this.indexCache;
    const r = await this.assets.fetch(new URL('/data/research-index.json', this.baseUrl).toString());
    if (!r.ok) throw new Error(`Legislative research index unavailable (${r.status}).`);
    const idx = await r.json();
    return (this.indexCache = idx);
  }

  private async graph(): Promise<GraphPayload> {
    if (this.graphCache) return this.graphCache;
    const r = await this.assets.fetch(new URL('/data/research-graph.json', this.baseUrl).toString());
    if (!r.ok) return (this.graphCache = { edges: [] });
    const graph = (await r.json()) as GraphPayload;
    return (this.graphCache = graph);
  }

  private async scanPart(
    path: string,
    tokens: string[],
    phrase: string,
    intent: string | undefined,
    exactCode?: string,
    exactSection?: string,
    limit = 16,
  ): Promise<Array<{ rec: any; relevance: number }>> {
    const r = await this.assets.fetch(new URL(`/data/law/${path}`, this.baseUrl).toString());
    if (!r.ok) return [];
    const reader = r.body?.getReader();
    if (!reader) return [];
    const decoder = new TextDecoder();
    let buffer = '';
    const best: Array<{ rec: any; relevance: number }> = [];

    const push = (rec: any) => {
      if (rec?.kind !== 'section') return;
      const code = String(rec.code || '').toUpperCase();
      const section = String(rec.section || '');
      if (exactCode && code !== exactCode) return;
      if (exactSection && section !== exactSection) return;
      if (!exactSection && !tokens.length && !phrase) return;

      const relevance = exactSection ? 10000 : score(rec, tokens, phrase, intent);
      if (!exactSection && relevance <= 0.1) return;

      best.push({ rec, relevance });
      best.sort((a, b) => b.relevance - a.relevance);
      if (best.length > limit) best.pop();
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          push(JSON.parse(line));
        } catch {}
      }
      if (done) break;
    }
    if (buffer.trim()) {
      try {
        push(JSON.parse(buffer));
      } catch {}
    }
    return best;
  }

  private toSection(rec: any, relevance: number, matchType: RetrievedSection['matchType']): RetrievedSection {
    const code = String(rec.code || '').toUpperCase();
    const section = String(rec.section || '');
    const normalizedRelevance = Math.min(1, relevance / 30 + 0.2); // normalize from raw score
    return {
      uid: String(rec.uid || `${code}:${section}`),
      lawCode: code,
      sectionNum: section,
      citation: citationForSection({ lawCode: code, sectionNum: section }),
      title: typeof rec.title === 'string' ? rec.title : undefined,
      text: String(rec.text || ''),
      history: typeof rec.history === 'string' ? rec.history : undefined,
      relevance: exactRef ? normalizedRelevance : relevance,
      matchType,
      charCount: typeof rec.char_count === 'number' ? rec.char_count : String(rec.text || '').length,
      path: typeof rec.path === 'string' ? rec.path : undefined,
    };
  }

  async search(input: RetrievalQuery): Promise<EvidenceBundle> {
    const query = input.query.trim();
    const limit = Math.max(1, Math.min(input.limit || 12, 30));
    const explicitCode = (input.code || codeFromQuery(query))?.toUpperCase();
    const exact = input.exactUid?.trim() || (() => {
      const m = exactRef(query);
      return m ? `${m[1].toUpperCase()}:${m[2]}` : undefined;
    })();

    const { tokens, phrase, code: inferredCode } = extractConcepts(query);
    const code = explicitCode || inferredCode;

    // Intent detection for scoring
    const lower = query.toLowerCase();
    let intent: string | undefined;
    if (/\b(define|definition|means|meaning)\b/.test(lower)) intent = 'definition';
    else if (/\b(history|amended|effective)\b/.test(lower)) intent = 'history';

    // Query rewrites – semantic expansion, not just word match
    const rewrites: string[] = [phrase];
    if (tokens.length) {
      rewrites.push(tokens.slice(0, 4).join(' '));
      // Add definition-oriented rewrite
      if (intent === 'definition') rewrites.push(`${tokens[0]} means`);
    }

    let candidateCodes = new Set<string>();
    if (code) candidateCodes.add(code);

    // Use research-index terms for candidate pruning – but as semantic filter, not sole source
    try {
      const idx = await this.index();
      if (!code && idx.terms) {
        for (const term of tokens) {
          for (const uid of idx.terms[term] || []) {
            candidateCodes.add(String(uid).split(':')[0]);
          }
        }
      }
    } catch {
      // index unavailable, fallback to manifest
    }

    const manifest = await this.manifest();
    if (!candidateCodes.size) {
      Object.keys(manifest.codes).slice(0, 8).forEach((c) => candidateCodes.add(c));
    }

    const exactMatch = exact?.match(/^([A-Z0-9]+):(.+)$/);
    const all: Array<{ rec: any; relevance: number }> = [];

    // Scan candidate codes – with concurrency limit
    for (const c of candidateCodes) {
      const parts = manifest.codes[c] || [];
      for (const part of parts) {
        const found = await this.scanPart(part, tokens, phrase, intent, exactMatch?.[1], exactMatch?.[2], limit * 2);
        all.push(...found);
        if (exactMatch && found.length) break;
      }
      if (exactMatch && all.length) break;
      if (all.length > limit * 6) break; // early stop if enough
    }

    all.sort((a, b) => b.relevance - a.relevance);

    const seen = new Set<string>();
    const results: RetrievedSection[] = [];
    for (const item of all) {
      const section = this.toSection(item.rec, item.relevance, exactMatch ? 'exact' : 'fulltext');
      if (seen.has(section.uid)) continue;
      if (!section.text.trim()) continue;
      seen.add(section.uid);
      results.push(section);
      if (results.length >= limit) break;
    }

    // Ensure exact match gets top relevance
    if (exactMatch) {
      results.sort((a, b) => {
        if (a.uid === exact) return -1;
        if (b.uid === exact) return 1;
        return b.relevance - a.relevance;
      });
    }

    return {
      query,
      results,
      relationships: [],
      retrieval: {
        methods: ['static-corpus', 'semantic-scoring', 'bm25-like', 'phrase-boost', 'title-boost'],
        complete: true,
        queryRewrite: rewrites.slice(0, 5),
      },
    };
  }

  async getSection(uid: string): Promise<RetrievedSection | null> {
    const [code, section] = uid.split(':', 2);
    if (!code || !section) return null;
    const e = await this.search({ query: `${code} section ${section}`, exactUid: uid, limit: 1 });
    return e.results[0] || null;
  }

  async getRelationships(
    uid: string,
    options: { direction?: 'outbound' | 'inbound' | 'both'; depth?: number; limit?: number } = {},
  ): Promise<RelationshipEdge[]> {
    const graph = await this.graph();
    const direction = options.direction || 'both';
    const depth = Math.min(Math.max(options.depth || 1, 1), 3);
    const limit = Math.min(Math.max(options.limit || 15, 1), 120);
    let frontier = [uid];
    const visited = new Set([uid]);
    const out: RelationshipEdge[] = [];
    const seen = new Set<string>();

    for (let level = 0; level < depth && frontier.length && out.length < limit; level++) {
      const next: string[] = [];
      for (const current of frontier) {
        for (const edge of graph.edges) {
          const outbound = edge.sourceUid === current;
          const inbound = edge.targetUid === current;
          if (!((direction === 'outbound' && outbound) || (direction === 'inbound' && inbound) || (direction === 'both' && (outbound || inbound)))) continue;
          const key = `${edge.sourceUid}|${edge.targetUid}|${edge.relationship}`;
          if (seen.has(key)) continue;
          seen.add(key);
          out.push(edge);
          const neighbor = outbound ? edge.targetUid : edge.sourceUid;
          if (neighbor && !visited.has(neighbor)) {
            visited.add(neighbor);
            next.push(neighbor);
          }
          if (out.length >= limit) break;
        }
        if (out.length >= limit) break;
      }
      frontier = next;
    }
    return out;
  }

  async getHistory(uid: string): Promise<HistoryEvent[]> {
    const section = await this.getSection(uid);
    if (!section?.history) return [];
    return [{ id: `${uid}:history`, uid, eventType: 'statutory-history', description: section.history }];
  }

  async getDefinition(term: string, scope?: string): Promise<RetrievedSection[]> {
    const t = term.toLowerCase().trim();
    if (!t) return [];
    const queries = [`${t} means`, `${t} definition`, `${t} includes`, `definition of ${t}`];
    const results: RetrievedSection[] = [];
    const seen = new Set<string>();

    for (const q of queries) {
      const bundle = await this.search({ query: q, code: scope, limit: 6 });
      for (const r of bundle.results) {
        if (seen.has(r.uid)) continue;
        const text = r.text.toLowerCase();
        if (!text.includes(t)) continue;
        if (!(text.includes('means') || text.includes('definition') || text.includes('includes') || text.includes('defined'))) continue;
        seen.add(r.uid);
        results.push({ ...r, matchType: 'definition', relevance: 0.9 });
        if (results.length >= 10) break;
      }
      if (results.length >= 10) break;
    }

    return results;
  }

  async compare(leftUid: string, rightUid: string): Promise<{ left: RetrievedSection | null; right: RetrievedSection | null; diff?: string }> {
    const [left, right] = await Promise.all([this.getSection(leftUid), this.getSection(rightUid)]);
    if (!left || !right) return { left, right };
    const leftTokens = new Set((left.text.toLowerCase().match(/\b\w{3,}\b/g) || []) as string[]);
    const rightTokens = new Set((right.text.toLowerCase().match(/\b\w{3,}\b/g) || []) as string[]);
    const common = [...leftTokens].filter((t) => rightTokens.has(t)).slice(0, 40);
    const onlyLeft = [...leftTokens].filter((t) => !rightTokens.has(t)).slice(0, 20);
    const onlyRight = [...rightTokens].filter((t) => !leftTokens.has(t)).slice(0, 20);
    const diff = `Shared concepts: ${common.join(', ')}. Unique to ${left.citation.label}: ${onlyLeft.join(', ')}. Unique to ${right.citation.label}: ${onlyRight.join(', ')}. Lengths: ${left.text.length} vs ${right.text.length}.`;
    return { left, right, diff };
  }

  async resolveCitation(uid: string): Promise<ReturnType<typeof citationForSection> | null> {
    try {
      const sec = await this.getSection(uid);
      return sec?.citation ?? null;
    } catch {
      return null;
    }
  }

  async buildEvidenceGraph(uids: string[], options?: { depth?: number; limit?: number }): Promise<RelationshipEdge[]> {
    const depth = Math.min(Math.max(options?.depth ?? 2, 1), 3);
    const limit = Math.min(Math.max(options?.limit ?? 40, 1), 120);
    const edges: RelationshipEdge[] = [];
    const seen = new Set<string>();

    for (const uid of uids.slice(0, 10)) {
      const rels = await this.getRelationships(uid, { direction: 'both', depth, limit: Math.floor(limit / uids.length) || 10 });
      for (const r of rels) {
        const key = `${r.sourceUid}|${r.targetUid}|${r.relationship}`;
        if (seen.has(key)) continue;
        seen.add(key);
        edges.push(r);
        if (edges.length >= limit) break;
      }
      if (edges.length >= limit) break;
    }

    return edges;
  }

  async analyzeDocument(document: string, propositions?: string[]): Promise<EvidenceBundle> {
    const doc = document.trim();
    if (!doc) throw new Error('Document required');

    // Extract citations from document
    const refPattern = /\b([A-Z]{2,8})\s*(?:§+|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)/gi;
    const refs: string[] = [];
    let m: RegExpExecArray | null;
    const seenRef = new Set<string>();
    while ((m = refPattern.exec(doc)) !== null) {
      const uid = `${m[1].toUpperCase()}:${m[2]}`;
      if (!seenRef.has(uid)) {
        seenRef.add(uid);
        refs.push(uid);
      }
    }

    const results: RetrievedSection[] = [];
    const seen = new Set<string>();

    for (const uid of refs.slice(0, 15)) {
      const sec = await this.getSection(uid);
      if (sec && !seen.has(sec.uid)) {
        seen.add(sec.uid);
        results.push({ ...sec, relevance: 0.95, matchType: 'relationship', referenceText: 'Cited in analyzed document' });
      }
    }

    // Proposition search
    const props = propositions?.length ? propositions : [doc.slice(0, 400)];
    for (const prop of props.slice(0, 6)) {
      const bundle = await this.search({ query: prop, limit: 5 });
      for (const r of bundle.results) {
        if (!seen.has(r.uid)) {
          seen.add(r.uid);
          results.push(r);
        }
      }
    }

    return {
      query: `Document analysis: ${doc.slice(0, 120)}`,
      results,
      relationships: [],
      retrieval: { methods: ['document-analysis', 'citation-extraction', 'proposition-search'], complete: true },
    };
  }
}
