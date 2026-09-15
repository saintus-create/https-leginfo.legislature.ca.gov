interface AISearchInstance {
  search(input: Record<string, unknown>): Promise<unknown>;
  chatCompletions(input: Record<string, unknown>): Promise<Response | ReadableStream>;
}
interface Env {
  ASSETS: Fetcher;
  AI_SEARCH?: AISearchInstance;
  AI_MODEL?: string;
}

const DEFAULT_MODEL = '@cf/meta/llama-3.3-70b-instruct-fp8-fast';
const SYSTEM_PROMPT = `You are the California Law AI for this application. Answer the user's question using the California legal corpus retrieved by AI Search. Reason over the retrieved source material; do not merely match keywords or concatenate passages. Distinguish what the sources actually establish from inference. When the retrieved material is insufficient, say so rather than inventing law. Prefer exact California statutory language when the user asks what a statute says. Preserve section numbers, subdivisions, dates, and defined terms accurately. Cite the retrieved sources in the response when citations are available.`;

const cors = (): HeadersInit => ({
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': 'content-type',
});

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', ...cors() },
});

async function answer(request: Request, env: Env) {
  if (!env.AI_SEARCH) return json({ error: 'AI Search binding is not configured.' }, 503);

  const body = await request.json().catch(() => null) as {
    query?: unknown;
    messages?: unknown;
    stream?: boolean;
  } | null;

  const suppliedMessages = Array.isArray(body?.messages)
    ? body.messages.filter((m): m is { role: 'system' | 'user' | 'assistant'; content: string } =>
        !!m && typeof m === 'object' &&
        ['system', 'user', 'assistant'].includes((m as any).role) &&
        typeof (m as any).content === 'string')
      .slice(-12)
    : [];

  const query = typeof body?.query === 'string' ? body.query.trim() : '';
  const messages = suppliedMessages.length
    ? [{ role: 'system', content: SYSTEM_PROMPT }, ...suppliedMessages]
    : [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: query },
      ];

  if (!query && suppliedMessages.length === 0) {
    return json({ error: 'A question is required.' }, 400);
  }

  try {
    const response = await env.AI_SEARCH.chatCompletions({
      messages,
      model: env.AI_MODEL || DEFAULT_MODEL,
      stream: body?.stream !== false,
      ai_search_options: {
        retrieval: {
          retrieval_type: 'hybrid',
          max_num_results: 12,
          match_threshold: 0.25,
          context_expansion: 1,
        },
        query_rewrite: { enabled: true },
        reranking: {
          enabled: true,
          model: '@cf/baai/bge-reranker-base',
          match_threshold: 0.2,
        },
      },
    });

    if (response instanceof ReadableStream) {
      return new Response(response, {
        headers: {
          'content-type': 'text/event-stream',
          'cache-control': 'no-cache',
          ...cors(),
        },
      });
    }

    return response;
  } catch (error) {
    return json({
      error: error instanceof Error ? error.message : 'AI generation failed.',
    }, 502);
  }
}

async function search(request: Request, env: Env) {
  if (!env.AI_SEARCH) return json({ error: 'AI Search binding is not configured.' }, 503);
  const body = await request.json().catch(() => null) as { query?: unknown } | null;
  if (typeof body?.query !== 'string' || !body.query.trim()) {
    return json({ error: 'A search query is required.' }, 400);
  }

  try {
    const result = await env.AI_SEARCH.search({
      messages: [{ role: 'user', content: body.query.trim() }],
      ai_search_options: {
        retrieval: {
          retrieval_type: 'hybrid',
          max_num_results: 12,
          match_threshold: 0.25,
          context_expansion: 1,
        },
        query_rewrite: { enabled: true },
        reranking: {
          enabled: true,
          model: '@cf/baai/bge-reranker-base',
          match_threshold: 0.2,
        },
      },
    });
    return json(result);
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : 'AI Search failed.' }, 502);
  }
}

export default {
  async fetch(request: Request, env: Env) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors() });
    const url = new URL(request.url);

    if ((url.pathname === '/api/answer' || url.pathname === '/api/research') && request.method === 'POST') {
      return answer(request, env);
    }

    if (url.pathname === '/api/search' && request.method === 'POST') {
      return search(request, env);
    }

    if (url.pathname === '/api/health' && request.method === 'GET') {
      return json({
        ok: true,
        service: 'leginfo-ai',
        ai: 'cloudflare-ai-search-chat-completions',
        aiSearch: Boolean(env.AI_SEARCH),
        model: env.AI_MODEL || DEFAULT_MODEL,
      });
    }

    return env.ASSETS.fetch(request);
  },
};
