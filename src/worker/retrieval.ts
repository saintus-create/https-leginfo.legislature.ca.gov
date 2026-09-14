import { citationForSection } from '../leginfo/citations';

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
  matchType: 'exact' | 'fulltext' | 'relationship';
  relationship?: string;
  referenceText?: string;
}

export interface RelationshipEdge {
  sourceUid: string;
  targetUid?: string;
  relationship: string;
  referenceText?: string;
  confidence: number;
}

export interface EvidenceBundle {
  query: string;
  results: RetrievedSection[];
  relationships: RelationshipEdge[];
  retrieval: { methods: string[]; complete: boolean };
}

export interface ResearchRetriever {
  search(input: RetrievalQuery): Promise<EvidenceBundle>;
  getSection(uid: string, versionId?: string): Promise<RetrievedSection | null>;
  getRelationships(uid: string, options?: { direction?: 'outbound' | 'inbound' | 'both'; depth?: number; limit?: number }): Promise<RelationshipEdge[]>;
}

const MAX_QUERY_LENGTH = 1000;
const MAX_RESULTS = 25;
const MAX_TRAVERSAL_DEPTH = 3;
const MAX_TRAVERSAL_NODES = 100;

function clean(value: string): string { return value.trim().replace(/\s+/g, ' '); }
function normalizeCode(value: string | undefined): string | undefined {
  const code = value ? value.trim().toUpperCase().replace(/[^A-Z0-9]/g, '') : '';
  return code || undefined;
}
function parseExactReference(query: string): { code: string; section: string } | null {
  const match = /\b([A-Z]{2,8})\s*(?:§|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)\b/i.exec(query);
  return match ? { code: normalizeCode(match[1])!, section: match[2] } : null;
}
function rowToSection(row: Record<string, unknown>, relevance: number, matchType: RetrievedSection['matchType']): RetrievedSection {
  const lawCode = String(row.code ?? '').toUpperCase();
  const sectionNum = String(row.section ?? '');
  return {
    uid: String(row.uid ?? `${lawCode}:${sectionNum}`), lawCode, sectionNum,
    citation: citationForSection({ lawCode, sectionNum }),
    title: typeof row.title === 'string' ? row.title : undefined,
    text: String(row.text ?? ''), history: typeof row.history === 'string' ? row.history : undefined,
    relevance, matchType,
    relationship: typeof row.relationship === 'string' ? row.relationship : undefined,
    referenceText: typeof row.reference_text === 'string' ? row.reference_text : undefined,
  };
}

export class D1ResearchRetriever implements ResearchRetriever {
  constructor(private readonly db: D1Database) {}

  async getSection(uid: string, versionId?: string): Promise<RetrievedSection | null> {
    const key = clean(uid);
    if (!key) return null;
    const row = versionId
      ? await this.db.prepare(`SELECT uid, code, section, title, text, history FROM law_section_versions WHERE uid = ? AND corpus_version_id = ? LIMIT 1`).bind(key, versionId).first()
      : await this.db.prepare(`SELECT uid, code, section, title, text, history FROM law_sections WHERE uid = ? LIMIT 1`).bind(key).first();
    return row ? rowToSection(row, 1, 'exact') : null;
  }

