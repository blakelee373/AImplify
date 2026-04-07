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

  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
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

// --- Types ---

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

export interface IntegrationInfo {
  name: string;
  display_name: string;
  description: string;
  auth_type: string;
  capabilities: string[];
  status: "connected" | "disconnected" | "error" | "expired";
}

export interface WorkflowTestResult {
  success: boolean;
  execution_id?: string;
  workflow_name?: string;
  dry_run: boolean;
  steps: WorkflowStepResult[];
  error?: string;
}

export interface WorkflowStepResult {
  step_order: number;
  action_type: string;
  description: string;
  success: boolean;
  dry_run?: boolean;
  preview?: string;
  error?: string;
}

// --- API functions ---

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

export function fetchIntegrations() {
  return api.get<IntegrationInfo[]>("/api/integrations");
}

export function connectGoogle() {
  return api.get<{ auth_url: string }>("/api/integrations/connect/google");
}

export function connectTwilio(creds: {
  account_sid: string;
  auth_token: string;
  phone_number: string;
}) {
  return api.post<{ status: string }>("/api/integrations/connect/twilio", creds);
}

export function disconnectIntegration(type: string) {
  return api.post<{ status: string }>(`/api/integrations/disconnect/${type}`);
}

export function testIntegration(type: string) {
  return api.get<{ integration: string; connected: boolean }>(
    `/api/integrations/status/${type}`
  );
}

export function testWorkflow(workflowId: string) {
  return api.post<WorkflowTestResult>(`/api/workflows/${workflowId}/test`);
}

export function activateWorkflow(workflowId: string) {
  return api.patch<unknown>(`/api/workflows/${workflowId}`, { status: "active" });
}
