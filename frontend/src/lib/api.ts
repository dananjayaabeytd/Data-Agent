export type Role = "user" | "assistant";

export interface ChatMessage {
  role: Role;
  content: string;
}

export interface SessionSummary {
  session_id: string;
  title: string;
  updated_at: string;
  message_count: number;
}

export interface Session {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface SendMessageResult {
  session: Session;
  answer: string;
}

function errorMessage(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return `Request failed (${status})`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessage(data, response.status));
  return data as T;
}

export const api = {
  listSessions: () => request<SessionSummary[]>("sessions"),
  getSession: (id: string) => request<Session>(`sessions/${encodeURIComponent(id)}`),
  createSession: (title: string) =>
    request<Session>("sessions", { method: "POST", body: JSON.stringify({ title }) }),
  renameSession: (id: string, title: string) =>
    request<Session>(`sessions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  clearSession: (id: string) =>
    request<Session>(`sessions/${encodeURIComponent(id)}/messages`, { method: "DELETE" }),
  deleteSession: (id: string) =>
    request<void>(`sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
  deleteSessions: (ids: string[]) =>
    request<{ deleted: number }>("sessions/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ session_ids: ids }),
    }),
  deleteAllSessions: () => request<{ deleted: number }>("sessions", { method: "DELETE" }),
  sendMessage: (id: string, message: string) =>
    request<SendMessageResult>(`sessions/${encodeURIComponent(id)}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};
