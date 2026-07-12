export type Role = "user" | "assistant";

export interface ChatMessage {
  role: Role;
  content: string;
}

export interface StreamChunk {
  text: string;
}

export type UploadStatus = "idle" | "uploading" | "done" | "error";
