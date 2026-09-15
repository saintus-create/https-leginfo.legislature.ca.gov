import { StaticCorpusRetriever } from './worker/static-retrieval';
import { HybridResearchRetriever, type AISearchInstance } from './worker/ai-search';
import { ResearchOrchestrator, createCloudflareAIProvider, generateResearchAnswer } from './worker/orchestrator';

interface AI { run(model: string, input: unknown, options?: unknown): Promise<unknown>; }
interface DurableObjectNamespace { idFromName(name: string): unknown; get(id: unknown): { fetch(input: Request | string, init?: RequestInit): Promise<Response> }; }
interface Env {
  ASSETS: Fetcher;
  R2: R2Bucket;
  AI: AI;
  AI_SEARCH?: AISearchInstance;
  RESEARCH_SESSIONS: DurableObjectNamespace;
  AI_MODEL?: string;
}

const MAX_QUERY_LENGTH = 1000;
const DEFAULT_MODEL = '@cf/meta/llama-3.3-70b-instruct-fp8-fast';
const cors = (): HeadersInit => ({
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': 'content-type',
});
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', ...cors() },
});
function retriever(request: Request, env: Env) {
  const primary = new StaticCorpusRetriever(env.ASSETS, new URL(request.url));
  return env.AI_SEARCH ? new HybridResearchRetriever(primary, env.AI_SEARCH) : primary;
}

async function research(request: Request, env: Env) {
  const body = await request.json().catch(() => null) as { query?: unknown; messages?: unknown; sessionId?: unknown } | null;
  if (typeof body?.query !== 'string' || !body.query.trim()) return json({ error: 'A research question is required.' }, 400);
  if (body.query.length > MAX_QUERY_LENGTH) return json({ error: 'Research question is too long.' }, 413);
  const messages = Array.isArray(body.messages)
    ? body.messages.filter((m): m is { role: 'user' | 'assistant'; content: string } => !!m && typeof m === 'object' && ((m as any).role === 'user' || (m as any).role === 'assistant') && typeof (m as any).content === 'string').slice(-8)
    : [];
  try {
    const o = new ResearchOrchestrator(retriever(request, env));
    const result = await generateResearchAnswer(o, createCloudflareAIProvider(env.AI, env.AI_MODEL || DEFAULT_MODEL), body.query.trim(), messages);
    if (typeof body.sessionId === 'string' && body.sessionId.trim()) {
      const id = env.RESEARCH_SESSIONS.idFromName(body.sessionId.trim());
      await env.RESEARCH_SESSIONS.get(id).fetch('https://research-session/state', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ query: body.query.trim(), answer: result.answer, state: result.state }),
      });
    }
    return json(result);
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : 'Research failed.' }, 502);
  }
}

async function search(request: Request, env: Env) {
  const body = await request.json().catch(() => null) as { query?: unknown; code?: string; limit?: number; exactUid?: string } | null;
  if (typeof body?.query !== 'string' || !body.query.trim()) return json({ error: 'A search query is required.' }, 400);
  try { return json(await retriever(request, env).search(body)); }
  catch (e) { return json({ error: e instanceof Error ? e.message : 'Legislative retrieval failed.' }, 400); }
}

async function aiSearch(request: Request, env: Env) {
  if (!env.AI_SEARCH) return json({ error: 'AI Search binding is not configured.' }, 503);
  const body = await request.json().catch(() => null) as { query?: string; messages?: unknown; stream?: boolean } | null;
  const query = body?.query?.trim() || '';
  const messages = Array.isArray(body?.messages) ? body.messages : [{ role: 'user', content: query }];
  if (!query && !messages.length) return json({ error: 'A research question is required.' }, 400);
  const stream = body?.stream !== false;
  const response = await env.AI_SEARCH.chatCompletions({
    messages,
    model: env.AI_MODEL || DEFAULT_MODEL,
    stream,
    ai_search_options: {
      retrieval: { retrieval_type: 'hybrid', fusion_method: 'rrf', max_num_results: 12, match_threshold: 0.25, context_expansion: 1 },
      query_rewrite: { enabled: true },
      reranking: { enabled: true, model: '@cf/baai/bge-reranker-base', match_threshold: 0.2 },
      cache: { enabled: true, cache_threshold: 'close_enough' },
    },
  });
  if (stream && response instanceof ReadableStream) return new Response(response, { headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', ...cors() } });
  return json(response);
}

async function session(request: Request, env: Env, idText: string) {
  const id = env.RESEARCH_SESSIONS.idFromName(idText);
  return env.RESEARCH_SESSIONS.get(id).fetch(new Request(new URL('/state', request.url), request));
}

export class ResearchSession {
  private readonly state: any;
  constructor(state: any) { this.state = state; }
  async fetch(request: Request) {
    const url = new URL(request.url);
    if (request.method === 'GET') {
      return new Response(JSON.stringify(await this.state.storage.get('research') || { messages: [], findings: [] }), { headers: { 'content-type': 'application/json', ...cors() } });
    }
    if (request.method === 'POST') {
      const value = await request.json().catch(() => null);
      if (!value) return json({ error: 'Invalid research state.' }, 400);
      const current = await this.state.storage.get('research') || { messages: [], findings: [] };
      current.messages = [...(current.messages || []), { query: value.query, answer: value.answer }].slice(-20);
      current.findings = value.state?.findings || current.findings;
      await this.state.storage.put('research', current);
      return new Response(JSON.stringify(current), { headers: { 'content-type': 'application/json', ...cors() } });
    }
    return new Response('Method Not Allowed', { status: 405 });
  }
}

export default {
  async fetch(request: Request, env: Env) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors() });
    const url = new URL(request.url);
    if (url.pathname === '/api/research' && request.method === 'POST') return research(request, env);
    if (url.pathname === '/api/search' && request.method === 'POST') return search(request, env);
    if (url.pathname === '/api/answer' && request.method === 'POST') return aiSearch(request, env);
    const sessionMatch = url.pathname.match(/^\/api\/research\/session\/([^/]+)$/);
    if (sessionMatch && (request.method === 'GET' || request.method === 'POST')) return session(request, env, decodeURIComponent(sessionMatch[1]));
    if (url.pathname === '/api/health' && request.method === 'GET') return json({ ok: true, service: 'leginfo', retrieval: env.AI_SEARCH ? 'ai-search-hybrid' : 'static-corpus', research: true, sessions: true, aiSearch: Boolean(env.AI_SEARCH), model: env.AI_MODEL || DEFAULT_MODEL });
    return env.ASSETS.fetch(request);
  },
};
