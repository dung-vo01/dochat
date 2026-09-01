import type { SSEChunk } from "@/types";
import { extractErrorDetail } from "@/api/http";

const BASE_URL = import.meta.env.VITE_API_URL;

export async function streamChat(
  conversationId: number,
  message: string,
  onChunk: (text: string) => void,
  onToolCall: (toolName: string) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, message }),
    signal,
  });

  if (!res.ok) throw new Error(await extractErrorDetail(res));
  if (!res.body) throw new Error("Response had no body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") continue;

      const chunk: SSEChunk = JSON.parse(payload);

      if ("error" in chunk) {
        throw new Error(chunk.error);
      } else if ("tool" in chunk) {
        onToolCall(chunk.tool);
      } else if ("text" in chunk) {
        onChunk(chunk.text);
      }
    }
  }
}
