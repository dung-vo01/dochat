import { useState } from "react";
import { uploadPdf } from "@/api/chat";
import type { UploadStatus } from "@/types";

export function useUpload() {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");
  const [uploadedFileName, setUploadedFileName] = useState("");

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus("uploading");
    setUploadedFileName(file.name);

    try {
      await uploadPdf(file);
      setUploadStatus("done");
    } catch {
      setUploadStatus("error");
    }
  };

  const uploadStatusText = (): string => {
    switch (uploadStatus) {
      case "idle":
        return "No document uploaded - chatting without context";
      case "uploading":
        return `Uploading ${uploadedFileName}...`;
      case "done":
        return `✓ ${uploadedFileName} indexed - ask me anything about it`;
      case "error":
        return "Upload failed - please try again";
    }
  };

  return { uploadStatus, uploadStatusText, handleFileChange };
}
