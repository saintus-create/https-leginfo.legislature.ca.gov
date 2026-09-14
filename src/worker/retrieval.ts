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
  matchType: 'exact' | 'fulltext';
}

export interface EvidenceBundle {
  query: string;
  results: RetrievedSection[];
  retrieval: {
    methods: string[];
    complete: boolean;
  };
}

const MAX_QUERY_LENGTH = 1000;
const MAX_RESULTS = 25;

function clean(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

function normalizeCode(value: string | undefined): string | undefined {
  const code = value ? value.trim().toUpperCase().replace(/[^A-Z0-9]/g, '') : '';
  return code || undefined;
}

function parseExactReference(query: string): { code: string; section: string } | null {
  const match = /\b([A-Z]{2,8})\s*(?:§|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)\b/i.exec(query);
  if (!match) return null;
  return { code: normalizeCode(match[1])!, section: match[2] };
}

function rowToSection(row: Record<string, unknown>, relevance: number, matchType: RetrievedSection['matchType']): RetrievedSection {
  const lawCode = String(row.code ?? '').toUpperCase();
  const sectionNum = String(row.section ?? '');
  return {
    uid: String(row.uid ?? `${lawCode}:${sectionNum}`),
    lawCode,
    sectionNum,
    citation: citationForSection({ lawCode, sectionNum }),
    title: typeof row.title === 'string' ? row.title : undefined,
    text: String(row.text ?? ''),
    history: typeof row.history === 'string' ? row.history : undefined,
    relevance,
    matchType,
  };
}

/**
 * Deterministic legislative retrieval. AI providers never participate here.
 * Exact section lookup is attempted before FTS so a question naming a section
 * cannot be displaced by a merely similar result.
 */
export async function retrieve(db: D1Database, input: RetrievalQuery): Promise<EvidenceBundle> {
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
    const exactCode = typeof exact === 'string' ? undefined : exact.code;
    const exactSection = typeof exact === 'string' ? undefined : exact.section;
    const row = typeof exact === 'string'
      ? await db.prepare(
          'SELECT uid, code, section, title, text, history FROM law_sections WHERE uid = ? LIMIT 1'
        ).bind(uid).first()
      : await db.prepare(
          'SELECT uid, code, section, title, text, history FROM law_sections WHERE code = ? AND section = ? LIMIT 1'
        ).bind(exactCode, exactSection).first();

    if (row) {
      const section = rowToSection(row, 1, 'exact');
      results.push(section);
      seen.add(section.uid);
      methods.push('exact-section');
    }
  }

  const tokens = query
    .toLowerCase()
    .replace(/[^a-z0-9.\-\s]/g, ' ')
    .split(/\s+/)
    .filter((token) => token.length >= 2)
    .slice(0, 24);

  if (tokens.length) {
    const matchExpression = tokens.map((token) => `"${token.replace(/"/g, '')}"`).join(' OR ');
    const sql = code
      ? `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, bm25(law_sections_fts) AS rank
         FROM law_sections_fts f
         JOIN law_sections s ON s.rowid = f.rowid
         WHERE law_sections_fts MATCH ? AND s.code = ?
         ORDER BY rank LIMIT ?`
      : `SELECT s.uid, s.code, s.section, s.title, s.text, s.history, bm25(law_sections_fts) AS rank
         FROM law_sections_fts f
         JOIN law_sections s ON s.rowid = f.rowid
         WHERE law_sections_fts MATCH ?
         ORDER BY rank LIMIT ?`;

    const rows = code
      ? await db.prepare(sql).bind(matchExpression, code, limit * 2).all()
      : await db.prepare(sql).bind(matchExpression, limit * 2).all();

    methods.push('full-text');
    for (const row of rows.results) {
      const uid = String(row.uid ?? '');
      if (!uid || seen.has(uid)) continue;
      const rawRank = Number(row.rank);
      const relevance = Number.isFinite(rawRank) ? 1 / (1 + Math.max(0, rawRank)) : 0;
      const section = rowToSection(row, relevance, 'fulltext');
      results.push(section);
      seen.add(uid);
      if (results.length >= limit) break;
    }
  }

  return {
    query,
    results: results.slice(0, limit),
    retrieval: {
      methods,
      complete: true,
    },
  };
}
