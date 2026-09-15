import type { EvidenceBundle, HistoryEvent, RelationshipEdge, ResearchRetriever, RetrievalQuery, RetrievedSection } from './retrieval';

export interface AISearchInstance {
  search(input: Record<string, unknown>): Promise<{ search_query?: string; chunks?: Array<{ id?: string; score?: number; text?: string; item?: { key?: string; metadata?: Record<string, unknown> }; scoring_details?: Record<string, unknown> }> }>;
  chatCompletions(input: Record<string, unknown>): Promise<Response | ReadableStream>;
}

function sectionFromChunk(chunk: NonNullable<Awaited<ReturnType<AISearchInstance['search']>>['chunks']>[number]): RetrievedSection | null {
  const metadata = chunk.item?.metadata ?? {};
  const key = String(chunk.item?.key ?? metadata.uid ?? metadata.citation ?? '');
  const match = key.match(/(?:codes\/)?([A-Z]{2,8})[/:_-]([^/]+?)(?:\.md)?$/i);
  const code = String(metadata.code ?? match?.[1] ?? '').toUpperCase();
  const section = String(metadata.section ?? match?.[2] ?? '');
  if (!code || !section || !chunk.text) return null;
  const uid = String(metadata.uid ?? `${code}:${section}`);
  return {
    uid,
    lawCode: code,
    sectionNum: section,
    citation: String(metadata.citation ?? `${code} § ${section}`),
    title: typeof metadata.title === 'string' ? metadata.title : undefined,
    text: chunk.text,
    history: typeof metadata.history === 'string' ? metadata.history : undefined,
    relevance: Number(chunk.scoring_details?.reranking_score ?? chunk.score ?? 0),
    matchType: 'fulltext',
    corpusVersionId: typeof metadata.corpus_version_id === 'string' ? metadata.corpus_version_id : undefined,
    validFrom: typeof metadata.valid_from === 'string' ? metadata.valid_from : undefined,
    validTo: typeof metadata.valid_to === 'string' ? metadata.valid_to : undefined,
  };
}

export class HybridResearchRetriever implements ResearchRetriever {
  constructor(private readonly primary: ResearchRetriever, private readonly aiSearch: AISearchInstance) {}

  async search(input: RetrievalQuery): Promise<EvidenceBundle> {
    const [primary, remote] = await Promise.allSettled([
      this.primary.search(input),
      this.aiSearch.search({
        query: input.query,
        ai_search_options: {
          retrieval: { retrieval_type: 'hybrid', fusion_method: 'rrf', max_num_results: Math.min(input.limit ?? 10, 20), match_threshold: 0.25 },
          query_rewrite: { enabled: true },
          reranking: { enabled: true, model: '@cf/baai/bge-reranker-base', match_threshold: 0.2 },
          cache: { enabled: true, cache_threshold: 'close_enough' },
        },
      }),
    ]);

    const results: RetrievedSection[] = [];
    const seen = new Set<string>();
    const methods: string[] = [];
    if (primary.status === 'fulfilled') {
      methods.push(...primary.value.retrieval.methods);
      for (const result of primary.value.results) { if (!seen.has(result.uid)) { seen.add(result.uid); results.push(result); } }
    }
    if (remote.status === 'fulfilled') {
      methods.push('ai-search-hybrid', 'ai-search-reranking');
      for (const chunk of remote.value.chunks ?? []) {
        const result = sectionFromChunk(chunk);
        if (result && !seen.has(result.uid)) { seen.add(result.uid); results.push(result); }
      }
    }
    results.sort((a, b) => b.relevance - a.relevance);
    const limit = Math.min(input.limit ?? 10, 25);
    return {
      query: input.query,
      results: results.slice(0, limit),
      relationships: primary.status === 'fulfilled' ? primary.value.relationships : [],
      retrieval: {
        methods: [...new Set(methods)],
        complete: primary.status === 'fulfilled' && remote.status === 'fulfilled',
      },
    };
  }

  getSection(uid: string, versionId?: string): Promise<RetrievedSection | null> { return this.primary.getSection(uid, versionId); }
  getRelationships(uid: string, options?: { direction?: 'outbound' | 'inbound' | 'both'; depth?: number; limit?: number }): Promise<RelationshipEdge[]> { return this.primary.getRelationships(uid, options); }
  getHistory(uid: string, options?: { versionId?: string; from?: string; to?: string; limit?: number }): Promise<HistoryEvent[]> { return this.primary.getHistory(uid, options); }
}
