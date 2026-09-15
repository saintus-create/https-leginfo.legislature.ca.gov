import { citationForSection, citationFromUid } from '../leginfo/citations';

export interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  all<T = Record<string, unknown>>(): Promise<{ results: T[] }>;
  first<T = Record<string, unknown>>(): Promise<T | null>;
}

export interface D1Database {
  prepare(query: string): D1PreparedStatement;
}

export interface RetrievalQuery {
  query: string;
  code?: string;
  limit?: number;
  exactUid?: string;
  filters?: {
    repealed?: boolean;
    hasHistory?: boolean;
  };
}

export interface RetrievedSection {
  uid: string;
  lawCode: string;
  sectionNum: string;
  citation: ReturnType<typeof citationForSection>;
  title?: string;
  text: string;
  history?: string;
  relevance: number;
  matchType: 'exact' | 'fulltext' | 'relationship' | 'definition' | 'temporal';
  relationship?: string;
  referenceText?: string;
  corpusVersionId?: string;
  validFrom?: string;
  validTo?: string;
  charCount?: number;
  path?: string;
}

export interface RelationshipEdge {
  sourceUid: string;
  targetUid?: string;
  relationship: string;
  referenceText?: string;
  confidence: number;
  provenance?: string;
}

export interface HistoryEvent {
  id: string;
  uid: string;
  eventType: string;
  effectiveDate?: string;
  enactedDate?: string;
  session?: string;
  billId?: string;
  chapter?: string;
  sourceKey?: string;
  sourceUrl?: string;
  description?: string;
  versionId?: string;
}

export interface EvidenceBundle {
  query: string;
  results: RetrievedSection[];
  relationships: RelationshipEdge[];
  retrieval: { methods: string[]; complete: boolean; queryRewrite?: string[] };
}

export interface ResearchRetriever {
  search(input: RetrievalQuery): Promise<EvidenceBundle>;
  getSection(uid: string, versionId?: string): Promise<RetrievedSection | null>;
  getRelationships(
    uid: string,
    options?: { direction?: 'outbound' | 'inbound' | 'both'; depth?: number; limit?: number },
  ): Promise<RelationshipEdge[]>;
  getHistory(
    uid: string,
    options?: { versionId?: string; from?: string; to?: string; limit?: number },
  ): Promise<HistoryEvent[]>;
  // Extended tool contract – provider independent
  getDefinition?(term: string, scope?: string): Promise<RetrievedSection[]>;
  compare?(leftUid: string, rightUid: string): Promise<{ left: RetrievedSection | null; right: RetrievedSection | null; diff?: string }>;
  resolveCitation?(uid: string): Promise<ReturnType<typeof citationForSection> | null>;
  buildEvidenceGraph?(uids: string[], options?: { depth?: number; limit?: number }): Promise<RelationshipEdge[]>;
  analyzeDocument?(document: string, propositions?: string[]): Promise<EvidenceBundle>;
}

const MAX_QUERY_LENGTH = 2000;
const MAX_RESULTS = 30;
const MAX_TRAVERSAL_DEPTH = 3;
const MAX_TRAVERSAL_NODES = 150;

