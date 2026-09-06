import { useEffect, useRef, useState } from "react";
import { askQuestion, createConversation } from "./api";
import type { ChatMessage, Citation } from "./types";
import "./App.css";

function SourceList({ citations }: { citations: Citation[] }) {
  const cited = citations.filter((c) => c.cited);
  const other = citations.filter((c) => !c.cited);

  if (citations.length === 0) return null;

  return (
    <div className="sources">
      <div className="sources-heading">Sources</div>
      {cited.map((c) => (
        <SourceCard key={c.chunk_id} citation={c} highlighted />
      ))}
      {other.length > 0 && (
        <details className="sources-other">
          <summary>{other.length} more retrieved but not cited</summary>
          {other.map((c) => (
            <SourceCard key={c.chunk_id} citation={c} />
          ))}
        </details>
      )}
    </div>
  );
}

function SourceCard({ citation, highlighted }: { citation: Citation; highlighted?: boolean }) {
  return (
    <div className={`source-card${highlighted ? " highlighted" : ""}`}>
      <div className="source-card-title">
        <span className="source-chunk-id">{citation.chunk_id}</span>
        <span className="source-platform">{citation.metadata.platform}</span>
        <span className="source-score">{citation.score.toFixed(3)}</span>
      </div>
      <div className="source-doc-title">{citation.metadata.title}</div>
      <div className="source-snippet">{citation.text.slice(0, 220)}...</div>
    </div>
  );
}

export default function App() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    createConversation()
      .then(setConversationId)
      .catch((err) => setError(`Could not reach the API: ${err.message}`));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || !conversationId || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setQuestion("");
    setLoading(true);
    setError(null);

    try {
      const result = await askQuestion(conversationId, trimmed);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.answer_text, citations: result.citations },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>CyberWell Policy Assistant</h1>
        <p>Ask about platform hate-speech and moderation policies. Answers are grounded in the indexed corpus only.</p>
      </header>

      <main className="chat">
        {messages.length === 0 && !loading && (
          <div className="empty-state">Ask a question to get started, e.g. "What is YouTube's hate speech policy?"</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-role">{m.role === "user" ? "You" : "Assistant"}</div>
            <div className="message-content">{m.content}</div>
            {m.role === "assistant" && m.citations && <SourceList citations={m.citations} />}
          </div>
        ))}
        {loading && <div className="message assistant loading">Thinking...</div>}
        {error && <div className="error-banner">{error}</div>}
        <div ref={bottomRef} />
      </main>

      <form className="composer" onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          disabled={!conversationId || loading}
        />
        <button type="submit" disabled={!conversationId || loading || !question.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
