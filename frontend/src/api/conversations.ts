import { Conversation, ConversationDetails } from "@/types";

const BASE_URL = import.meta.env.VITE_API_URL;

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BASE_URL}/api/conversations`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function fetchConversation(
  conversation_id: number,
): Promise<ConversationDetails> {
  const res = await fetch(`${BASE_URL}/api/conversations/${conversation_id}`);
  if (!res.ok) throw new Error("Failed to fetch conversation");
  return res.json();
}

export async function createConversation(): Promise<Conversation> {
  const res = await fetch(`${BASE_URL}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "New chat" }),
  });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function deleteConversation(id: number): Promise<void> {
  await fetch(`${BASE_URL}/api/conversations/${id}`, { method: "DELETE" });
}
