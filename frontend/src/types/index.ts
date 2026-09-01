export type Role = "user" | "assistant";

export interface ChatMessage {
  role: Role;
  content: string;
}

// SSE event shapes from the backend
export interface TextChunk {
  text: string;
}

export interface ToolChunk {
  tool: string;
}

export type SSEChunk = TextChunk | ToolChunk | ErrorChunk;

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

export interface ErrorChunk {
  error: string;
}
