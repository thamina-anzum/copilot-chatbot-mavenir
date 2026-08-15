"""Evaluation runner used by scripts/evaluate.py."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from app.rag.graph import run_graph
from app.rag.prompts import ABSTAIN_TEXT

REPO_ROOT = Path(__file__).resolve().parents[3]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return float(ordered[f])
    return float(ordered[f] + (ordered[c] - ordered[f]) * (k - f))


def evaluate_questions(path: Path | None = None) -> dict[str, Any]:
    path = path or (REPO_ROOT / "evaluation" / "questions.json")
    questions = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []

    for item in questions:
        qid = item["id"]
        query = item["query"]
        expected_status = item["expected_status"]  # grounded | abstained
        t0 = time.perf_counter()
        state = run_graph(query, [])
        ms = (time.perf_counter() - t0) * 1000
        latencies.append(ms)
        status = state.get("status")
        citations = state.get("citations") or []
        expected_spec = item.get("expected_specification")
        expected_section = item.get("expected_section")
        cite_ok: str | bool
        if expected_spec:
            cite_ok = any(c.get("specification") == expected_spec for c in citations)
            if expected_section:
                cite_ok = any(
                    c.get("specification") == expected_spec and c.get("section") == expected_section
                    for c in citations
                )
        else:
            cite_ok = "manual review needed" if status == "grounded" else True

        verification = state.get("verification_result") or {}
        groundedness = verification.get("entailment", {}).get("all_supported")
        if groundedness is None:
            groundedness = "manual review needed"

        rows.append(
            {
                "id": qid,
                "query": query,
                "category": item.get("category"),
                "expected_status": expected_status,
                "actual_status": status,
                "abstention_correct": status == expected_status,
                "citation_accuracy": cite_ok,
                "groundedness": groundedness,
                "latency_ms": round(ms, 1),
                "classification": state.get("classification"),
                "evidence_strength": state.get("evidence_strength"),
                "answer_preview": (state.get("answer") or "")[:240],
            }
        )

    abstention_acc = (
        sum(1 for r in rows if r["abstention_correct"]) / len(rows) if rows else 0.0
    )
    measurable_cite = [r["citation_accuracy"] for r in rows if isinstance(r["citation_accuracy"], bool)]
    cite_acc = sum(1 for x in measurable_cite if x) / len(measurable_cite) if measurable_cite else "manual review needed"
    measurable_g = [r["groundedness"] for r in rows if isinstance(r["groundedness"], bool)]
    ground_acc = sum(1 for x in measurable_g if x) / len(measurable_g) if measurable_g else "manual review needed"

    summary = {
        "n": len(rows),
        "abstention_accuracy": round(abstention_acc, 3),
        "citation_accuracy": cite_acc if isinstance(cite_acc, str) else round(cite_acc, 3),
        "groundedness_proxy": ground_acc if isinstance(ground_acc, str) else round(ground_acc, 3),
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else 0,
        "p95_latency_ms": round(percentile(latencies, 0.95), 1),
        "results": rows,
    }
    return summary
