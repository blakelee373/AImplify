const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path);
  },

  post<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  patch<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  delete<T>(path: string): Promise<T> {
    return request<T>(path, { method: "DELETE" });
  },
};

// --- Typed API functions ---

export interface ConversationSummary {
  id: string;
  title: string | null;
  workflow_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  workflow_id: string | null;
  created_at: string;
  messages: MessageData[];
}

export interface ChatResult {
  response: string;
  conversation_id: string;
  message_id: string;
  workflow_saved: boolean;
}

export function fetchConversations() {
  return api.get<ConversationSummary[]>("/api/conversations");
}

export function fetchConversation(id: string) {
  return api.get<ConversationDetail>(`/api/conversations/${id}`);
}

export function sendMessage(message: string, conversationId: string | null) {
  return api.post<ChatResult>("/api/chat", {
    message,
    conversation_id: conversationId,
  });
}
