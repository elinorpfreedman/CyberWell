import type { AnswerResponse } from "./types";

// Overridable at build time via VITE_API_BASE_URL; defaults to the local Flask dev server.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

async function asJson(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error ?? `Request failed with status ${response.status}`);
  }
  return body;
}

export async function createConversation(): Promise<string> {
  const response = await fetch(`${API_BASE}/conversations`, { method: "POST" });
  const body = await asJson(response);
  return body.conversation_id;
}

export async function askQuestion(conversationId: string, question: string): Promise<AnswerResponse> {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return asJson(response);
}
