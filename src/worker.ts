import { retrieve, type D1Database, type RetrievalQuery } from './worker/retrieval';

interface Env {
  ASSETS: Fetcher;
  R2: R2Bucket;
  LEGINFO_DB?: D1Database;
  AI_SEARCH_ENDPOINT?: string;
}

const DEFAULT_AI_SEARCH_ENDPOINT = 'https://5f679b75-e58c-4cbd-8350-b2c83df8f361.search.ai.cloudflare.com/search';
const MAX_QUERY_LENGTH = 1000;

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...corsHeaders() },
  });
}

function corsHeaders(): HeadersInit {
  return {
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,POST,OPTIONS',
    'access-control-allow-headers': 'content-type',
  };
}

async function aiSearch(request: Request, env: Env): Promise<Response> {
  const body = await request.json().catch(() => null) as { messages?: unknown[]; query?: string } | null;
  if (!body) return json({ error: 'Invalid JSON body.' }, 400);

  const messages = Array.isArray(body.messages) ? body.messages : [];
  const last = messages[messages.length - 1] as { content?: unknown } | undefined;
  const query = typeof body.query === 'string'
    ? body.query.trim()
    : typeof last?.content === 'string'
      ? last.content.trim()
      : '';

  if (!query) return json({ error: 'A search question is required.' }, 400);
  if (query.length > MAX_QUERY_LENGTH) return json({ error: 'Search question is too long.' }, 413);

  const payload = {
    messages: [{ role: 'user', content: query }],
    ai_search_options: {
      retrieval: { max_num_results: 8, keyword_match_mode: 'or' },
    },
  };

  const upstream = await fetch(env.AI_SEARCH_ENDPOINT || DEFAULT_AI_SEARCH_ENDPOINT, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { 'content-type': upstream.headers.get('content-type') || 'application/json', ...corsHeaders() },
  });
}

async function legislativeSearch(request: Request, env: Env): Promise<Response> {
  if (!env.LEGINFO_DB) {
    return json({ error: 'Legislative retrieval is not configured.' }, 503);
  }

  const body = await request.json().catch(() => null) as RetrievalQuery | null;
  if (!body || typeof body.query !== 'string') {
    return json({ error: 'A search query is required.' }, 400);
  }

  try {
    const evidence = await retrieve(env.LEGINFO_DB, body);
    return json(evidence);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Legislative retrieval failed.';
    const status = message.includes('too long') ? 413 : 400;
    return json({ error: message }, status);
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders() });

    const url = new URL(request.url);

    if (url.pathname === '/api/search' && request.method === 'POST') {
      return await legislativeSearch(request, env);
    }

    if (url.pathname === '/api/answer' && request.method === 'POST') {
      try {
        return await aiSearch(request, env);
      } catch (error) {
        return json({ error: error instanceof Error ? error.message : 'AI Search unavailable.' }, 502);
      }
    }

    if (url.pathname === '/api/health' && request.method === 'GET') {
      return json({
        ok: true,
        service: 'leginfo',
        retrieval: Boolean(env.LEGINFO_DB),
        ai: Boolean(env.AI_SEARCH_ENDPOINT || DEFAULT_AI_SEARCH_ENDPOINT),
      });
    }

    const assetResponse = await env.ASSETS.fetch(request);
    return assetResponse;
  },
};
