"""Embed every chunk and save the vector index.

Reads data/processed/chunks.jsonl (see src/chunking.py), embeds each chunk's
text with Gemini's gemini-embedding-2 (task_type=retrieval_document), and
writes:
  - data/processed/index.npy       a (n_chunks, 3072) float32 array of embeddings
  - data/processed/index_meta.json a list of chunk metadata, same row order

Deterministic: re-running after deleting these two files reproduces them
exactly, since the same model always maps the same text to the same vector.

Requires GEMINI_API_KEY (see .env.example).

Usage: python src/build_index.py [--chunks data/processed/chunks.jsonl] [--out-dir data/processed]
"""

from __future__ import annotations

import argparse
import hashlib
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


def _texts_fingerprint(texts: list[str]) -> str:
    """Stable hash of the exact text list, in order, that a checkpoint belongs to."""
    h = hashlib.sha256()
    for text in texts:
        h.update(text.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def embed_texts(client, texts: list[str], task_type: str, checkpoint_path: Path, model: str = EMBED_MODEL) -> np.ndarray:
    """Embed `texts` in batches, retrying transient failures with backoff.

    Saves a checkpoint after every batch, so a hard failure partway through
    (a free-tier daily quota cap, say) loses at most one batch of progress,
    not the whole run -- rerunning the script picks up where it left off.

    The checkpoint holds vectors by *position* in `texts`, so it is only valid
    for the exact list that produced it. Editing the corpus between runs
    reorders that list -- a replaced document shifts every later entry -- so
    the checkpoint is fingerprinted and discarded when it no longer matches,
    rather than silently pairing saved vectors with different chunks.
    """
    from google.genai import types

    fingerprint_path = checkpoint_path.with_suffix(".fingerprint")
    fingerprint = _texts_fingerprint(texts)

    done: list[list[float]] = []
    if checkpoint_path.exists():
        saved = fingerprint_path.read_text(encoding="utf-8").strip() if fingerprint_path.exists() else ""
        if saved == fingerprint:
            done = np.load(checkpoint_path).tolist()
            print(f"Resuming from checkpoint: {len(done)}/{len(texts)} chunks already embedded.")
        else:
            print("Checkpoint was built for a different set of chunks; discarding it and starting over.")
            checkpoint_path.unlink(missing_ok=True)
            fingerprint_path.unlink(missing_ok=True)
    fingerprint_path.write_text(fingerprint, encoding="utf-8")

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


def _reusable_vectors(out_dir: Path) -> dict[str, list[float]]:
    """Map chunk text -> embedding from a previous build, when it's safe to reuse.

    Keyed on the chunk text itself, not the chunk id: if a document's content
    changed, its text changed, so its vector is correctly treated as missing and
    re-embedded. Reuse is abandoned entirely if the previous index was built with
    a different embedding model, since vectors from two models aren't comparable.
    """
    index_path, meta_path, model_path = out_dir / "index.npy", out_dir / "index_meta.json", out_dir / ".index_model"
    if not (index_path.exists() and meta_path.exists() and model_path.exists()):
        return {}
    if model_path.read_text(encoding="utf-8").strip() != EMBED_MODEL:
        print(f"Previous index used a different embedding model; rebuilding all vectors.")
        return {}

    vectors = np.load(index_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if len(meta) != vectors.shape[0]:
        return {}
    return {chunk["text"]: vectors[i].tolist() for i, chunk in enumerate(meta)}


def build_index(chunks_path: Path, out_dir: Path, rebuild: bool = False) -> None:
    chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not chunks:
        raise ValueError(f"No chunks found in {chunks_path}. Run src/chunking.py first.")

    client = _client()
    checkpoint_path = out_dir / ".build_index_checkpoint.npy"

    # Incremental build: only chunks whose exact text isn't already embedded cost
    # an API call. Adding documents to the corpus then costs calls proportional to
    # what was added, not to the whole corpus -- which matters against a daily quota.
    reusable = {} if rebuild else _reusable_vectors(out_dir)
    new_texts = [c["text"] for c in chunks if c["text"] not in reusable]
    print(f"{len(chunks)} chunks: reusing {len(chunks) - len(new_texts)}, embedding {len(new_texts)} with '{EMBED_MODEL}'...")

    fresh = {}
    if new_texts:
        vectors = embed_texts(client, new_texts, task_type="retrieval_document", checkpoint_path=checkpoint_path)
        fresh = {text: vectors[i] for i, text in enumerate(new_texts)}

    embeddings = np.array([reusable.get(c["text"], fresh.get(c["text"])) for c in chunks], dtype="float32")
    if embeddings.shape[0] != len(chunks):
        raise RuntimeError(
            f"Embedded {embeddings.shape[0]} vectors but there are {len(chunks)} chunks -- "
            "refusing to save a misaligned index."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "index.npy", embeddings)
    (out_dir / "index_meta.json").write_text(json.dumps(chunks), encoding="utf-8")
    # Records which model produced these vectors, so a later run can tell whether
    # reusing them is valid.
    (out_dir / ".index_model").write_text(EMBED_MODEL, encoding="utf-8")
    checkpoint_path.unlink(missing_ok=True)
    checkpoint_path.with_suffix(".fingerprint").unlink(missing_ok=True)

    print(f"Saved {embeddings.shape[0]} vectors of dim {embeddings.shape[1]} -> {out_dir/'index.npy'}")
    print(f"Saved matching metadata -> {out_dir/'index_meta.json'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument(
        "--rebuild", action="store_true",
        help="Re-embed every chunk instead of reusing vectors from the existing index.",
    )
    args = ap.parse_args()

    if not args.chunks.exists():
        print(f"Input not found: {args.chunks}. Run src/chunking.py first.")
        return 1

    build_index(args.chunks, args.out_dir, rebuild=args.rebuild)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
