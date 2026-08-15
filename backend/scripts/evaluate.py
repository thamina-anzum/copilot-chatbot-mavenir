"""Run evaluation/questions.json through the full graph."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.core.logging import configure_logging  # noqa: E402
from app.services.evaluation_service import evaluate_questions  # noqa: E402

configure_logging()


def main() -> None:
    summary = evaluate_questions()
    out_dir = REPO / "evaluation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"eval_{stamp}.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    print(f"\nFull results: {path}")
    print("\nPer-question:")
    for row in summary["results"]:
        flag = "OK" if row["abstention_correct"] else "MISS"
        print(
            f"  [{flag}] {row['id']} expected={row['expected_status']} "
            f"got={row['actual_status']} {row['latency_ms']}ms"
        )


if __name__ == "__main__":
    main()
