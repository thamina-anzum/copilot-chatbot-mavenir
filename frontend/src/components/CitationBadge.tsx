import { useState } from "react";
import type { Citation, RetrievedChunk } from "../types";

export function CitationBadge({
  citation,
  chunks,
}: {
  citation: Citation;
  chunks: RetrievedChunk[];
}) {
  const [open, setOpen] = useState(false);
  const chunk = chunks.find((c) => c.chunk_id === citation.supporting_chunk_id);
  const excerpt = citation.excerpt || chunk?.text || "No passage stored for this citation.";

  return (
    <span>
      <button className="cite" type="button" onClick={() => setOpen((v) => !v)}>
        TS {citation.specification} §{citation.section} p.{citation.page}
        {open ? " ▴" : " ▾"}
      </button>
      {open && (
        <div className="evidence">
          <strong>View evidence</strong>
          {"\n"}
          {excerpt}
        </div>
      )}
    </span>
  );
}
