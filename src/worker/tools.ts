/**
 * Provider-independent tool contract for California legislative research.
 * These definitions own tool semantics – model providers expose them via native function calling,
 * but the application owns validation, limits, provenance, and state transitions.
 */

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, { type: string; description: string; enum?: string[] }>;
    required: string[];
  };
}

export const RESEARCH_TOOLS: ToolDefinition[] = [
  {
    name: 'search',
    description:
      'Search California legislative corpus for provisions responsive to a natural-language query. Use for discovery; prefer get_section once an authority is identified. Supports code-scoped search and semantic query rewriting – not just keyword match.',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Natural-language query or concept – will be semantically expanded, not just keyword matched' },
        code: { type: 'string', description: 'Optional code filter: BPC, CIV, CCP, COM, CORP, EDC, ELEC, EVID, FAM, FIN, FGC, FAC, GOV, HNC, HSC, INS, LAB, MVC, PEN, PROB, PCC, PRC, PUC, RTC, SHC, UIC, VEH, WAT, WIC, CONS' },
        limit: { type: 'number', description: 'Max results 1-30' },
        exactUid: { type: 'string', description: 'Optional exact UID like GOV:7921.000 to boost' },
      },
      required: ['query'],
    },
  },
  {
    name: 'get_section',
    description: 'Retrieve exact statutory section by UID (e.g., GOV:7921.000) or code+section. Returns authoritative text, title, history, citation, path. Use when citation is known.',
    parameters: {
      type: 'object',
      properties: {
        uid: { type: 'string', description: 'Section UID like GOV:7921.000 or FAM:3044' },
        versionId: { type: 'string', description: 'Optional corpus version ID for historical text' },
      },
      required: ['uid'],
    },
  },
  {
    name: 'get_definition',
    description: 'Retrieve operative statutory definitions for a term. Searches for "X means" patterns across codes. Critical for interpretation – statutory definition controls.',
    parameters: {
      type: 'object',
      properties: {
        term: { type: 'string', description: 'Term to define, e.g., custody, public records' },
        scope: { type: 'string', description: 'Optional code scope to limit definition search' },
      },
      required: ['term'],
    },
  },
  {
    name: 'get_relationships',
    description:
      'Traverse explicit statutory relationships (references, exceptions, dependencies) from a section. Bounded by depth and node limits. Prefer explicit relationships over semantic guesses.',
    parameters: {
      type: 'object',
      properties: {
        uid: { type: 'string', description: 'Source UID' },
        direction: { type: 'string', enum: ['outbound', 'inbound', 'both'], description: 'Traversal direction' },
        depth: { type: 'number', description: 'Depth 1-3, default 2' },
        limit: { type: 'number', description: 'Max edges 1-100' },
      },
      required: ['uid'],
    },
  },
  {
    name: 'get_history',
    description: 'Retrieve legislative history events for a section – amendments, effective dates, bill/chapter sources. Required for temporal questions. Current text alone is not historical evidence.',
    parameters: {
      type: 'object',
      properties: {
        uid: { type: 'string', description: 'Section UID' },
        versionId: { type: 'string', description: 'Optional version filter' },
        from: { type: 'string', description: 'ISO date lower bound' },
        to: { type: 'string', description: 'ISO date upper bound' },
        limit: { type: 'number', description: 'Max events 1-200' },
      },
      required: ['uid'],
    },
  },
  {
    name: 'compare',
    description: 'Compare two sections side-by-side – textual similarities, differences, shared terms, length. Use for compare intent after retrieving each authority independently.',
    parameters: {
      type: 'object',
      properties: {
        leftUid: { type: 'string', description: 'Left section UID' },
        rightUid: { type: 'string', description: 'Right section UID' },
      },
      required: ['leftUid', 'rightUid'],
    },
  },
  {
    name: 'analyze_document',
    description:
      'Analyze a user-provided document against the legislative corpus. Extracts cited sections and propositions, then retrieves responsive authorities. For document analysis capability.',
    parameters: {
      type: 'object',
      properties: {
        document: { type: 'string', description: 'Document text to analyze, up to 20000 chars' },
        propositions: { type: 'string', description: 'Optional JSON array of propositions to check' },
      },
      required: ['document'],
    },
  },
  {
    name: 'resolve_citation',
    description: 'Resolve a UID to canonical LegInfo citation object with label and URL. Ensures human-verifiable source links.',
    parameters: {
      type: 'object',
      properties: {
        uid: { type: 'string', description: 'Section UID' },
      },
      required: ['uid'],
    },
  },
  {
    name: 'build_evidence_graph',
    description: 'Build evidence graph from multiple UIDs – traverses relationships to map connections. Use for multi-authority synthesis, compare, investigate intents.',
    parameters: {
      type: 'object',
      properties: {
        uids: { type: 'string', description: 'JSON array of UIDs, e.g., ["FAM:3044","GOV:7921.000"]' },
        depth: { type: 'number', description: 'Traversal depth 1-3' },
        limit: { type: 'number', description: 'Max edges 1-100' },
      },
      required: ['uids'],
    },
  },
];

export function toolDefinitionsForProvider(provider: 'openai' | 'anthropic' | 'cloudflare' | 'generic' = 'generic') {
  // For now return generic; provider adapters can transform
  return RESEARCH_TOOLS;
}
