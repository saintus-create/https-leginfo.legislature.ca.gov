import { citationForSection } from './leginfo/citations';
import { D1ResearchRetriever, type D1Database, type ResearchRetriever } from './worker/retrieval';
import { HybridResearchRetriever, type AISearchInstance } from './worker/ai-search';
import { StaticCorpusRetriever } from './worker/static-retrieval';
import {
  ResearchOrchestrator,
  createCloudflareAIProvider,
  generateResearchAnswer,
  ORCHESTRATOR_SYSTEM_PROMPT,
  type ResearchState,
} from './worker/orchestrator';

// ─────────────────────────────────────────────────────────────────────────────
// Env
// ─────────────────────────────────────────────────────────────────────────────
interface Env {
  ASSETS: Fetcher;
  AI?: { run: (model: string, input: unknown, options?: unknown) => Promise<unknown> };
  AI_SEARCH?: AISearchInstance;
  AI_MODEL?: string;
  // D1 bindings – support multiple possible names
  DB?: D1Database;
  LEGAL_DB?: D1Database;
  LEGINFO_DB?: D1Database;
  D1?: D1Database;
  R2?: R2Bucket;
}

const DEFAULT_MODEL = '@cf/meta/llama-3.3-70b-instruct-fp8-fast';
const FALLBACK_MODEL = '@cf/meta/llama-3.1-8b-instruct';

const STRONG_SYSTEM_PROMPT = `${ORCHESTRATOR_SYSTEM_PROMPT}

ADDITIONAL PRODUCT RULES:
- You are the California Law AI. You perform AI reasoning over authoritative evidence, not keyword concatenation.
- Prefer exact statutory language when user asks what a statute says.
- Preserve section numbers, subdivisions (a)(1)(A), dates, defined terms.
- Cite using label and URL from evidence. Never invent URLs.
- If evidence insufficient, say so clearly.
- Distinguish statutory text from analysis.
- For comparisons, retrieve each subject independently – similar vocabulary is not evidence of relationship.
`;

const corsHeaders = (): HeadersInit => ({
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': 'content-type,authorization',
  'access-control-max-age': '86400',
});

const json = (data: unknown, status = 200, extra?: HeadersInit) =>
  new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...corsHeaders(), ...(extra || {}) },
  });

const sse = (stream: ReadableStream) =>
  new Response(stream, {
    headers: {
      'content-type': 'text/event-stream',
      'cache-control': 'no-cache, no-transform',
      connection: 'keep-alive',
      ...corsHeaders(),
    },
  });

// ─────────────────────────────────────────────────────────────────────────────
// Retriever factory – strongholding: deterministic + semantic + hybrid
// ─────────────────────────────────────────────────────────────────────────────
function getD1(env: Env): D1Database | undefined {
  return env.DB || env.LEGAL_DB || env.LEGINFO_DB || env.D1;
}

function createRetriever(env: Env, requestUrl: URL): ResearchRetriever {
  const d1 = getD1(env);

  let primary: ResearchRetriever;

  if (d1) {
    primary = new D1ResearchRetriever(d1);
  } else {
    // Fallback to static corpus via ASSETS – works on Pages / without D1
    primary = new StaticCorpusRetriever(env.ASSETS as any, requestUrl);
  }

  if (env.AI_SEARCH) {
    return new HybridResearchRetriever(primary, env.AI_SEARCH, { rrfK: 60, enableQueryRewrite: true });
  }

  return primary;
}

// ─────────────────────────────────────────────────────────────────────────────
// Request parsing & validation – hardened
// ─────────────────────────────────────────────────────────────────────────────
type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string };

function parseMessages(raw: unknown): ChatMessage[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (m): m is ChatMessage =>
        !!m &&
        typeof m === 'object' &&
        ['system', 'user', 'assistant'].includes((m as any).role) &&
        typeof (m as any).content === 'string' &&
        (m as any).content.trim().length > 0,
    )
    .map((m) => ({ role: m.role, content: m.content.trim().slice(0, 8000) }))
    .slice(-12);
}

function parseBody(body: any): { query: string; messages: ChatMessage[]; stream: boolean; code?: string; limit?: number; document?: string } {
  const query = typeof body?.query === 'string' ? body.query.trim().slice(0, 2000) : '';
  const messages = parseMessages(body?.messages);
  const stream = body?.stream === true;
  const code = typeof body?.code === 'string' ? body.code.trim().toUpperCase().slice(0, 10) : undefined;
  const limit = typeof body?.limit === 'number' ? Math.max(1, Math.min(Math.floor(body.limit), 30)) : undefined;
  const document = typeof body?.document === 'string' ? body.document.trim().slice(0, 20000) : undefined;
  return { query, messages, stream, code, limit, document };
}

