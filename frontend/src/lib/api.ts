const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, data: unknown) =>
    request<T>(path, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  patch: <T>(path: string, data: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: <T>(path: string) =>
    request<T>(path, { method: "DELETE" }),
};
