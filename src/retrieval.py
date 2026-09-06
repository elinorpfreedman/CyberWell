"""Retrieve the top-k chunks for a question by cosine similarity.

Loads data/processed/index.npy + index_meta.json (see src/build_index.py)
once (lazily, on first call), embeds the question with Gemini's
gemini-embedding-2 (task_type=retrieval_query -- an asymmetric embedding
mode tuned for "short query vs. long document" matching, distinct from the
retrieval_document mode used when the index was built), and returns the
top-k chunks ranked by cosine similarity.

Requires GEMINI_API_KEY (see .env.example).

Usage: python src/retrieval.py "some question" [k]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv

load_dotenv()

INDEX_PATH = Path("data/processed/index.npy")
META_PATH = Path("data/processed/index_meta.json")
EMBED_MODEL = os.environ.get("CW_EMBED_MODEL", "gemini-embedding-2")
DEFAULT_K = int(os.environ.get("CW_TOP_K", 5))

_client = None
_embeddings: Optional[np.ndarray] = None
_meta: Optional[list[dict]] = None


def _load_index() -> None:
    """Lazily load the Gemini client and index on first use."""
    global _client, _embeddings, _meta
    if _embeddings is not None:
        return

    if not INDEX_PATH.exists() or not META_PATH.exists():
        raise FileNotFoundError(
            f"Index not found ({INDEX_PATH}, {META_PATH}). Run src/build_index.py first."
        )

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    from google import genai

    _client = genai.Client(api_key=api_key)
    _embeddings = np.load(INDEX_PATH)
    # Pre-normalize once so scoring is a plain dot product (cosine similarity).
    _embeddings = _embeddings / np.linalg.norm(_embeddings, axis=1, keepdims=True)
    _meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    if _embeddings.shape[0] != len(_meta):
        raise ValueError(
            f"Index/metadata size mismatch: {_embeddings.shape[0]} vectors vs {len(_meta)} metadata rows."
        )


def _embed_query(question: str) -> np.ndarray:
    from google.genai import types

    result = _client.models.embed_content(
        model=EMBED_MODEL,
        contents=[question],
        config=types.EmbedContentConfig(task_type="retrieval_query"),
    )
    vec = np.array(result.embeddings[0].values, dtype="float32")
    return vec / np.linalg.norm(vec)


def retrieve(question: str, k: int = DEFAULT_K) -> list[dict]:
    """Return the top-k chunks for `question`, ranked by cosine similarity."""
    _load_index()

    query_vec = _embed_query(question)
    scores = _embeddings @ query_vec  # cosine similarity, both sides unit-normalized
    top_indices = np.argsort(-scores)[:k]

    results = []
    for i in top_indices:
        row = _meta[i]
        results.append(
            {
                "chunk_id": row["chunk_id"],
                "text": row["text"],
                "score": float(scores[i]),
                "metadata": {
                    "doc_id": row["doc_id"],
                    "source_file": row["source_file"],
                    "title": row["title"],
                    "platform": row["platform"],
                    "page": row.get("page"),
                },
            }
        )
    return results


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "What counts as hate speech?"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_K
    for r in retrieve(question, k):
        print(f"[{r['score']:.3f}] {r['chunk_id']} ({r['metadata']['platform']}, {r['metadata']['title']})")
        print(f"    {r['text'][:200]}...")