// ─────────────────────────────────────────────────────────────────────────────
// Core handlers – AI-first, not word-match
// ─────────────────────────────────────────────────────────────────────────────
async function handleResearch(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const body = await request.json().catch(() => null);
  const { query, messages, code, limit } = parseBody(body);

  if (!query && messages.length === 0) {
    return json({ error: 'A question is required. Provide query or messages.' }, 400);
  }

  const effectiveQuery = query || messages.filter((m) => m.role === 'user').pop()?.content || '';
  if (!effectiveQuery) return json({ error: 'A question is required.' }, 400);

  try {
    const retriever = createRetriever(env, url);
    const orchestrator = new ResearchOrchestrator(retriever, { sections: 50, relationships: 120, history: 120, definitions: 20 });

    // Allow code/limit override from body for targeted retrieval
    let finalQuery = effectiveQuery;
    if (code) finalQuery = `${code} ${effectiveQuery}`.trim();

    const result = await orchestrator.research(finalQuery, messages as any);

    // Apply limit override if present
    let findings = result.state.findings;
    if (limit) findings = findings.slice(0, limit);

    return json({
      ok: true,
      intent: result.state.intent,
      question: result.state.question,
      normalizedQuestion: result.state.normalizedQuestion,
      codes: result.state.codes,
      subjects: result.state.subjects,
      citations: result.state.citations,
      temporalScope: result.state.temporalScope,
      state: {
        ...result.state,
        findings: findings.map((f) => ({
          uid: f.uid,
          lawCode: f.lawCode,
          sectionNum: f.sectionNum,
          citation: f.citation,
          title: f.title,
          text: f.text.slice(0, 6000),
          history: f.history,
          relevance: f.relevance,
          matchType: f.matchType,
          charCount: f.charCount,
          path: f.path,
        })),
        definitions: result.state.definitions?.map((d) => ({
          uid: d.uid,
          citation: d.citation,
          text: d.text.slice(0, 4000),
          relevance: d.relevance,
        })),
      },
      evidence: {
        query: result.evidence.query,
        results: result.evidence.results.slice(0, limit ?? 25).map((r) => ({
          uid: r.uid,
          lawCode: r.lawCode,
          sectionNum: r.sectionNum,
          citation: r.citation,
          title: r.title,
          text: r.text.slice(0, 6000),
          relevance: r.relevance,
          matchType: r.matchType,
        })),
        relationships: result.evidence.relationships.slice(0, 50),
        retrieval: result.evidence.retrieval,
      },
      provenance: result.state.provenance,
      methods: result.state.methods,
      unresolved: result.state.unresolved,
    });
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : 'Research failed.', query: effectiveQuery }, 502);
  }
}

