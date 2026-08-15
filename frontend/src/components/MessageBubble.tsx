import type { ChatTurn } from "../types";
import { AbstentionNotice } from "./AbstentionNotice";
import { CitationBadge } from "./CitationBadge";
import { EvidenceStrengthBadge } from "./EvidenceStrengthBadge";
import { MarkdownAnswer } from "./MarkdownAnswer";

export function MessageBubble({ turn }: { turn: ChatTurn }) {
  if (turn.role === "user") {
    return <div className="bubble user">{turn.content}</div>;
  }
  const response = turn.response;
  if (!response) {
    return <div className="bubble assistant">{turn.content}</div>;
  }
  if (response.status === "abstained") {
    return (
      <div>
        <AbstentionNotice>{response.answer}</AbstentionNotice>
        <div className="meta-row">
          <EvidenceStrengthBadge strength={response.evidence_strength} />
          <span className="badge">abstained</span>
          <span className="badge">{response.latency_ms} ms</span>
        </div>
      </div>
    );
  }
  return (
    <div className="bubble assistant">
      <MarkdownAnswer text={response.answer} />
      <div className="meta-row">
        <EvidenceStrengthBadge strength={response.evidence_strength} />
        <span className="badge">{response.status}</span>
        {response.classification && <span className="badge">{response.classification}</span>}
        <span className="badge">{response.latency_ms} ms</span>
        {response.citations.map((c, i) => (
          <CitationBadge key={`${c.specification}-${c.section}-${i}`} citation={c} chunks={response.retrieved_chunks} />
        ))}
      </div>
    </div>
  );
}
