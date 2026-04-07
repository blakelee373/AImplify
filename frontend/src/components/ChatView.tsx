"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Sidebar } from "@/components/Sidebar";
import { MessageBubble } from "@/components/MessageBubble";
import { ChatInput } from "@/components/ChatInput";
import { TypingIndicator } from "@/components/TypingIndicator";
import { SuggestionChips } from "@/components/SuggestionChips";
import { Toast } from "@/components/Toast";
import {
  fetchConversations,
  fetchConversation,
  sendMessage,
  type ConversationSummary,
  type MessageData,
} from "@/lib/api";

export function ChatView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const conversationId = searchParams.get("c");

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toastVisible, setToastVisible] = useState(false);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeIdRef = useRef(conversationId);

  // Keep ref in sync
  useEffect(() => {
    activeIdRef.current = conversationId;
  }, [conversationId]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Load conversation list on mount
  useEffect(() => {
    fetchConversations()
      .then(setConversations)
      .catch(() => {});
  }, []);

  // Load conversation when ID changes
  useEffect(() => {
    if (conversationId) {
      fetchConversation(conversationId)
        .then((conv) => {
          setMessages(conv.messages);
          setConversationTitle(conv.title);
        })
        .catch(() => {});
    } else {
      setMessages([]);
      setConversationTitle(null);
    }
  }, [conversationId]);

  const handleDismissToast = useCallback(() => setToastVisible(false), []);

  async function handleSend() {
    const text = input.trim();
    if (!text || isLoading) return;

    setInput("");

    // Optimistically add user message
    const tempUserMsg: MessageData = {
      id: "temp-" + Date.now(),
      role: "user",
      content: text,
      metadata: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsLoading(true);

    try {
      const result = await sendMessage(text, conversationId);

      // Add assistant message
      const assistantMsg: MessageData = {
        id: result.message_id,
        role: "assistant",
        content: result.response,
        metadata: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // If new conversation, update URL and sidebar
      if (!conversationId) {
        router.push(`/chat?c=${result.conversation_id}`, { scroll: false });
        // Refresh conversation list to pick up new title
        setTimeout(() => {
          fetchConversations()
            .then(setConversations)
            .catch(() => {});
        }, 2000);
      }

      // Show toast if workflow was saved
      if (result.workflow_saved) {
        setToastVisible(true);
      }
    } catch {
      const errorMsg: MessageData = {
        id: "error-" + Date.now(),
        role: "assistant",
        content: "Sorry, something went wrong. Please try again.",
        metadata: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleSelectConversation(id: string) {
    router.push(`/chat?c=${id}`, { scroll: false });
  }

  function handleNewConversation() {
    router.push("/chat", { scroll: false });
    setMessages([]);
    setConversationTitle(null);
  }

  function handleSuggestionClick(text: string) {
    setInput(text);
    // Auto-send after a brief moment so user sees what was selected
    setTimeout(() => {
      setInput("");
      const tempUserMsg: MessageData = {
        id: "temp-" + Date.now(),
        role: "user",
        content: text,
        metadata: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);
      setIsLoading(true);

      sendMessage(text, null)
        .then((result) => {
          const assistantMsg: MessageData = {
            id: result.message_id,
            role: "assistant",
            content: result.response,
            metadata: null,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
          router.push(`/chat?c=${result.conversation_id}`, { scroll: false });
          setTimeout(() => {
            fetchConversations()
              .then(setConversations)
              .catch(() => {});
          }, 2000);
        })
        .catch(() => {
          setMessages((prev) => [
            ...prev,
            {
              id: "error-" + Date.now(),
              role: "assistant",
              content: "Sorry, something went wrong. Please try again.",
              metadata: null,
              created_at: new Date().toISOString(),
            },
          ]);
        })
        .finally(() => setIsLoading(false));
    }, 100);
  }

  const showWelcome = messages.length === 0 && !isLoading;

  return (
    <div className="flex h-full bg-background">
      <Sidebar
        conversations={conversations}
        activeId={conversationId}
        isOpen={sidebarOpen}
        onSelect={handleSelectConversation}
        onNew={handleNewConversation}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-surface shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden p-1.5 rounded-lg hover:bg-background transition-colors"
            aria-label="Open menu"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3 5h14M3 10h14M3 15h14" />
            </svg>
          </button>
          <h1 className="font-semibold text-foreground truncate">
            {conversationTitle || "New Conversation"}
          </h1>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto chat-scroll">
          {showWelcome ? (
            <SuggestionChips onSelect={handleSuggestionClick} />
          ) : (
            <div className="max-w-3xl mx-auto p-4 space-y-4">
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  timestamp={msg.created_at}
                />
              ))}
              {isLoading && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          disabled={isLoading}
        />
      </div>

      <Toast
        message="Task saved! You can view it in your dashboard."
        visible={toastVisible}
        onDismiss={handleDismissToast}
      />
    </div>
  );
}
