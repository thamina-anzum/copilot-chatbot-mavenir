"""Manual retrieval inspection: print top-5 hybrid results for 5 real questions."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.logging import configure_logging  # noqa: E402
from app.retrieval.hybrid import hybrid_search  # noqa: E402
from app.retrieval.reranker import rerank  # noqa: E402

configure_logging()

QUESTIONS = [
    "What is the role of the AMF?",
    "What is the N2 interface?",
    "What is the purpose of the UPF?",
    "How does UE registration work?",
    "What is the difference between AMF and SMF?",
]


def main() -> None:
    for q in QUESTIONS:
        print("=" * 78)
        print(f"Q: {q}")
        hits = hybrid_search(q)
        ranked = rerank(q, hits)
        for i, h in enumerate(ranked[:5], start=1):
            preview = h.text.replace("\n", " ")[:220]
            print(
                f"\n  #{i} {h.specification} §{h.section} {h.section_title!r} p.{h.page} "
                f"type={h.chunk_type}\n"
                f"     vector={h.vector_score} bm25={h.bm25_score} rrf={h.rrf_score} "
                f"rerank={h.rerank_score}\n"
                f"     {preview}"
            )
        print()


if __name__ == "__main__":
    main()
