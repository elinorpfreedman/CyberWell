"""Embed every chunk and save the vector index.

Reads data/processed/chunks.jsonl (see src/chunking.py), embeds each chunk's
text with Gemini's gemini-embedding-2 (task_type=retrieval_document), and
writes:
  - data/processed/index.npy       a (n_chunks, 768) float32 array of embeddings
  - data/processed/index_meta.json a list of chunk metadata, same row order

Deterministic: re-running after deleting these two files reproduces them
exactly, since the same model always maps the same text to the same vector.

Requires GEMINI_API_KEY (see .env.example).

Usage: python src/build_index.py [--chunks data/processed/chunks.jsonl] [--out-dir data/processed]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

load_dotenv()

CHUNKS_PATH = Path("data/processed/chunks.jsonl")
OUT_DIR = Path("data/processed")
EMBED_MODEL = os.environ.get("CW_EMBED_MODEL", "gemini-embedding-2")
BATCH_SIZE = 20  # kept small so a free-tier rate limit hit only costs one small batch
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 30  # free-tier embed_content quota resets are ~30-60s
INTER_BATCH_DELAY_SECONDS = 2


def _client():
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return genai.Client(api_key=api_key)


def embed_texts(client, texts: list[str], task_type: str, checkpoint_path: Path, model: str = EMBED_MODEL) -> np.ndarray:
    """Embed `texts` in batches, retrying transient failures with backoff.

    Saves a checkpoint after every batch, so a hard failure partway through
    (a free-tier daily quota cap, say) loses at most one batch of progress,
    not the whole run -- rerunning the script picks up where it left off.
    """
    from google.genai import types

    done: list[list[float]] = []
    if checkpoint_path.exists():
        done = np.load(checkpoint_path).tolist()
        print(f"Resuming from checkpoint: {len(done)}/{len(texts)} chunks already embedded.")

    for start in range(len(done), len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        for attempt in range(MAX_RETRIES):
            try:
                result = client.models.embed_content(
                    model=model,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                # Some models silently ignore extra items in a batched `contents`
                # list and return just one embedding instead of raising -- verify
                # the count instead of trusting it, or a mismatch would silently
                # misalign every later chunk_id against the wrong vector.
                if len(result.embeddings) != len(batch):
                    result_embeddings = []
                    for text in batch:
                        single = client.models.embed_content(
                            model=model, contents=[text], config=types.EmbedContentConfig(task_type=task_type)
                        )
                        result_embeddings.append(single.embeddings[0])
                        time.sleep(0.3)
                else:
                    result_embeddings = result.embeddings
                done.extend(e.values for e in result_embeddings)
                break
            except Exception as exc:
                if attempt == MAX_RETRIES - 1:
                    # Save what we have before giving up -- a daily quota cap won't
                    # clear with more retries, but the next run shouldn't redo this work.
                    np.save(checkpoint_path, np.array(done, dtype="float32"))
                    raise RuntimeError(
                        f"Embedding batch starting at {start} failed: {exc}\n"
                        f"Progress saved ({len(done)}/{len(texts)} chunks) -- rerun this script to resume."
                    ) from exc
                wait = RETRY_BACKOFF_SECONDS * (attempt + 1)
                print(f"  batch at {start} failed ({exc}); retrying in {wait}s...")
                time.sleep(wait)
        print(f"  embedded {min(start + BATCH_SIZE, len(texts))}/{len(texts)}")
        np.save(checkpoint_path, np.array(done, dtype="float32"))
        time.sleep(INTER_BATCH_DELAY_SECONDS)
    return np.array(done, dtype="float32")


def build_index(chunks_path: Path, out_dir: Path) -> None:
    chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not chunks:
        raise ValueError(f"No chunks found in {chunks_path}. Run src/chunking.py first.")

    client = _client()
    texts = [c["text"] for c in chunks]
    checkpoint_path = out_dir / ".build_index_checkpoint.npy"
    print(f"Embedding {len(texts)} chunks with '{EMBED_MODEL}'...")
    embeddings = embed_texts(client, texts, task_type="retrieval_document", checkpoint_path=checkpoint_path)
    if embeddings.shape[0] != len(chunks):
        raise RuntimeError(
            f"Embedded {embeddings.shape[0]} vectors but there are {len(chunks)} chunks -- "
            "refusing to save a misaligned index."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "index.npy", embeddings)
    (out_dir / "index_meta.json").write_text(json.dumps(chunks), encoding="utf-8")
    checkpoint_path.unlink(missing_ok=True)

    print(f"Saved {embeddings.shape[0]} vectors of dim {embeddings.shape[1]} -> {out_dir/'index.npy'}")
    print(f"Saved matching metadata -> {out_dir/'index_meta.json'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    if not args.chunks.exists():
        print(f"Input not found: {args.chunks}. Run src/chunking.py first.")
        return 1

    build_index(args.chunks, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
