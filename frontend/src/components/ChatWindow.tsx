"use client";

import { useState, useRef, useEffect } from "react";
import { MessageBubble } from "./MessageBubble";
import { api } from "@/lib/api";

interface MessageMetadata {
  message_type?: string;
  workflow_draft?: {
    name: string;
    description: string;
    trigger_type: string;
    trigger_config: Record<string, string>;
    steps: Array<{
      step_order: number;
      action_type: string;
      description: string;
    }>;
  };
  workflow_id?: number;
}

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  metadata?: MessageMetadata | null;
}

interface ChatResponse {
  conversation_id: number;
  message: Message;
}

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    // Optimistically add user message
    const userMsg: Message = { id: Date.now(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const data = await api.post<ChatResponse>("/api/chat", {
        message: text,
        conversation_id: conversationId,
      });

      setConversationId(data.conversation_id);
      setMessages((prev) => [...prev, data.message]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-stone-400 text-sm">
            Start by describing a task you do repeatedly.
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            role={msg.role}
            content={msg.content}
            metadata={msg.metadata}
          />
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-stone-100 rounded-2xl px-4 py-3 text-sm text-stone-400 rounded-bl-md">
              Thinking...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-stone-200 px-6 py-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-3"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe a task you'd like to automate..."
            className="flex-1 rounded-lg border border-stone-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
