import { citationForSection } from '../leginfo/citations';
import type { EvidenceBundle, HistoryEvent, RelationshipEdge, ResearchRetriever, RetrievalQuery, RetrievedSection } from './retrieval';

interface FetcherLike { fetch(input: Request | string, init?: RequestInit): Promise<Response>; }

const CODE_NAMES: Record<string, string> = {
  BPC: 'Business and Professions Code', CIV: 'Civil Code', CCP: 'Code of Civil Procedure', COM: 'Commercial Code',
  CORP: 'Corporations Code', EDC: 'Education Code', ELEC: 'Elections Code', EVID: 'Evidence Code', FAM: 'Family Code',
  FIN: 'Financial Code', FGC: 'Fish and Game Code', FAC: 'Food and Agricultural Code', GOV: 'Government Code',
  HNC: 'Harbors and Navigation Code', HSC: 'Health and Safety Code', INS: 'Insurance Code', LAB: 'Labor Code',
  MVC: 'Military and Veterans Code', PEN: 'Penal Code', PROB: 'Probate Code', PCC: 'Public Contract Code',
  PRC: 'Public Resources Code', PUC: 'Public Utilities Code', RTC: 'Revenue and Taxation Code', SHC: 'Streets and Highways Code',
  UIC: 'Unemployment Insurance Code', VEH: 'Vehicle Code', WAT: 'Water Code', WIC: 'Welfare and Institutions Code', CONS: 'California Constitution',
};

const ALIASES: Record<string, string> = {
  ...Object.fromEntries(Object.entries(CODE_NAMES).flatMap(([k, v]) => [[k.toLowerCase(), k], [v.toLowerCase(), k]])),
  family: 'FAM', government: 'GOV', civil: 'CIV', penal: 'PEN', evidence: 'EVID', probate: 'PROB',
  labor: 'LAB', 'health and safety': 'HSC', 'welfare and institutions': 'WIC', vehicle: 'VEH', education: 'EDC',
  'business and professions': 'BPC', 'code of civil procedure': 'CCP', 'california constitution': 'CONS',
};

const STOP = new Set(['the','and','for','that','this','with','from','shall','may','must','such','which','into','upon','under','there','their','them','than','then','where','when','what','have','has','had','not','any','all','each','other','more','only','section','sections','code','codes','california']);
const tokenise = (s: string) => [...new Set((s.toLowerCase().match(/[a-z0-9][a-z0-9._-]{2,}/g) || []).filter(x => !STOP.has(x)))].slice(0, 24);
const exactRef = (q: string) => /\b([A-Z]{2,8})\s*(?:§|section)\s*([A-Z0-9]+(?:[.\-][A-Z0-9]+)*)\b/i.exec(q);

function codeFromQuery(q: string): string | undefined {
  const x = q.toLowerCase();
  for (const [alias, code] of Object.entries(ALIASES).sort((a, b) => b[0].length - a[0].length)) if (x.includes(alias)) return code;
  const ref = exactRef(q);
  return ref?.[1]?.toUpperCase();
}

function score(rec: any, terms: string[], phrase: string): number {
  const hay = `${rec.title || ''} ${rec.text || ''}`.toLowerCase();
  let value = 0;
  for (const term of terms) {
    const hits = hay.split(term).length - 1;
    value += Math.min(hits, 8) * (rec.title?.toLowerCase().includes(term) ? 5 : 1);
  }
  if (phrase && hay.includes(phrase.toLowerCase())) value += 15;
  return value;
}

export class StaticCorpusRetriever implements ResearchRetriever {
  constructor(private readonly assets: FetcherLike, private readonly baseUrl: URL) {}

  private async manifest(): Promise<{ codes: Record<string, string[]> }> {
    const r = await this.assets.fetch(new URL('/data/law/manifest.json', this.baseUrl).toString());
    if (!r.ok) throw new Error(`Legislative corpus manifest unavailable (${r.status}).`);
    const manifest = await r.json() as { codes?: Record<string, string[]> };
    if (!manifest.codes || typeof manifest.codes !== 'object') throw new Error('Legislative corpus manifest is invalid.');
    return manifest as { codes: Record<string, string[]> };
  }

  private async index(): Promise<any> {
    const r = await this.assets.fetch(new URL('/data/research-index.json', this.baseUrl).toString());
    if (!r.ok) throw new Error(`Legislative research index unavailable (${r.status}).`);
    return await r.json();
  }

