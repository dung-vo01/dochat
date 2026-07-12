import { type KeyboardEvent } from "react";
import styles from "./index.module.scss";
import { useChat } from "@/hooks/useChat";
import { useUpload } from "@/hooks/useUpload";

const Chat = () => {
  const { messages, input, setInput, isStreaming, sendMessage } = useChat();
  const { uploadStatus, uploadStatusText, handleFileChange } = useUpload();

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>Dochat</h1>

      {/* Upload */}
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

      {/* Messages */}
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
        {isStreaming && (
          <div className={styles.typingIndicator}>Assistant is typing...</div>
        )}
      </div>

      {/* Input */}
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
        <button
          className={styles.sendButton}
          onClick={() => void sendMessage()}
          disabled={isStreaming || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
};

export default Chat;
