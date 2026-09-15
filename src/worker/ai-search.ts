import { citationForSection, citationFromUid } from '../leginfo/citations';
import type { EvidenceBundle, HistoryEvent, RelationshipEdge, ResearchRetriever, RetrievalQuery, RetrievedSection } from './retrieval';

export interface AISearchInstance {
  search(input: Record<string, unknown>): Promise<{
    search_query?: string;
    chunks?: Array<{
      id?: string;
      score?: number;
      text?: string;
      item?: { key?: string; metadata?: Record<string, unknown> };
      scoring_details?: Record<string, unknown>;
    }>;
  }>;
  chatCompletions(input: Record<string, unknown>): Promise<Response | ReadableStream>;
}

function cleanCode(v: unknown): string {
  return String(v ?? '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
}
function cleanSection(v: unknown): string {
  return String(v ?? '').trim().replace(/[^A-Za-z0-9.\-]/g, '');
}

function sectionFromChunk(
  chunk: NonNullable<Awaited<ReturnType<AISearchInstance['search']>>['chunks']>[number]>,
): RetrievedSection | null {
  const metadata = (chunk.item?.metadata ?? {}) as Record<string, unknown>;
  const key = String(chunk.item?.key ?? metadata.uid ?? metadata.citation ?? '');

  // Try multiple key patterns: codes/FAM/432.5.md, FAM:432.5, FAM-432.5, etc.
  let code = cleanCode(metadata.code);
  let section = cleanSection(metadata.section);

  if (!code || !section) {
    const match = key.match(/(?:codes\/)?([A-Z]{2,8})[/:_-]([^/]+?)(?:\.md)?$/i);
    if (match) {
      if (!code) code = cleanCode(match[1]);
      if (!section) section = cleanSection(match[2]);
    }
  }

  if (!code || !section) {
    // Try to parse UID directly
    const uidMatch = key.match(/^([A-Z]{2,8})[:\-/]([A-Z0-9.\-]+)$/i);
    if (uidMatch) {
      if (!code) code = cleanCode(uidMatch[1]);
      if (!section) section = cleanSection(uidMatch[2]);
    }
  }

  if (!code || !section || !chunk.text) return null;

  const uid = String(metadata.uid ?? `${code}:${section}`);
  const rawCitation = metadata.citation;
  let citation: RetrievedSection['citation'];

  // Prefer structured citation, fallback to helper
  try {
    if (typeof rawCitation === 'object' && rawCitation !== null) {
      const rc = rawCitation as any;
      if (rc.label && rc.url) citation = rc as any;
      else if (rc.lawCode && rc.sectionNum) citation = citationForSection({ lawCode: rc.lawCode, sectionNum: rc.sectionNum });
      else citation = citationForSection({ lawCode: code, sectionNum: section });
    } else if (typeof rawCitation === 'string' && rawCitation.includes('§')) {
      const parsed = citationFromUid(uid);
      citation = parsed ?? citationForSection({ lawCode: code, sectionNum: section });
    } else {
      citation = citationForSection({ lawCode: code, sectionNum: section });
    }
  } catch {
    citation = {
      label: `${code} § ${section}`,
      lawCode: code,
      sectionNum: section,
      url: `https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=${encodeURIComponent(section)}.&lawCode=${code}`,
    } as any;
  }

  const relevance = (() => {
    const details = chunk.scoring_details as any;
    const rerank = details?.reranking_score;
    const score = chunk.score;
    const raw = Number(rerank ?? score ?? 0);
    if (!Number.isFinite(raw)) return 0.5;
    // Normalize: reranker 0-1, vector score may be higher
    return Math.min(1, Math.max(0, raw > 1 ? raw / 10 : raw));
  })();

  return {
    uid,
    lawCode: code,
    sectionNum: section,
    citation,
    title: typeof metadata.title === 'string' ? metadata.title : undefined,
    text: String(chunk.text),
    history: typeof metadata.history === 'string' ? metadata.history : undefined,
    relevance: relevance || 0.6,
    matchType: 'fulltext',
    corpusVersionId: typeof metadata.corpus_version_id === 'string' ? metadata.corpus_version_id : undefined,
    validFrom: typeof metadata.valid_from === 'string' ? metadata.valid_from : undefined,
    validTo: typeof metadata.valid_to === 'string' ? metadata.valid_to : undefined,
  };
}

// RRF fusion – stronger than simple concatenation
function reciprocalRankFusion(
  lists: Array<Array<{ uid: string; score: number; item: RetrievedSection }>>,
  k = 60,
): Map<string, { item: RetrievedSection; fusedScore: number }> {
  const fused = new Map<string, { item: RetrievedSection; fusedScore: number }>();
  for (const list of lists) {
    list.forEach((entry, rank) => {
      const rrf = 1 / (k + rank + 1);
      const weighted = rrf * (0.5 + entry.score); // incorporate original score
      const existing = fused.get(entry.uid);
      if (existing) {
        existing.fusedScore += weighted;
        // Keep higher relevance
        if (entry.item.relevance > existing.item.relevance) existing.item = entry.item;
      } else {
        fused.set(entry.uid, { item: entry.item, fusedScore: weighted });
      }
    });
  }
  return fused;
}

export class HybridResearchRetriever implements ResearchRetriever {
  constructor(
    private readonly primary: ResearchRetriever,
    private readonly aiSearch: AISearchInstance,
    private readonly options = { rrfK: 60, enableQueryRewrite: true },
  ) {}

  async search(input: RetrievalQuery): Promise<EvidenceBundle> {
    const query = input.query.trim();
    if (!query) throw new Error('A search query is required.');

    const limit = Math.min(input.limit ?? 12, 30);

    // Parallel execution: primary deterministic + AI semantic
    const [primary, remote] = await Promise.allSettled([
      this.primary.search(input),
      this.aiSearch.search({
        query,
        // Use messages format for better query understanding if supported
        messages: [{ role: 'user', content: query }],
        ai_search_options: {
          retrieval: {
            retrieval_type: 'hybrid',
            fusion_method: 'rrf',
            max_num_results: Math.min(limit * 2, 30),
            match_threshold: 0.22,
            context_expansion: 2,
          },
          query_rewrite: { enabled: this.options.enableQueryRewrite },
          reranking: {
            enabled: true,
            model: '@cf/baai/bge-reranker-base',
            match_threshold: 0.18,
          },
          cache: { enabled: true, cache_threshold: 'close_enough' },
        },
      }),
    ]);

    const results: RetrievedSection[] = [];
    const seen = new Set<string>();
    const methods: string[] = [];
    const rewrites: string[] = [];

    let primaryResults: Array<{ uid: string; score: number; item: RetrievedSection }> = [];
    let aiResults: Array<{ uid: string; score: number; item: RetrievedSection }> = [];
    let relationships: RelationshipEdge[] = [];

    if (primary.status === 'fulfilled') {
      methods.push(...primary.value.retrieval.methods);
      if (primary.value.retrieval.queryRewrite) rewrites.push(...primary.value.retrieval.queryRewrite);
      relationships = primary.value.relationships;
      primaryResults = primary.value.results.map((r, idx) => ({
        uid: r.uid,
        score: r.relevance,
        item: r,
      }));
    } else {
      methods.push(`primary-error:${primary.reason instanceof Error ? primary.reason.message : String(primary.reason)}`);
    }

    if (remote.status === 'fulfilled') {
      methods.push('ai-search-hybrid', 'ai-search-reranking', 'ai-search-query-rewrite');
      const searchQuery = (remote.value as any).search_query;
      if (typeof searchQuery === 'string' && searchQuery !== query) rewrites.push(searchQuery);

      for (const chunk of remote.value.chunks ?? []) {
        const result = sectionFromChunk(chunk);
        if (!result) continue;
        if (seen.has(result.uid)) continue; // temporary dedup before fusion
        aiResults.push({ uid: result.uid, score: result.relevance, item: result });
      }
    } else {
      methods.push(`ai-search-error:${remote.reason instanceof Error ? remote.reason.message : String(remote.reason)}`);
    }

    // If we have both, do RRF fusion for stronger AI ranking
    if (primaryResults.length && aiResults.length) {
      const fused = reciprocalRankFusion([primaryResults, aiResults], this.options.rrfK);
      const sorted = [...fused.values()].sort((a, b) => b.fusedScore - a.fusedScore);
      for (const { item, fusedScore } of sorted) {
        if (seen.has(item.uid)) continue;
        seen.add(item.uid);
        results.push({ ...item, relevance: Math.min(1, (item.relevance + fusedScore) / 2 + 0.1) });
        if (results.length >= limit) break;
      }
      methods.push('rrf-fusion');
    } else {
      // Fallback: concatenate with dedup, primary first for determinism
      const combined = [...primaryResults, ...aiResults].sort((a, b) => b.score - a.score);
      for (const entry of combined) {
        if (seen.has(entry.uid)) continue;
        seen.add(entry.uid);
        results.push(entry.item);
        if (results.length >= limit) break;
      }
    }

    // Final sort by relevance
    results.sort((a, b) => b.relevance - a.relevance);

    return {
      query,
      results: results.slice(0, limit),
      relationships,
      retrieval: {
        methods: [...new Set(methods)],
        complete: primary.status === 'fulfilled' && remote.status === 'fulfilled',
        queryRewrite: [...new Set(rewrites)].slice(0, 8),
      },
    };
  }

  // Delegated tools – primary is source of truth for deterministic operations
  getSection(uid: string, versionId?: string): Promise<RetrievedSection | null> {
    return this.primary.getSection(uid, versionId);
  }

  getRelationships(
    uid: string,
    options?: { direction?: 'outbound' | 'inbound' | 'both'; depth?: number; limit?: number },
  ): Promise<RelationshipEdge[]> {
    return this.primary.getRelationships(uid, options);
  }

  getHistory(
    uid: string,
    options?: { versionId?: string; from?: string; to?: string; limit?: number },
  ): Promise<HistoryEvent[]> {
    return this.primary.getHistory(uid, options);
  }

  async getDefinition(term: string, scope?: string): Promise<RetrievedSection[]> {
    if (typeof (this.primary as any).getDefinition === 'function') {
      return (this.primary as any).getDefinition(term, scope);
    }
    // Fallback via search
    const bundle = await this.search({ query: `${term} means definition`, limit: 8 });
    return bundle.results.filter((r) => r.text.toLowerCase().includes(term.toLowerCase()));
  }

  async compare(leftUid: string, rightUid: string): Promise<{ left: RetrievedSection | null; right: RetrievedSection | null; diff?: string }> {
    if (typeof (this.primary as any).compare === 'function') {
      return (this.primary as any).compare(leftUid, rightUid);
    }
    const [left, right] = await Promise.all([this.getSection(leftUid), this.getSection(rightUid)]);
    return { left, right };
  }

  async resolveCitation(uid: string): Promise<ReturnType<typeof citationForSection> | null> {
    if (typeof (this.primary as any).resolveCitation === 'function') {
      return (this.primary as any).resolveCitation(uid);
    }
    const sec = await this.getSection(uid);
    return sec?.citation ?? null;
  }

  async buildEvidenceGraph(uids: string[], options?: { depth?: number; limit?: number }): Promise<RelationshipEdge[]> {
    if (typeof (this.primary as any).buildEvidenceGraph === 'function') {
      return (this.primary as any).buildEvidenceGraph(uids, options);
    }
    const edges: RelationshipEdge[] = [];
    for (const uid of uids.slice(0, 8)) {
      const rels = await this.getRelationships(uid, { depth: options?.depth ?? 2, limit: Math.floor((options?.limit ?? 30) / uids.length) || 10 });
      edges.push(...rels);
    }
    return edges;
  }

  async analyzeDocument(document: string, propositions?: string[]): Promise<EvidenceBundle> {
    if (typeof (this.primary as any).analyzeDocument === 'function') {
      return (this.primary as any).analyzeDocument(document, propositions);
    }
    return this.search({ query: document.slice(0, 500), limit: 10 });
  }
}

// Helper to create retriever chain with fallback logic
export function createHybridRetriever(primary: ResearchRetriever, aiSearch?: AISearchInstance): ResearchRetriever {
  if (!aiSearch) return primary;
  return new HybridResearchRetriever(primary, aiSearch);
}