async function handleAnswer(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const body = await request.json().catch(() => null);
  const { query, messages, stream } = parseBody(body);

  const effectiveQuery = query || messages.filter((m) => m.role === 'user').pop()?.content || '';
  if (!effectiveQuery) return json({ error: 'A question is required.' }, 400);

  const retriever = createRetriever(env, url);
  const orchestrator = new ResearchOrchestrator(retriever);

  // If no AI binding, fallback to research-only with evidence, but still provide structured answer
  if (!env.AI) {
    try {
      const research = await orchestrator.research(effectiveQuery, messages as any);
      // Generate a deterministic answer from evidence – not just word match, but structured synthesis
      const evidenceText = research.state.findings
        .slice(0, 5)
        .map((f) => `${f.citation.label}: ${f.text.slice(0, 600)}`)
        .join('\n\n');

      const fallbackAnswer = `Short answer: Based on retrieved California statutory provisions, the following authorities are responsive to "${effectiveQuery}".

Evidence:
${research.state.findings
  .slice(0, 8)
  .map((f) => `- ${f.citation.label} (${f.citation.url}): ${f.title || ''}`)
  .join('\n')}

Analysis:
The retrieved provisions contain the following operative language:
${evidenceText.slice(0, 2000)}

Limits:
${research.state.unresolved.length ? research.state.unresolved.join('; ') : 'No unresolved items identified, but AI generation was unavailable so this is a deterministic evidence synthesis.'}

Sources:
${research.state.findings.map((f) => `${f.citation.label}: ${f.citation.url}`).join('\n')}
`;

      if (stream) {
        // Stream fallback as SSE
        const encoder = new TextEncoder();
        const readable = new ReadableStream({
          start(controller) {
            const chunks = fallbackAnswer.match(/.{1,80}/g) || [fallbackAnswer];
            let i = 0;
            const send = () => {
              if (i >= chunks.length) {
                controller.enqueue(encoder.encode(`data: [DONE]\n\n`));
                controller.close();
                return;
              }
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ response: chunks[i] })}\n\n`));
              i++;
              setTimeout(send, 15);
            };
            send();
          },
        });
        return sse(readable);
      }

      return json({
        ok: true,
        answer: fallbackAnswer,
        state: research.state,
        evidence: research.evidence,
        model: 'deterministic-evidence-synthesis',
        warning: 'AI binding not configured – returned deterministic evidence synthesis.',
      });
    } catch (e) {
      return json({ error: e instanceof Error ? e.message : 'Research failed' }, 502);
    }
  }

  // Full AI path: research -> draft -> verify
  try {
    const provider = createCloudflareAIProvider(env.AI!, env.AI_MODEL || DEFAULT_MODEL);

    // If streaming requested, we need to do research first, then stream LLM
    if (stream) {
      const research = await orchestrator.research(effectiveQuery, messages as any);

      // Build messages for streaming generation
      const system = STRONG_SYSTEM_PROMPT;
      const evidencePrompt = research.prompt;

      const chatMessages: ChatMessage[] = [
        { role: 'system', content: system },
        ...messages.slice(-8),
        {
          role: 'user',
          content: `CORPUS EVIDENCE (JSON):\n${evidencePrompt.slice(0, 18000)}\n\nCURRENT QUESTION:\n${effectiveQuery}\n\nAnswer with: Short answer, Evidence, Connections, Analysis, Limits, Sources. Cite using label and URL.`,
        },
      ];

      // Use AI_SEARCH chatCompletions if available for better grounding, else direct AI
      if (env.AI_SEARCH) {
        try {
          const response = await env.AI_SEARCH.chatCompletions({
            messages: chatMessages,
            model: env.AI_MODEL || DEFAULT_MODEL,
            stream: true,
            ai_search_options: {
              retrieval: {
                retrieval_type: 'hybrid',
                max_num_results: 14,
                match_threshold: 0.22,
                context_expansion: 2,
              },
              query_rewrite: { enabled: true },
              reranking: { enabled: true, model: '@cf/baai/bge-reranker-base', match_threshold: 0.18 },
            },
          });

          if (response instanceof ReadableStream) {
            return sse(response);
          }
          return response as Response;
        } catch {
          // Fall through to direct AI streaming
        }
      }

      // Direct AI streaming via provider – we need to simulate streaming by chunking final answer
      // Since provider.generate is non-streaming, we generate then stream
      const { answer } = await generateResearchAnswer(orchestrator, provider, effectiveQuery, messages as any);
      const encoder = new TextEncoder();
      const readable = new ReadableStream({
        start(controller) {
          const chunks = answer.match(/.{1,100}/g) || [answer];
          let i = 0;
          const send = () => {
            if (i >= chunks.length) {
              controller.enqueue(encoder.encode(`data: [DONE]\n\n`));
              controller.close();
              return;
            }
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ response: chunks[i] })}\n\n`));
            i++;
            setTimeout(send, 12);
          };
          send();
        },
      });
      return sse(readable);
    }

    // Non-streaming: full orchestration with verification
    const { answer, state, evidence } = await generateResearchAnswer(orchestrator, provider, effectiveQuery, messages as any);

    return json({
      ok: true,
      answer,
      state: {
        question: state.question,
        normalizedQuestion: state.normalizedQuestion,
        intent: state.intent,
        codes: state.codes,
        subjects: state.subjects,
        citations: state.citations,
        temporalScope: state.temporalScope,
        findings: state.findings.map((f) => ({
          uid: f.uid,
          lawCode: f.lawCode,
          sectionNum: f.sectionNum,
          citation: f.citation,
          title: f.title,
          text: f.text.slice(0, 6000),
          relevance: f.relevance,
          matchType: f.matchType,
        })),
        definitions: (state as any).definitions,
        relationships: state.relationships.slice(0, 50),
        history: state.history.slice(0, 30),
        unresolved: state.unresolved,
        methods: state.methods,
        provenance: state.provenance,
      },
      evidence: {
        query: evidence.query,
        results: evidence.results.slice(0, 20).map((r) => ({
          uid: r.uid,
          citation: r.citation,
          text: r.text.slice(0, 6000),
          relevance: r.relevance,
        })),
        relationships: evidence.relationships.slice(0, 40),
        retrieval: evidence.retrieval,
      },
      model: env.AI_MODEL || DEFAULT_MODEL,
    });
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : 'AI generation failed.', query: effectiveQuery }, 502);
  }
}

