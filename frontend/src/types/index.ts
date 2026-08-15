export type EvidenceStrength = "high" | "medium" | "low";
export type AnswerStatus = "grounded" | "abstained" | "error";

export interface Citation {
  specification: string;
  section: string;
  page: number;
  supporting_chunk_id: string;
  excerpt?: string | null;
}

export interface RetrievedChunk {
  chunk_id: string;
  specification: string;
  section: string;
  section_title: string;
  page: number;
  chunk_type: string;
  text: string;
  rerank_score?: number | null;
  rrf_score?: number | null;
  vector_score?: number | null;
  bm25_score?: number | null;
}

export interface ChatMessageResponse {
  conversation_id: string;
  answer: string;
  status: AnswerStatus;
  evidence_strength: EvidenceStrength;
  citations: Citation[];
  retrieved_chunks: RetrievedChunk[];
  classification?: string | null;
  latency_ms: number;
  evidence_reasoning?: string | null;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  response?: ChatMessageResponse;
}

export interface IngestedDocument {
  specification: string;
  title: string;
  release: string;
  version: string;
  source_filename: string;
  page_count: number;
  chunk_count: number;
}
