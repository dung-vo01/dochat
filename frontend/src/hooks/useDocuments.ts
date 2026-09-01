import { useEffect, useState } from "react";
import { deleteDocument, fetchDocuments, uploadDocument } from "@/api/documents";
import type { Document } from "@/types";

export function useDocuments(conversationId: number | null) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDocuments([]);
    setError(null);

    if (conversationId) {
      void fetchDocuments(conversationId).then(setDocuments);
    }
  }, [conversationId]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file || !conversationId) return;

    setIsUploading(true);
    setError(null);

    try {
      const doc = await uploadDocument(conversationId, file);
      setDocuments((prev) => [...prev, doc]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (documentId: number) => {
    try {
      await deleteDocument(documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return { documents, isUploading, error, handleFileChange, handleDelete };
}
