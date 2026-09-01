import { useEffect, useRef, type KeyboardEvent } from "react";
import styles from "./index.module.scss";
import { useChat } from "@/hooks/useChat";
import { useDocuments } from "@/hooks/useDocuments";

interface Props {
  conversationId: number | null;
  handleFirstMessage: () => Promise<void>;
}

const Chat = ({ conversationId, handleFirstMessage }: Props) => {
  const {
    messages,
    input,
    setInput,
    isStreaming,
    toolLabel,
    sendMessage,
    cancel,
  } = useChat(conversationId, handleFirstMessage);

  const { documents, isUploading, error, handleFileChange, handleDelete } =
    useDocuments(conversationId);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "auto" });
  }, [messages, isStreaming, toolLabel]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  if (!conversationId) {
    return (
      <div className={styles.empty}>
        <p>Select a conversation or start a new one.</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.uploadArea}>
        <label className={styles.uploadLabel}>
          Upload PDF
          <input
            type="file"
            accept=".pdf"
            className={styles.uploadInput}
            onChange={(e) => void handleFileChange(e)}
            disabled={isUploading}
          />
        </label>

        {documents.length === 0 && !isUploading && (
          <span className={styles.uploadStatus}>
            No documents uploaded - chatting without context
          </span>
        )}

        {documents.length > 0 && (
          <ul className={styles.documentList}>
            {documents.map((doc) => (
              <li key={doc.id} className={styles.documentItem}>
                <span className={styles.documentName}>{doc.filename}</span>
                <button
                  className={styles.documentDeleteButton}
                  onClick={() => void handleDelete(doc.id)}
                  title="Remove document"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}

        {isUploading && (
          <span className={`${styles.uploadStatus} ${styles.uploading}`}>
            Uploading...
          </span>
        )}
        {error && (
          <span className={`${styles.uploadStatus} ${styles.error}`}>
            {error}
          </span>
        )}
      </div>

      <div className={styles.messageList}>
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`${styles.message} ${
              msg.role === "user" ? styles.user : styles.assistant
            }`}
          >
            <div className={styles.messageRole}>{msg.role}</div>
            <div className={styles.messageContent}>{msg.content}</div>
          </div>
        ))}

        {/* Show tool label or typing indicator */}
        {isStreaming && (
          <div
            className={
              toolLabel ? styles.toolIndicator : styles.typingIndicator
            }
          >
            {toolLabel ?? "Assistant is typing..."}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className={styles.inputRow}>
        <textarea
          className={styles.textarea}
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            documents.length > 0
              ? "Ask something about the documents..."
              : "Type a message..."
          }
          disabled={isStreaming}
        />
        {isStreaming ? (
          <button className={styles.stopButton} onClick={cancel}>
            Stop
          </button>
        ) : (
          <button
            className={styles.sendButton}
            onClick={() => void sendMessage()}
            disabled={!input.trim()}
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
};

export default Chat;
