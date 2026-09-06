// Shapes mirror api/app.py's JSON responses exactly.

export interface Citation {
  chunk_id: string;
  text: string;
  score: number;
  metadata: {
    doc_id: string;
    source_file: string;
    title: string;
    platform: string;
    page: number | null;
  };
  cited: boolean;
}

export interface AnswerResponse {
  conversation_id: string;
  message_id: string;
  question: string;
  answer_text: string;
  source_chunk_ids: string[];
  citations: Citation[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}