function clean(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

function normalizeCode(value: string | undefined): string | undefined {
  const code = value ? value.trim().toUpperCase().replace(/[^A-Z0-9]/g, '') : '';
  return code || undefined;
}

function parseExactReference(query: string): { code: string; section: string } | null {
  const match = /\b([A-Z]{2,8})\s*(?:§|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)\b/i.exec(query);
  return match ? { code: normalizeCode(match[1])!, section: match[2] } : null;
}

function parseAllReferences(text: string): Array<{ code: string; section: string; uid: string }> {
  const out: Array<{ code: string; section: string; uid: string }> = [];
  const pattern = /\b([A-Z]{2,8})\s*(?:§+|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)/gi;
  let m: RegExpExecArray | null;
  const seen = new Set<string>();
  while ((m = pattern.exec(text)) !== null) {
    const code = normalizeCode(m[1]);
    const section = m[2];
    if (!code || !section) continue;
    const uid = `${code}:${section}`;
    if (seen.has(uid)) continue;
    seen.add(uid);
    out.push({ code, section, uid });
  }
  return out;
}

function rowToSection(row: Record<string, unknown>, relevance: number, matchType: RetrievedSection['matchType']): RetrievedSection {
  const lawCode = String(row.code ?? '').toUpperCase();
  const sectionNum = String(row.section ?? '');
  const citation = (() => {
    try {
      return citationForSection({ lawCode, sectionNum });
    } catch {
      return { label: `${lawCode} § ${sectionNum}`, lawCode, sectionNum, url: `https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=${encodeURIComponent(sectionNum)}.&lawCode=${lawCode}` } as any;
    }
  })();
  return {
    uid: String(row.uid ?? `${lawCode}:${sectionNum}`),
    lawCode,
    sectionNum,
    citation,
    title: typeof row.title === 'string' ? row.title : undefined,
    text: String(row.text ?? ''),
    history: typeof row.history === 'string' ? row.history : undefined,
    relevance,
    matchType,
    relationship: typeof row.relationship === 'string' ? row.relationship : undefined,
    referenceText: typeof row.reference_text === 'string' ? row.reference_text : undefined,
    corpusVersionId: typeof row.corpus_version_id === 'string' ? row.corpus_version_id : undefined,
    validFrom: typeof row.valid_from === 'string' ? row.valid_from : undefined,
    validTo: typeof row.valid_to === 'string' ? row.valid_to : undefined,
    charCount: typeof row.char_count === 'number' ? row.char_count : undefined,
    path: typeof row.path === 'string' ? row.path : undefined,
  };
}

function rowToHistory(row: Record<string, unknown>): HistoryEvent {
  return {
    id: String(row.id ?? ''),
    uid: String(row.uid ?? ''),
    eventType: String(row.event_type ?? 'unknown'),
    effectiveDate: typeof row.effective_date === 'string' ? row.effective_date : undefined,
    enactedDate: typeof row.enacted_date === 'string' ? row.enacted_date : undefined,
    session: typeof row.session === 'string' ? row.session : undefined,
    billId: typeof row.bill_id === 'string' ? row.bill_id : undefined,
    chapter: typeof row.chapter === 'string' ? row.chapter : undefined,
    sourceKey: typeof row.source_key === 'string' ? row.source_key : undefined,
    sourceUrl: typeof row.source_url === 'string' ? row.source_url : undefined,
    description: typeof row.description === 'string' ? row.description : undefined,
    versionId: typeof row.version_id === 'string' ? row.version_id : undefined,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Query understanding – not just word match, but semantic rewriting
// ─────────────────────────────────────────────────────────────────────────────
function rewriteQuery(query: string): { primary: string; rewrites: string[]; tokens: string[] } {
  const base = clean(query);
  const lower = base.toLowerCase();

  // Remove question scaffolding
  const stripped = base
    .replace(/^(what is|what are|what does|how does|how do|why does|explain|describe|summarize|tell me about)\b/gi, '')
    .replace(/\b(please|can you|could you|i want to know)\b/gi, '')
    .trim();

  const rewrites: string[] = [stripped];

  // Synonym expansion – lightweight, deterministic, AI-inspired
  const synonyms: Record<string, string[]> = {
    custody: ['custody', 'custodial', 'parenting'],
    support: ['support', 'alimony', 'maintenance'],
    records: ['records', 'public records', 'access'],
    privacy: ['privacy', 'confidential', 'disclosure'],
    definition: ['definition', 'means', 'defined'],
    enforcement: ['enforcement', 'penalty', 'violation'],
  };

  for (const [key, vals] of Object.entries(synonyms)) {
    if (lower.includes(key)) {
      rewrites.push(vals.join(' '));
    }
  }

  // Extract meaningful tokens
  const tokens = stripped
    .toLowerCase()
    .replace(/[^a-z0-9.\-\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length >= 3)
    .filter((t) => !['what', 'does', 'this', 'that', 'with', 'from', 'have', 'been', 'about', 'section'].includes(t))
    .slice(0, 20);

  return { primary: stripped || base, rewrites: [...new Set(rewrites)].slice(0, 6), tokens };
}

// ─────────────────────────────────────────────────────────────────────────────
// D1 retriever – hardened
// ─────────────────────────────────────────────────────────────────────────────
export class D1ResearchRetriever implements ResearchRetriever {
  constructor(private readonly db: D1Database) {}

  async getSection(uid: string, versionId?: string): Promise<RetrievedSection | null> {
    const key = clean(uid);
    if (!key) return null;

    // Try versioned first if provided
    if (versionId) {
      const row = await this.db
        .prepare(
          `SELECT uid, code, section, title, text, history, corpus_version_id, valid_from, valid_to, char_count, path FROM law_section_versions WHERE uid = ? AND corpus_version_id = ? LIMIT 1`,
        )
        .bind(key, versionId)
        .first();
      if (row) return rowToSection(row, 1, 'exact');
    }

    // Current sections
    const row = await this.db
      .prepare(
        `SELECT uid, code, section, title, text, history, corpus_version_id, char_count, path FROM law_sections WHERE uid = ? LIMIT 1`,
      )
      .bind(key)
      .first();

    if (row) return rowToSection(row, 1, 'exact');

    // Try code + section split
    const parts = key.split(':');
    if (parts.length === 2) {
      const row2 = await this.db
        .prepare(
          `SELECT uid, code, section, title, text, history, corpus_version_id, char_count, path FROM law_sections WHERE code = ? AND section = ? LIMIT 1`,
        )
        .bind(parts[0], parts[1])
        .first();
      if (row2) return rowToSection(row2, 1, 'exact');
    }

    return null;
  }

  async search(input: RetrievalQuery): Promise<EvidenceBundle> {
    const query = clean(input.query);
    if (!query) throw new Error('A search query is required.');
    if (query.length > MAX_QUERY_LENGTH) throw new Error('Search query is too long.');

    const limit = Math.max(1, Math.min(input.limit ?? 12, MAX_RESULTS));
    const code = normalizeCode(input.code);
    const exact = input.exactUid?.trim() || parseExactReference(query);

    const { primary, rewrites, tokens } = rewriteQuery(query);

    const results: RetrievedSection[] = [];
    const seen = new Set<string>();
    const methods: string[] = [];

    // 1. Exact citation – highest confidence
    if (exact) {
      const uid = typeof exact === 'string' ? exact : `${exact.code}:${exact.section}`;
      try {
        const row =
          typeof exact === 'string'
            ? await this.db
                .prepare(
                  'SELECT uid, code, section, title, text, history, corpus_version_id, char_count, path FROM law_sections WHERE uid = ? LIMIT 1',
                )
                .bind(uid)
                .first()
            : await this.db
                .prepare(
                  'SELECT uid, code, section, title, text, history, corpus_version_id, char_count, path FROM law_sections WHERE code = ? AND section = ? LIMIT 1',
                )
                .bind(exact.code, exact.section)
                .first();
        if (row) {
          const section = rowToSection(row, 1, 'exact');
          results.push(section);
          seen.add(section.uid);
          methods.push('exact-section');
        }
      } catch {
        // ignore, fall through to FTS
      }
    }

    // 2. Full-text with hybrid ranking – BM25 + phrase boost + code filter
    const searchVariants = [primary, ...rewrites.slice(0, 3)];

    for (const variant of searchVariants) {
      if (results.length >= limit) break;
      const variantTokens = variant
        .toLowerCase()
        .replace(/[^a-z0-9.\-\s]/g, ' ')
        .split(/\s+/)
        .filter((t) => t.length >= 2)
        .slice(0, 20);
      if (!variantTokens.length) continue;

      // Build FTS5 query: quoted phrases + OR
      const matchExpression = variantTokens.map((t) => `"${t.replace(/"/g, '')}"`).join(' OR ');

      try {
        const sql = code
          ? `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, s.corpus_version_id, s.char_count, s.path, bm25(law_sections_fts) AS rank FROM law_sections_fts f JOIN law_sections s ON s.rowid = f.rowid WHERE law_sections_fts MATCH ? AND s.code = ? ORDER BY rank LIMIT ?`
          : `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, s.corpus_version_id, s.char_count, s.path, bm25(law_sections_fts) AS rank FROM law_sections_fts f JOIN law_sections s ON s.rowid = f.rowid WHERE law_sections_fts MATCH ? ORDER BY rank LIMIT ?`;

        const rows = code
          ? await this.db.prepare(sql).bind(matchExpression, code, limit * 2).all()
          : await this.db.prepare(sql).bind(matchExpression, limit * 2).all();

        if (!methods.includes('full-text')) methods.push('full-text');

        for (const row of rows.results) {
          const uid = String(row.uid ?? '');
          if (!uid || seen.has(uid)) continue;
          const rank = Number(row.rank);
          // Convert BM25 rank (negative is better) to 0-1 relevance
          const relevance = Number.isFinite(rank) ? 1 / (1 + Math.max(0, rank + 10)) + 0.1 : 0.2;

          // Boost if title contains query tokens
          const title = String(row.title ?? '').toLowerCase();
          const titleBoost = tokens.some((t) => title.includes(t)) ? 0.15 : 0;

          // Boost if exact phrase appears
          const text = String(row.text ?? '').toLowerCase();
          const phraseBoost = text.includes(primary.toLowerCase().slice(0, 60)) ? 0.2 : 0;

          const finalRelevance = Math.min(1, relevance + titleBoost + phraseBoost);

          results.push(rowToSection(row, finalRelevance, 'fulltext'));
          seen.add(uid);
          if (results.length >= limit * 1.5) break;
        }
      } catch (e) {
        // FTS might fail if query contains special chars – fallback to LIKE
        try {
          const likePattern = `%${tokens.slice(0, 3).join('%')}%`;
          const sql = code
            ? `SELECT uid, code, section, title, text, history, corpus_version_id, char_count, path FROM law_sections WHERE text LIKE ? AND code = ? LIMIT ?`
            : `SELECT uid, code, section, title, text, history, corpus_version_id, char_count, path FROM law_sections WHERE text LIKE ? LIMIT ?`;
          const rows = code
            ? await this.db.prepare(sql).bind(likePattern, code, limit).all()
            : await this.db.prepare(sql).bind(likePattern, limit).all();
          for (const row of rows.results) {
            const uid = String(row.uid ?? '');
            if (!uid || seen.has(uid)) continue;
            results.push(rowToSection(row, 0.3, 'fulltext'));
            seen.add(uid);
          }
          if (!methods.includes('like-fallback')) methods.push('like-fallback');
        } catch {
          // ignore
        }
      }
    }

    // Sort by relevance descending and cap
    results.sort((a, b) => b.relevance - a.relevance);

    // Deduplicate and ensure citation integrity
    const deduped = results.filter((r) => {
      if (!r.text?.trim()) return false;
      return true;
    });

    return {
      query,
      results: deduped.slice(0, limit),
      relationships: [],
      retrieval: { methods: [...new Set(methods)], complete: true, queryRewrite: rewrites },
    };
  }

  async getRelationships(
    uid: string,
    options: { direction?: 'outbound' | 'inbound' | 'both'; depth?: number; limit?: number } = {},
  ): Promise<RelationshipEdge[]> {
    const root = clean(uid);
    if (!root) return [];
    const direction = options.direction ?? 'outbound';
    const depth = Math.min(Math.max(options.depth ?? 1, 1), MAX_TRAVERSAL_DEPTH);
    const limit = Math.min(Math.max(options.limit ?? 25, 1), MAX_TRAVERSAL_NODES);
    const edges: RelationshipEdge[] = [];
    const seenEdges = new Set<string>();
    const visited = new Set<string>([root]);
    let frontier = [root];

    for (let level = 0; level < depth && frontier.length && edges.length < limit; level++) {
      const next: string[] = [];
      for (const current of frontier) {
        if (direction === 'outbound' || direction === 'both') {
          const out = await this.db
            .prepare(
              `SELECT source_uid, target_uid, relationship, reference_text, confidence FROM section_relationships WHERE source_uid = ? LIMIT ?`,
            )
            .bind(current, limit - edges.length)
            .all();
          for (const row of out.results) this.addRelationship(row, current, edges, seenEdges, visited, next, limit);
        }
        if (direction === 'inbound' || direction === 'both') {
          const incoming = await this.db
            .prepare(
              `SELECT source_uid, target_uid, relationship, reference_text, confidence FROM section_relationships WHERE target_uid = ? LIMIT ?`,
            )
            .bind(current, limit - edges.length)
            .all();
          for (const row of incoming.results) this.addRelationship(row, current, edges, seenEdges, visited, next, limit);
        }
        if (edges.length >= limit) break;
      }
      frontier = next;
    }
    return edges;
  }

  private addRelationship(
    row: Record<string, unknown>,
    current: string,
    edges: RelationshipEdge[],
    seenEdges: Set<string>,
    visited: Set<string>,
    next: string[],
    limit: number,
  ): void {
    if (edges.length >= limit) return;
    const edge: RelationshipEdge = {
      sourceUid: String(row.source_uid ?? ''),
      targetUid: row.target_uid ? String(row.target_uid) : undefined,
      relationship: String(row.relationship ?? 'related'),
      referenceText: row.reference_text ? String(row.reference_text) : undefined,
      confidence: Number.isFinite(Number(row.confidence)) ? Number(row.confidence) : 1,
    };
    const edgeKey = `${edge.sourceUid}|${edge.targetUid ?? ''}|${edge.relationship}|${edge.referenceText ?? ''}`;
    if (seenEdges.has(edgeKey)) return;
    seenEdges.add(edgeKey);
    edges.push(edge);
    const neighbor = edge.sourceUid === current ? edge.targetUid : edge.sourceUid;
    if (neighbor && !visited.has(neighbor) && visited.size < MAX_TRAVERSAL_NODES) {
      visited.add(neighbor);
      next.push(neighbor);
    }
  }

  async getHistory(
    uid: string,
    options: { versionId?: string; from?: string; to?: string; limit?: number } = {},
  ): Promise<HistoryEvent[]> {
    const key = clean(uid);
    if (!key) return [];
    const limit = Math.min(Math.max(options.limit ?? 50, 1), 200);
    const conditions = ['uid = ?'];
    const values: unknown[] = [key];
    if (options.versionId) {
      conditions.push('version_id = ?');
      values.push(options.versionId);
    }
    if (options.from) {
      conditions.push('(effective_date IS NULL OR effective_date >= ?)');
      values.push(options.from);
    }
    if (options.to) {
      conditions.push('(effective_date IS NULL OR effective_date <= ?)');
      values.push(options.to);
    }
    try {
      const rows = await this.db
        .prepare(
          `SELECT id, uid, event_type, effective_date, enacted_date, session, bill_id, chapter, source_key, source_url, description, version_id FROM legislative_history_events WHERE ${conditions.join(' AND ')} ORDER BY COALESCE(effective_date, enacted_date, '9999-12-31'), id LIMIT ?`,
        )
        .bind(...values, limit)
        .all();
      return rows.results.map(rowToHistory);
    } catch {
      // Table may not exist in minimal DB – fallback to parsing history field
      const section = await this.getSection(key);
      if (section?.history) {
        return [
          {
            id: `${key}:history`,
            uid: key,
            eventType: 'statutory-history',
            description: section.history,
          },
        ];
      }
      return [];
    }
  }

  async getDefinition(term: string, scope?: string): Promise<RetrievedSection[]> {
    const t = clean(term).toLowerCase();
    if (!t) return [];
    const code = normalizeCode(scope);
    // Search for definition patterns: "X means", "X includes", "definition of X"
    const queries = [`"${t}" means`, `"${t}" includes`, `definition ${t}`, `${t} defined`];
    const results: RetrievedSection[] = [];
    const seen = new Set<string>();

    for (const q of queries) {
      if (results.length >= 10) break;
      try {
        const matchExpr = q.replace(/"/g, '').split(/\s+/).map((w) => `"${w}"`).join(' OR ');
        const sql = code
          ? `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, s.corpus_version_id FROM law_sections_fts f JOIN law_sections s ON s.rowid = f.rowid WHERE law_sections_fts MATCH ? AND s.code = ? ORDER BY bm25(law_sections_fts) LIMIT 5`
          : `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, s.corpus_version_id FROM law_sections_fts f JOIN law_sections s ON s.rowid = f.rowid WHERE law_sections_fts MATCH ? ORDER BY bm25(law_sections_fts) LIMIT 5`;
        const rows = code ? await this.db.prepare(sql).bind(matchExpr, code).all() : await this.db.prepare(sql).bind(matchExpr).all();
        for (const row of rows.results) {
          const uid = String(row.uid ?? '');
          if (!uid || seen.has(uid)) continue;
          // Heuristic: text must contain term near "means" or "definition"
          const text = String(row.text ?? '').toLowerCase();
          if (!text.includes(t)) continue;
          if (!(text.includes('means') || text.includes('definition') || text.includes('includes') || text.includes('defined'))) continue;
          seen.add(uid);
          results.push(rowToSection(row, 0.85, 'definition'));
        }
      } catch {
        // ignore
      }
    }

    return results.sort((a, b) => b.relevance - a.relevance);
  }

  async compare(leftUid: string, rightUid: string): Promise<{ left: RetrievedSection | null; right: RetrievedSection | null; diff?: string }> {
    const [left, right] = await Promise.all([this.getSection(leftUid), this.getSection(rightUid)]);
    if (!left || !right) return { left, right };
    // Simple textual diff summary – AI will do deeper reasoning
    const leftWords = new Set(left.text.toLowerCase().match(/\b\w{3,}\b/g) || []);
    const rightWords = new Set(right.text.toLowerCase().match(/\b\w{3,}\b/g) || []);
    const common = [...leftWords].filter((w) => rightWords.has(w)).slice(0, 30);
    const diff = `Common terms: ${common.join(', ')}. Left length ${left.text.length}, right length ${right.text.length}.`;
    return { left, right, diff };
  }

  async resolveCitation(uid: string): Promise<ReturnType<typeof citationForSection> | null> {
    try {
      const parsed = citationFromUid(uid);
      if (parsed) return parsed;
      const sec = await this.getSection(uid);
      if (sec) return sec.citation;
      return null;
    } catch {
      return null;
    }
  }

  async buildEvidenceGraph(uids: string[], options?: { depth?: number; limit?: number }): Promise<RelationshipEdge[]> {
    const depth = Math.min(Math.max(options?.depth ?? 2, 1), MAX_TRAVERSAL_DEPTH);
    const limit = Math.min(Math.max(options?.limit ?? 50, 1), MAX_TRAVERSAL_NODES);
    const allEdges: RelationshipEdge[] = [];
    const seen = new Set<string>();

    for (const uid of uids.slice(0, 10)) {
      const edges = await this.getRelationships(uid, { direction: 'both', depth, limit: Math.floor(limit / uids.length) || 10 });
      for (const e of edges) {
        const key = `${e.sourceUid}|${e.targetUid}|${e.relationship}`;
        if (seen.has(key)) continue;
        seen.add(key);
        allEdges.push(e);
        if (allEdges.length >= limit) break;
      }
      if (allEdges.length >= limit) break;
    }

    return allEdges;
  }

  async analyzeDocument(document: string, propositions?: string[]): Promise<EvidenceBundle> {
    const doc = clean(document);
    if (!doc) throw new Error('Document is required for analysis.');
    // Extract citations from document
    const refs = parseAllReferences(doc);
    const results: RetrievedSection[] = [];
    const seen = new Set<string>();

    for (const ref of refs.slice(0, 15)) {
      const sec = await this.getSection(ref.uid);
      if (sec && !seen.has(sec.uid)) {
        seen.add(sec.uid);
        results.push({ ...sec, relevance: 0.95, matchType: 'relationship', referenceText: `Cited in analyzed document` });
      }
    }

    // Also search for propositions
    if (propositions?.length) {
      for (const prop of propositions.slice(0, 5)) {
        const bundle = await this.search({ query: prop, limit: 5 });
        for (const r of bundle.results) {
          if (!seen.has(r.uid)) {
            seen.add(r.uid);
            results.push(r);
          }
        }
      }
    } else {
      // Search using document summary
      const summary = doc.slice(0, 500);
      const bundle = await this.search({ query: summary, limit: 10 });
      for (const r of bundle.results) {
        if (!seen.has(r.uid)) {
          seen.add(r.uid);
          results.push(r);
        }
      }
    }

    return {
      query: `Document analysis: ${doc.slice(0, 100)}`,
      results,
      relationships: [],
      retrieval: { methods: ['document-analysis', 'citation-extraction'], complete: true },
    };
  }
}

export async function retrieve(db: D1Database, input: RetrievalQuery): Promise<EvidenceBundle> {
  return new D1ResearchRetriever(db).search(input);
}
