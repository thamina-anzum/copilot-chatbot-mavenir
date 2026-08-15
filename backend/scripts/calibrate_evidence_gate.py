"""Print reranker score distributions for answerable vs unanswerable queries.

Use the printed numbers to set EVIDENCE_THRESHOLD in .env — do not guess.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.logging import configure_logging  # noqa: E402
from app.retrieval.hybrid import hybrid_search  # noqa: E402
from app.retrieval.reranker import rerank  # noqa: E402

configure_logging()

ANSWERABLE = [
    "What is the role of the AMF in the 5G System?",
    "What is the N2 interface used for?",
    "What is the purpose of the UPF?",
    "How does UE registration work in 5GS?",
    "What is the difference between AMF and SMF?",
    "What is an S-NSSAI?",
    "What does the SMF do during PDU Session establishment?",
    "What is the NG-RAN?",
    "What is NAS used for in 5G?",
    "What is connection management in 5GS?",
]

UNANSWERABLE = [
    "What is Ericsson's stock price today?",
    "How do I bake sourdough bread?",
    "Who won the 2018 FIFA World Cup?",
    "What is the capital of Mongolia?",
    "Write a Python quicksort implementation.",
    "What is 3GPP TS 36.331 clause 5.3.5 in detail?",
    "What is the exact AMF CPU core count recommended by 3GPP?",
    "What is Qualcomm's 5G modem die size?",
    "How much does a gNB cost from Nokia?",
    "What is the 6G system architecture in TS 23.700?",
]

QUICK_ANSWERABLE = ANSWERABLE[:4]
QUICK_UNANSWERABLE = UNANSWERABLE[:4]


def _stats(label: str, tops: list[float]) -> None:
    print(f"\n{label} (n={len(tops)})")
    if not tops:
        print("  no scores")
        return
    ordered = sorted(tops)
    print(f"  min={ordered[0]:.3f}  p25={ordered[len(ordered)//4]:.3f}  "
          f"median={statistics.median(ordered):.3f}  "
          f"p75={ordered[(3*len(ordered))//4]:.3f}  max={ordered[-1]:.3f}  "
          f"mean={statistics.mean(ordered):.3f}")


def main() -> None:
    quick = "--quick" in sys.argv or "-q" in sys.argv
    answerable = QUICK_ANSWERABLE if quick else ANSWERABLE
    unanswerable = QUICK_UNANSWERABLE if quick else UNANSWERABLE
    ans_tops: list[float] = []
    una_tops: list[float] = []
    print("Running retrieval + rerank calibration%s...\n" % (" (quick subset)" if quick else ""))
    for group, queries, bucket in (
        ("ANSWERABLE", answerable, ans_tops),
        ("UNANSWERABLE", unanswerable, una_tops),
    ):
        print(f"=== {group} ===")
        for q in queries:
            hits = hybrid_search(q)
            ranked = rerank(q, hits)
            top = float(ranked[0].rerank_score) if ranked and ranked[0].rerank_score is not None else 0.0
            bucket.append(top)
            print(f"  {top:.3f}  {q}")

    _stats("Answerable top rerank scores", ans_tops)
    _stats("Unanswerable top rerank scores", una_tops)
    if ans_tops and una_tops:
        # Midpoint between unanswerable p75 and answerable p25 as a suggestion
        una_p75 = sorted(una_tops)[(3 * len(una_tops)) // 4]
        ans_p25 = sorted(ans_tops)[len(ans_tops) // 4]
        suggestion = (una_p75 + ans_p25) / 2
        print("\nSuggested EVIDENCE_THRESHOLD (midpoint unanswerable p75 / answerable p25): "
              f"{suggestion:.3f}")
        print("Inspect the lists above and pick a value that keeps answerable queries above "
              "the line and unanswerable queries below it. Prefer abstention if they overlap.")


if __name__ == "__main__":
    main()