  private async scanPart(path: string, terms: string[], phrase: string, exactCode?: string, exactSection?: string, limit = 12): Promise<any[]> {
    const r = await this.assets.fetch(new URL(`/data/law/${path}`, this.baseUrl).toString());
    if (!r.ok) return [];
    const reader = r.body?.getReader();
    if (!reader) return [];
    const decoder = new TextDecoder();
    let buffer = '';
    const best: any[] = [];
    const push = (rec: any) => {
      if (rec?.kind !== 'section') return;
      const code = String(rec.code || '').toUpperCase();
      const section = String(rec.section || '');
      if (exactCode && code !== exactCode) return;
      if (exactSection && section !== exactSection) return;
      if (!exactSection && !terms.length) return;
      const relevance = exactSection ? 10000 : score(rec, terms, phrase);
      if (!exactSection && relevance <= 0) return;
      best.push({ rec, relevance });
      best.sort((a, b) => b.relevance - a.relevance);
      if (best.length > limit) best.pop();
    };
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) { if (!line.trim()) continue; try { push(JSON.parse(line)); } catch {} }
      if (done) break;
    }
    if (buffer.trim()) { try { push(JSON.parse(buffer)); } catch {} }
    return best;
  }

  private toSection(rec: any, relevance: number, matchType: RetrievedSection['matchType']): RetrievedSection {
    const code = String(rec.code || '').toUpperCase();
    const section = String(rec.section || '');
    return {
      uid: String(rec.uid || `${code}:${section}`), lawCode: code, sectionNum: section,
      citation: citationForSection({ lawCode: code, sectionNum: section }),
      title: typeof rec.title === 'string' ? rec.title : undefined,
      text: String(rec.text || ''), history: typeof rec.history === 'string' ? rec.history : undefined,
      relevance, matchType,
    };
  }

  async search(input: RetrievalQuery): Promise<EvidenceBundle> {
    const query = input.query.trim();
    const limit = Math.max(1, Math.min(input.limit || 10, 20));
    const code = (input.code || codeFromQuery(query))?.toUpperCase();
    const exact = input.exactUid?.trim() || (() => { const m = exactRef(query); return m ? `${m[1].toUpperCase()}:${m[2]}` : undefined; })();
    const idx = await this.index();
    const manifest = await this.manifest();
    const terms = tokenise(query);
    const phrase = query.replace(/\b(?:what|is|the|a|an|how|does|do|can|please)\b/gi, ' ').replace(/\s+/g, ' ').trim();
    const candidateCodes = new Set<string>();

    if (code) candidateCodes.add(code);
    if (!code && idx.terms) {
      for (const term of terms) for (const uid of (idx.terms[term] || [])) candidateCodes.add(String(uid).split(':')[0]);
    }
    if (!candidateCodes.size) Object.keys(manifest.codes).slice(0, 6).forEach(c => candidateCodes.add(c));

    const exactMatch = exact?.match(/^([A-Z0-9]+):(.+)$/);
    const all: any[] = [];
    for (const c of candidateCodes) {
      const parts = manifest.codes[c] || [];
      for (const part of parts) {
        const found = await this.scanPart(part, terms, phrase, exactMatch?.[1], exactMatch?.[2], limit);
        all.push(...found);
        if (exactMatch && found.length) break;
      }
      if (exactMatch && all.length) break;
    }
    all.sort((a, b) => b.relevance - a.relevance);
    const seen = new Set<string>();
    const results: RetrievedSection[] = [];
    for (const item of all) {
      const section = this.toSection(item.rec, item.relevance, exactMatch ? 'exact' : 'fulltext');
      if (seen.has(section.uid)) continue;
      seen.add(section.uid); results.push(section);
      if (results.length >= limit) break;
    }
    return { query, results, relationships: [], retrieval: { methods: ['static-corpus', 'lexical-search'], complete: true } };
  }

  async getSection(uid: string): Promise<RetrievedSection | null> {
    const [code, section] = uid.split(':', 2);
    if (!code || !section) return null;
    const e = await this.search({ query: `${code} section ${section}`, exactUid: uid, limit: 1 });
    return e.results[0] || null;
  }

  async getRelationships(_uid: string): Promise<RelationshipEdge[]> { return []; }
  async getHistory(_uid: string): Promise<HistoryEvent[]> { return []; }
}
