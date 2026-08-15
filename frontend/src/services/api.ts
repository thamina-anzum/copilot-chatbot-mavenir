import axios from "axios";
import type { ChatMessageResponse, IngestedDocument } from "../types";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  timeout: 180000,
});

export async function sendMessage(
  query: string,
  conversationId?: string | null,
): Promise<ChatMessageResponse> {
  const { data } = await client.post<ChatMessageResponse>("/chat/message", {
    query,
    conversation_id: conversationId || null,
  });
  return data;
}

export async function fetchDocuments(): Promise<IngestedDocument[]> {
  const { data } = await client.get<{ documents: IngestedDocument[] }>("/documents");
  return data.documents || [];
}

export async function fetchHealth(): Promise<{ status: string }> {
  const { data } = await client.get("/health");
  return data;
}