  async search(input: RetrievalQuery): Promise<EvidenceBundle> {
    const query = clean(input.query);
    if (!query) throw new Error('A search query is required.');
    if (query.length > MAX_QUERY_LENGTH) throw new Error('Search query is too long.');
    const limit = Math.max(1, Math.min(input.limit ?? 10, MAX_RESULTS));
    const code = normalizeCode(input.code);
    const exact = input.exactUid?.trim() || parseExactReference(query);
    const results: RetrievedSection[] = [];
    const seen = new Set<string>();
    const methods: string[] = [];

    if (exact) {
      const uid = typeof exact === 'string' ? exact : `${exact.code}:${exact.section}`;
      const row = typeof exact === 'string'
        ? await this.db.prepare('SELECT uid, code, section, title, text, history FROM law_sections WHERE uid = ? LIMIT 1').bind(uid).first()
        : await this.db.prepare('SELECT uid, code, section, title, text, history FROM law_sections WHERE code = ? AND section = ? LIMIT 1').bind(exact.code, exact.section).first();
      if (row) { const section = rowToSection(row, 1, 'exact'); results.push(section); seen.add(section.uid); methods.push('exact-section'); }
    }

    const tokens = query.toLowerCase().replace(/[^a-z0-9.\-\s]/g, ' ').split(/\s+/).filter(t => t.length >= 2).slice(0, 24);
    if (tokens.length) {
      const matchExpression = tokens.map(t => `"${t.replace(/"/g, '')}"`).join(' OR ');
      const sql = code
        ? `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, bm25(law_sections_fts) AS rank FROM law_sections_fts f JOIN law_sections s ON s.rowid = f.rowid WHERE law_sections_fts MATCH ? AND s.code = ? ORDER BY rank LIMIT ?`
        : `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, bm25(law_sections_fts) AS rank FROM law_sections_fts f JOIN law_sections s ON s.rowid = f.rowid WHERE law_sections_fts MATCH ? ORDER BY rank LIMIT ?`;
      const rows = code ? await this.db.prepare(sql).bind(matchExpression, code, limit * 2).all() : await this.db.prepare(sql).bind(matchExpression, limit * 2).all();
      methods.push('full-text');
      for (const row of rows.results) {
        const uid = String(row.uid ?? ''); if (!uid || seen.has(uid)) continue;
        const rank = Number(row.rank); const relevance = Number.isFinite(rank) ? 1 / (1 + Math.max(0, rank)) : 0;
        results.push(rowToSection(row, relevance, 'fulltext')); seen.add(uid);
        if (results.length >= limit) break;
      }
    }
    return { query, results: results.slice(0, limit), relationships: [], retrieval: { methods, complete: true } };
  }

  async getRelationships(uid: string, options: { direction?: 'outbound' | 'inbound' | 'both'; depth?: number; limit?: number } = {}): Promise<RelationshipEdge[]> {
    const root = clean(uid); if (!root) return [];
    const direction = options.direction ?? 'outbound';
    const depth = Math.min(Math.max(options.depth ?? 1, 1), MAX_TRAVERSAL_DEPTH);
    const limit = Math.min(Math.max(options.limit ?? 25, 1), MAX_TRAVERSAL_NODES);
    const edges: RelationshipEdge[] = [];
    const visited = new Set<string>([root]);
    let frontier = [root];

    for (let level = 0; level < depth && frontier.length && edges.length < limit; level++) {
      const next: string[] = [];
      for (const current of frontier) {
        let rows: { results: Record<string, unknown>[] } = { results: [] };
        if (direction === 'outbound' || direction === 'both') {
          const out = await this.db.prepare(`SELECT source_uid, target_uid, relationship, reference_text, confidence FROM section_relationships WHERE source_uid = ? LIMIT ?`).bind(current, limit - edges.length).all();
          rows.results.push(...out.results);
        }
        if (direction === 'inbound' || direction === 'both') {
          const incoming = await this.db.prepare(`SELECT source_uid, target_uid, relationship, reference_text, confidence FROM section_relationships WHERE target_uid = ? LIMIT ?`).bind(current, limit - edges.length).all();
          rows.results.push(...incoming.results);
        }
        for (const row of rows.results) {
          const edge: RelationshipEdge = {
            sourceUid: String(row.source_uid ?? ''), targetUid: row.target_uid ? String(row.target_uid) : undefined,
            relationship: String(row.relationship ?? 'related'), referenceText: row.reference_text ? String(row.reference_text) : undefined,
            confidence: Number.isFinite(Number(row.confidence)) ? Number(row.confidence) : 1,
          };
          const edgeKey = `${edge.sourceUid}|${edge.targetUid ?? ''}|${edge.relationship}|${edge.referenceText ?? ''}`;
          if (edges.some(e => `${e.sourceUid}|${e.targetUid ?? ''}|${e.relationship}|${e.referenceText ?? ''}` === edgeKey)) continue;
          edges.push(edge);
          const neighbor = edge.sourceUid === current ? edge.targetUid : edge.sourceUid;
          if (neighbor && !visited.has(neighbor) && visited.size < MAX_TRAVERSAL_NODES) { visited.add(neighbor); next.push(neighbor); }
          if (edges.length >= limit) break;
        }
        if (edges.length >= limit) break;
      }
      frontier = next;
    }
    return edges;
  }
}

export async function retrieve(db: D1Database, input: RetrievalQuery): Promise<EvidenceBundle> {
  return new D1ResearchRetriever(db).search(input);
}
