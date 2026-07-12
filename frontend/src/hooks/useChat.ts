import { useState, useRef } from "react";
import { streamChat } from "@/api/chat";
import type { ChatMessage } from "@/types";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const appendChunk = (text: string) => {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = { ...last, content: last.content + text };
      return updated;
    });
  };

  const sendMessage = async (): Promise<void> => {
    if (!input.trim() || isStreaming) return;

    const userMessage: ChatMessage = { role: "user", content: input };
    const newMessages: ChatMessage[] = [...messages, userMessage];

    setMessages([...newMessages, { role: "assistant", content: "" }]);
    setInput("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(newMessages, appendChunk, controller.signal);
    } catch (err) {
      if (err instanceof Error && err.name !== "AbortError") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Error: failed to get response." },
        ]);
      }
    } finally {
      setIsStreaming(false);
    }
  };

  const cancel = () => abortRef.current?.abort();

  return { messages, input, setInput, isStreaming, sendMessage, cancel };
}
