import { FormEvent, useEffect, useState } from "react";
import { ChatWindow } from "../components/ChatWindow";
import { fetchDocuments, sendMessage } from "../services/api";
import type { ChatTurn, IngestedDocument } from "../types";

export function ChatPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [docs, setDocs] = useState<IngestedDocument[]>([]);

  useEffect(() => {
    fetchDocuments()
      .then(setDocs)
      .catch(() => setDocs([]));
  }, []);

  async function ask() {
    const text = query.trim();
    if (!text || loading) return;
    setError(null);
    setQuery("");
    setTurns((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    try {
      const response = await sendMessage(text, conversationId);
      setConversationId(response.conversation_id);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, response }]);
    } catch {
      setError("The request failed. Check that the API is running and documents are ingested.");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await ask();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          3GPP
          <span>Standards Copilot</span>
        </div>
        <div>
          <h2>Indexed specifications</h2>
          <ul className="doc-list">
            {docs.length === 0 && <li>No documents yet. Run ingestion first.</li>}
            {docs.map((d) => (
              <li key={d.specification}>
                <strong>TS {d.specification}</strong>
                Rel-{d.release} / {d.version}
                <div>{d.chunk_count} chunks</div>
              </li>
            ))}
          </ul>
        </div>
        <p style={{ fontSize: 13, lineHeight: 1.45, color: "#c5d0da" }}>
          Answers are generated only from retrieved 3GPP passages. If evidence is weak, the
          copilot abstains.
        </p>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <strong>Evidence-grounded Q&amp;A</strong>
            <p>TS 23.501 · 23.502 · 24.501 · 38.300 (Release 18)</p>
          </div>
        </header>
        <ChatWindow turns={turns} loading={loading} />
        {error && <div className="error">{error}</div>}
        <form className="composer" onSubmit={onSubmit}>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about AMF, N2, registration, NAS, NG-RAN…"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void ask();
              }
            }}
          />
          <button type="submit" disabled={loading || !query.trim()}>
            Ask
          </button>
        </form>
      </main>
    </div>
  );
}
