import { useState, useEffect } from "react";
import Chat from "@/components/Chat";
import Sidebar from "@/components/Sidebar";
import {
  fetchConversations,
  createConversation,
  deleteConversation,
} from "@/api/conversations";
import "./App.scss";
import { Conversation } from "./types";

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);

  useEffect(() => {
    void loadConversations();
  }, []);

  const loadConversations = async () => {
    const data = await fetchConversations();
    setConversations(data);
  };

  const handleNew = async () => {
    const conv = await createConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
  };

  const handleSelect = async (id: number) => {
    setActiveId(id);
  };

  const handleDelete = async (id: number) => {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) setActiveId(null);
  };

  const handleFirstMessage = async () => {
    await loadConversations();
  };

  return (
    <div className="layout">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onNew={() => void handleNew()}
        onSelect={handleSelect}
        onDelete={(id) => void handleDelete(id)}
      />
      <main className="main">
        <Chat
          conversationId={activeId}
          handleFirstMessage={handleFirstMessage}
        />
      </main>
    </div>
  );
}

export default App;
