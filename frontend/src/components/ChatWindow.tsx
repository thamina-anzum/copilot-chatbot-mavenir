import { useEffect, useRef } from "react";
import type { ChatTurn } from "../types";
import { LoadingIndicator } from "./LoadingIndicator";
import { MessageBubble } from "./MessageBubble";

export function ChatWindow({
  turns,
  loading,
}: {
  turns: ChatTurn[];
  loading: boolean;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  return (
    <div className="chat">
      {turns.length === 0 && (
        <div className="bubble assistant">
          Ask a question grounded in TS 23.501, 23.502, 24.501, or 38.300.
          If the specs do not contain enough evidence, I will abstain rather than guess.
        </div>
      )}
      {turns.map((turn, i) => (
        <MessageBubble key={i} turn={turn} />
      ))}
      {loading && <LoadingIndicator />}
      <div ref={endRef} />
    </div>
  );
}
