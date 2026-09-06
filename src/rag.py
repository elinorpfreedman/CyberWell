"""The single entry point the assignment calls directly: answer(question).

Wires retrieval (src/retrieval.py) to generation (src/generation.py) and
returns exactly what's required for review: the answer text, the chunk ids
actually cited, and the full retrieved-chunks list with their scores and
metadata (so a reviewer can see what the model saw, not just what it wrote).
"""

from __future__ import annotations

import os

try:
    from src.generation import generate_answer
    from src.retrieval import retrieve
except ImportError:
    # Allows `python src/rag.py` directly (script mode) in addition to the
    # reviewer's expected `from src.rag import answer` (run from repo root).
    from generation import generate_answer
    from retrieval import retrieve

DEFAULT_K = int(os.environ.get("CW_TOP_K", 5))


def answer(question: str, k: int = DEFAULT_K) -> dict:
    """Retrieve top-k chunks for `question` and generate a grounded, cited answer.

    Returns:
        {
            "answer_text": str,
            "source_chunk_ids": list[str],   # chunk ids actually cited in the answer
            "retrieved_chunks": list[dict],  # every chunk retrieve() returned, with scores
        }
    """
    retrieved_chunks = retrieve(question, k=k)
    result = generate_answer(question, retrieved_chunks)
    return {
        "answer_text": result["answer_text"],
        "source_chunk_ids": result["source_chunk_ids"],
        "retrieved_chunks": retrieved_chunks,
    }


if __name__ == "__main__":
    import sys

    question = sys.argv[1] if len(sys.argv) > 1 else "What is YouTube's hate speech policy?"
    result = answer(question)
    print("ANSWER:", result["answer_text"])
    print("CITED:", result["source_chunk_ids"])
    print(f"RETRIEVED {len(result['retrieved_chunks'])} chunks")
