import { useState, useRef, useEffect } from "react";
import { streamChat } from "@/api/chat";
import type { ChatMessage } from "@/types";
import { fetchConversation } from "@/api/conversations";

const TOOL_LABELS: Record<string, string> = {
  get_current_datetime: "Checking date & time...",
  web_search: "Searching the web...",
  clear_chat_history: "Clearing history...",
};

export function useChat(
  conversationId: number | null,
  onFirstMessage?: () => Promise<void>,
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [toolLabel, setToolLabel] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    updateChat();
  }, [conversationId]);

  const setHistory = (msgs: ChatMessage[]) => setMessages(msgs);

  const updateChat = async () => {
    if (conversationId) {
      const data = await fetchConversation(conversationId);
      setMessages(data.messages);
    }
  };

  const appendChunk = (text: string) => {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = { ...last, content: last.content + text };
      return updated;
    });
  };

  const sendMessage = async (): Promise<void> => {
    if (!input.trim() || isStreaming || !conversationId) return;

    const isFirstMessage = messages.length === 0;
    const userMessage: ChatMessage = { role: "user", content: input };

    setMessages((prev) => [
      ...prev,
      userMessage,
      { role: "assistant", content: "" },
    ]);
    setInput("");
    setIsStreaming(true);
    setToolLabel(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        conversationId,
        input,
        appendChunk,
        (toolName) => setToolLabel(TOOL_LABELS[toolName] ?? "Using a tool..."),
        controller.signal,
      );
    } catch (err) {
      if (err instanceof Error && err.name !== "AbortError") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${err.message}` },
        ]);
      }
    } finally {
      setIsStreaming(false);
      setToolLabel(null);
      if (isFirstMessage) await onFirstMessage?.();
    }
  };

  const cancel = () => abortRef.current?.abort();

  return {
    messages,
    input,
    setInput,
    isStreaming,
    toolLabel,
    sendMessage,
    cancel,
    setHistory,
  };
}
