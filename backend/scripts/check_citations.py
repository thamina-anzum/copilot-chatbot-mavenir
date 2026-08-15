"""Print citation labels next to the real chunk excerpt for manual review."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.logging import configure_logging
from app.rag.graph import run_graph

configure_logging()

QUESTIONS = [
    "What is the role of the AMF?",
    "What is the N2 interface used for?",
    "What is the purpose of the UPF?",
    "What is Ericsson's stock price today?",
]


def main() -> None:
    for q in QUESTIONS:
        print("=" * 78)
        print("Q:", q)
        state = run_graph(q, [])
        print(
            "status:",
            state.get("status"),
            "class:",
            state.get("classification"),
            "strength:",
            state.get("evidence_strength"),
        )
        print("answer:", (state.get("answer") or "")[:400])
        print("hallucinated_ids:", state.get("hallucinated_chunk_ids"))
        vr = state.get("verification_result") or {}
        print("verify_ok:", vr.get("ok"), "failures:", vr.get("structural_failures"))
        print("CITATIONS:")
        for i, c in enumerate(state.get("citations") or [], 1):
            excerpt = (c.get("excerpt") or "").replace("\n", " ")[:240]
            print(
                f"  [{i}] TS {c.get('specification')} §{c.get('section')} "
                f"p.{c.get('page')} chunk_id={c.get('supporting_chunk_id')}"
            )
            print(f"      excerpt: {excerpt}")
        print()


if __name__ == "__main__":
    main()
