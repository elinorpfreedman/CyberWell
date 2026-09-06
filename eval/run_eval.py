"""Run the test set through the RAG pipeline and report retrieval + answer metrics.

For each question in eval/test_set.jsonl:
  1. Retrieve top-5 chunks once (src/retrieval.py).
  2. Compute hit@3 and hit@5 from that same retrieval (hit@3 is just the first
     3 of the top-5 list, so no second API call is needed for the ablation).
  3. Generate an answer from the retrieved chunks (src/generation.py).
  4. Save everything -- including an empty "grade"/"grade_notes" field -- to
     eval/results/eval_results.jsonl for manual grading afterward.

Retrieval metric: hit rate@k -- for each answerable question, did at least
one of its expected_chunk_ids appear in the top-k retrieved chunks? This
measures whether retrieval surfaced a usable source at all; it does NOT
measure whether the generated answer actually used that source correctly,
ranked it first, or covered every expected chunk (recall@k or MRR would be
needed for that). "Absent" questions are excluded from hit rate (there is
nothing to hit), but we separately check whether the model correctly
abstained ("I could not find an answer...") on them.

Ablation: hit rate@3 vs. hit rate@5, to see how much retrieval quality
depends on how many chunks we bother to look at.

Usage: python eval/run_eval.py [--test-set eval/test_set.jsonl] [--k 5]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.generation import NOT_FOUND_MESSAGE, generate_answer
from src.retrieval import retrieve

TEST_SET_PATH = Path("eval/test_set.jsonl")
RESULTS_DIR = Path("eval/results")
DEFAULT_K = 5
ABLATION_K = 3


def hit_at_k(retrieved_chunks: list[dict], expected_chunk_ids: list[str], k: int) -> bool:
    top_k_ids = {c["chunk_id"] for c in retrieved_chunks[:k]}
    return any(chunk_id in top_k_ids for chunk_id in expected_chunk_ids)


def run(test_set_path: Path, results_dir: Path, k: int) -> None:
    questions = [json.loads(line) for line in test_set_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / "eval_results.jsonl"

    # Resume support: skip questions already answered in a previous (possibly
    # interrupted) run, and write each new result immediately so a failure
    # partway through (e.g. an API quota error) doesn't lose prior progress.
    already_done = {}
    previously_errored = []
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("error") is None:
                    already_done[row["question"]] = row
                else:
                    previously_errored.append(row)  # retry these, don't carry the failure forward
    results = list(already_done.values())

    with results_path.open("a", encoding="utf-8") as f:
        for i, q in enumerate(questions, start=1):
            if q["question"] in already_done:
                print(f"[{i}/{len(questions)}] (already done) {q['question'][:60]}")
                continue

            print(f"[{i}/{len(questions)}] {q['question'][:70]}")
            expected = q["expected_chunk_ids"]
            is_answerable = q["category"] != "absent"

            try:
                retrieved = retrieve(q["question"], k=max(k, ABLATION_K))
                gen = generate_answer(q["question"], retrieved[:k])
                time.sleep(3)  # stay comfortably under free-tier requests-per-minute caps
                row = {
                    "question": q["question"],
                    "category": q["category"],
                    "reference_answer": q["reference_answer"],
                    "expected_chunk_ids": expected,
                    "retrieved_chunk_ids": [c["chunk_id"] for c in retrieved[:k]],
                    "hit_at_3": hit_at_k(retrieved, expected, ABLATION_K) if is_answerable else None,
                    "hit_at_5": hit_at_k(retrieved, expected, DEFAULT_K) if is_answerable else None,
                    "cited_chunk_ids": gen["source_chunk_ids"],
                    "answer_text": gen["answer_text"],
                    "abstained": gen["answer_text"].strip() == NOT_FOUND_MESSAGE,
                    "grade": None,  # fill in by hand: "correct" | "partially_correct" | "incorrect" | "unsupported"
                    "grade_notes": "",
                    "error": None,
                }
            except Exception as exc:
                # Record the failure and keep going -- one bad question (or a
                # rate/quota error) shouldn't lose the rest of the run.
                print(f"  FAILED: {exc}")
                row = {
                    "question": q["question"],
                    "category": q["category"],
                    "reference_answer": q["reference_answer"],
                    "expected_chunk_ids": expected,
                    "retrieved_chunk_ids": [],
                    "hit_at_3": None,
                    "hit_at_5": None,
                    "cited_chunk_ids": [],
                    "answer_text": None,
                    "abstained": False,
                    "grade": None,
                    "grade_notes": "",
                    "error": str(exc),
                }

            results.append(row)
            f.write(json.dumps(row) + "\n")
            f.flush()

    # The appends above may have left stale duplicate lines for any question
    # that failed on a prior run and just succeeded on this one; rewrite the
    # file from the final in-memory results so it holds exactly one row per
    # question (order follows test_set.jsonl).
    order = {q["question"]: i for i, q in enumerate(questions)}
    results.sort(key=lambda r: order.get(r["question"], len(order)))
    with results_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    ok = [r for r in results if r.get("error") is None]
    errored = [r for r in results if r.get("error") is not None]
    answerable = [r for r in ok if r["category"] != "absent"]
    absent = [r for r in ok if r["category"] == "absent"]
    hit_rate_3 = sum(r["hit_at_3"] for r in answerable) / len(answerable) if answerable else 0.0
    hit_rate_5 = sum(r["hit_at_5"] for r in answerable) / len(answerable) if answerable else 0.0
    abstain_accuracy = sum(r["abstained"] for r in absent) / len(absent) if absent else 0.0

    summary = {
        "n_questions": len(results),
        "n_errored": len(errored),
        "n_answerable": len(answerable),
        "n_absent": len(absent),
        "hit_rate_at_3": round(hit_rate_3, 3),
        "hit_rate_at_5": round(hit_rate_5, 3),
        "ablation_delta_5_minus_3": round(hit_rate_5 - hit_rate_3, 3),
        "abstain_accuracy_on_absent": round(abstain_accuracy, 3),
    }
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nSaved {len(results)} results -> {results_path}")
    print(json.dumps(summary, indent=2))
    print(f"\nGrade each row's \"grade\" field in {results_path} by hand, then re-read the file for error analysis.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test-set", type=Path, default=TEST_SET_PATH)
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--k", type=int, default=DEFAULT_K)
    args = ap.parse_args()

    if not args.test_set.exists():
        print(f"Test set not found: {args.test_set}")
        return 1

    run(args.test_set, args.results_dir, args.k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
