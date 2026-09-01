import type { Document } from "@/types";
import { extractErrorDetail } from "@/api/http";

const BASE_URL = import.meta.env.VITE_API_URL;

export async function fetchDocuments(
  conversationId: number,
): Promise<Document[]> {
  const res = await fetch(
    `${BASE_URL}/api/conversations/${conversationId}/documents`,
  );
  if (!res.ok) throw new Error(await extractErrorDetail(res));
  return res.json();
}

export async function uploadDocument(
  conversationId: number,
  file: File,
): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(
    `${BASE_URL}/api/conversations/${conversationId}/documents`,
    { method: "POST", body: formData },
  );

  if (!res.ok) throw new Error(await extractErrorDetail(res));
  return res.json();
}

export async function deleteDocument(documentId: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/documents/${documentId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await extractErrorDetail(res));
}
