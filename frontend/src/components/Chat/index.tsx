import { type KeyboardEvent } from "react";
import styles from "./index.module.scss";
import { useChat } from "@/hooks/useChat";
import { useUpload } from "@/hooks/useUpload";

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

  const { uploadStatus, uploadStatusText, handleFileChange } = useUpload();

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
            onChange={handleFileChange}
            disabled={uploadStatus === "uploading"}
          />
        </label>
        <span className={`${styles.uploadStatus} ${styles[uploadStatus]}`}>
          {uploadStatusText()}
        </span>
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
      </div>

      <div className={styles.inputRow}>
        <textarea
          className={styles.textarea}
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            uploadStatus === "done"
              ? "Ask something about the document..."
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
