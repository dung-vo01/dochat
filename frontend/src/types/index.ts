export type Role = "user" | "assistant";

// An excerpt the answer cited, e.g. [1] -> policy.pdf, page 2
export interface Source {
  n: number;
  filename: string;
  page: number | null;
  snippet: string;
}

export interface ChatMessage {
  role: Role;
  content: string;
  sources?: Source[] | null;
}

// SSE event shapes from the backend
export interface TextChunk {
  text: string;
}

export interface ToolChunk {
  tool: string;
}

export interface ErrorChunk {
  error: string;
}

export interface SourcesChunk {
  sources: Source[];
}

// Everything retrieval put in the prompt; the UI only shows the cited subset.
export interface ContextChunk {
  context: unknown[];
}

export type SSEChunk =
  | TextChunk
  | ToolChunk
  | ErrorChunk
  | SourcesChunk
  | ContextChunk;

export interface Document {
  id: number;
  filename: string;
  chunk_count: number;
  created_at: string;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

export interface ConversationDetails {
  id: number;
  title: string;
  created_at: string;
  messages: ChatMessage[];
}

export interface Percentiles {
  p50: number | null;
  p95: number | null;
}

export interface MetricsSummary {
  window_hours: number;
  turns: number;
  error_rate: number | null;
  cancelled_rate: number | null;
  latency_ms: Percentiles;
  ttft_ms: Percentiles;
  avg_tokens: { prompt: number | null; completion: number | null };
  no_match_rate: number | null;
  avg_top_distance: number | null;
  tools: Record<string, number>;
  tools_blocked: number;
  history_trimmed_turns: number;
  series: {
    bucket: string;
    turns: number;
    errors: number;
    p50_latency_ms: number | null;
  }[];
  totals: { conversations: number; documents: number; indexed_chunks: number };
}

export interface RecentTurn {
  id: number;
  created_at: string;
  conversation_id: number;
  status: "ok" | "error" | "cancelled";
  latency_ms: number;
  ttft_ms: number | null;
  used_chunks: number;
  top_distance: number | null;
  tool: string | null;
  tool_blocked: boolean;
  tokens: number | null;
  error: string | null;
}