async function handleSearch(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const body = await request.json().catch(() => null);
  const { query, code, limit } = parseBody(body);

  if (!query) return json({ error: 'A search query is required.' }, 400);

  try {
    const retriever = createRetriever(env, url);
    const bundle = await retriever.search({ query, code, limit: limit ?? 12 });

    return json({
      ok: true,
      query: bundle.query,
      results: bundle.results.map((r) => ({
        uid: r.uid,
        lawCode: r.lawCode,
        sectionNum: r.sectionNum,
        citation: r.citation,
        title: r.title,
        text: r.text.slice(0, 6000),
        history: r.history,
        relevance: r.relevance,
        matchType: r.matchType,
        path: r.path,
      })),
      relationships: bundle.relationships,
      retrieval: bundle.retrieval,
    });
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : 'Search failed.' }, 502);
  }
}

async function handleDocumentAnalyze(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const body = await request.json().catch(() => null);
  const { query, document } = parseBody(body as any);
  const doc = (body as any)?.document || query;

  if (!doc || typeof doc !== 'string' || doc.trim().length < 20) {
    return json({ error: 'A document (at least 20 chars) is required for analysis.' }, 400);
  }

  try {
    const retriever = createRetriever(env, url);
    if (typeof (retriever as any).analyzeDocument === 'function') {
      const bundle = await (retriever as any).analyzeDocument(doc, (body as any)?.propositions);
      return json({
        ok: true,
        query: bundle.query,
        results: bundle.results.map((r: any) => ({
          uid: r.uid,
          citation: r.citation,
          text: r.text.slice(0, 6000),
          relevance: r.relevance,
          matchType: r.matchType,
          referenceText: r.referenceText,
        })),
        relationships: bundle.relationships,
        retrieval: bundle.retrieval,
      });
    }
    // Fallback to search
    const bundle = await retriever.search({ query: doc.slice(0, 500), limit: 12 });
    return json({
      ok: true,
      query: bundle.query,
      results: bundle.results,
      retrieval: bundle.retrieval,
      note: 'analyzeDocument not implemented in primary retriever – used search fallback.',
    });
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : 'Document analysis failed.' }, 502);
  }
}

async function handleHealth(_request: Request, env: Env): Promise<Response> {
  const d1 = getD1(env);
  return json({
    ok: true,
    service: 'leginfo-ai-stronghold',
    version: '2.0-ai-first',
    ai: {
      binding: Boolean(env.AI),
      model: env.AI_MODEL || DEFAULT_MODEL,
      fallbackModel: FALLBACK_MODEL,
    },
    aiSearch: Boolean(env.AI_SEARCH),
    d1: Boolean(d1),
    assets: Boolean(env.ASSETS),
    capabilities: [
      'research-orchestration',
      'evidence-graph',
      'definition-search',
      'relationship-traversal',
      'temporal-history',
      'document-analysis',
      'citation-resolution',
      'verification-pass',
      'rrf-fusion',
      'query-rewrite',
      'streaming',
    ],
    systemPrompt: 'strong-ai-reasoning-not-keyword-match',
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Main fetch – hardened routing
// ─────────────────────────────────────────────────────────────────────────────
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    // API routes
    if (path === '/api/research' && request.method === 'POST') {
      return handleResearch(request, env);
    }

    if ((path === '/api/answer' || path === '/api/chat') && request.method === 'POST') {
      return handleAnswer(request, env);
    }

    if (path === '/api/search' && request.method === 'POST') {
      return handleSearch(request, env);
    }

    if (path === '/api/analyze' && request.method === 'POST') {
      return handleDocumentAnalyze(request, env);
    }

    if (path === '/api/health' && request.method === 'GET') {
      return handleHealth(request, env);
    }

    if (path === '/api/citation' && request.method === 'GET') {
      const uid = url.searchParams.get('uid');
      if (!uid) return json({ error: 'uid query param required' }, 400);
      try {
        const retriever = createRetriever(env, url);
        const citation = typeof (retriever as any).resolveCitation === 'function'
          ? await (retriever as any).resolveCitation(uid)
          : citationForSection({ lawCode: uid.split(':')[0], sectionNum: uid.split(':')[1] || '' });
        return json({ ok: true, uid, citation });
      } catch (e) {
        return json({ error: e instanceof Error ? e.message : 'Citation resolution failed' }, 502);
      }
    }

    // Fallback to assets (Astro static site)
    try {
      return await env.ASSETS.fetch(request);
    } catch (e) {
      return json({ error: 'Asset fetch failed', detail: e instanceof Error ? e.message : String(e) }, 502);
    }
  },
};
