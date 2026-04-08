"use client";

import { useState, useCallback } from "react";
import { ChatWindow } from "@/components/ChatWindow";
import { ConversationList } from "@/components/ConversationList";

export default function ChatPage() {
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleConversationCreated = useCallback((id: number) => {
    setActiveConversationId(id);
    setRefreshKey((k) => k + 1);
  }, []);

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null);
  }, []);

  const handleSelectConversation = useCallback((id: number) => {
    setActiveConversationId(id);
  }, []);

  return (
    <div className="flex h-full">
      {/* Conversation sidebar */}
      <div className="w-72 shrink-0">
        <ConversationList
          activeId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          refreshKey={refreshKey}
        />
      </div>

      {/* Chat area */}
      <div className="flex flex-col flex-1 min-w-0">
        <div className="border-b border-stone-200 px-6 py-4">
          <h1 className="text-xl font-semibold text-stone-900">Chat</h1>
          <p className="text-sm text-stone-500">
            Tell me about a task you or your staff do repeatedly
          </p>
        </div>
        <ChatWindow
          conversationId={activeConversationId}
          onConversationCreated={handleConversationCreated}
        />
      </div>
    </div>
  );
}
