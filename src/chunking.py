"""Split loaded documents into overlapping character chunks for embedding.

Reads data/processed/documents.jsonl (one JSON object per Document, see
src/loading.py) and writes data/processed/chunks.jsonl (one JSON object per
chunk), carrying doc_id/source_file/platform/page metadata through so later
citations can point back to the right source and page.

Chunk size/overlap: 800 characters with 150 characters of overlap. Picked as
a middle ground for policy-prose documents — long enough to keep a rule and
its qualifying clause together, short enough that a handful of chunks cover
most single-topic questions. Splitting on whitespace (not mid-word) keeps
chunk boundaries readable in citations.

Usage: python src/chunking.py [--in data/processed/documents.jsonl] [--out data/processed/chunks.jsonl]
       [--chunk-size 800] [--overlap 150]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

IN_PATH = Path("data/processed/documents.jsonl")
OUT_PATH = Path("data/processed/chunks.jsonl")
CHUNK_SIZE = 800
OVERLAP = 150


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    source_file: str
    title: str
    platform: str
    page: Optional[int]
    text: str


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Slide a chunk_size window over text with overlap, breaking on whitespace."""
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Don't cut mid-word: back off to the last space before `end`,
        # unless that's before `start` (a single very long "word").
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start:
                end = space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


def chunk_documents(documents: list[dict], chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in documents:
        pieces = split_text(doc["text"], chunk_size, overlap)
        for i, piece in enumerate(pieces):
            page_part = f"p{doc['page']}-" if doc.get("page") is not None else ""
            chunk_id = f"{doc['doc_id']}-{page_part}{i:03d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc["doc_id"],
                    source_file=doc["source_file"],
                    title=doc["title"],
                    platform=doc["platform"],
                    page=doc.get("page"),
                    text=piece,
                )
            )
    return chunks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_path", type=Path, default=IN_PATH)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    ap.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    ap.add_argument("--overlap", type=int, default=OVERLAP)
    args = ap.parse_args()

    if not args.in_path.exists():
        print(f"Input not found: {args.in_path}. Run src/loading.py first.")
        return 1

    documents = [json.loads(line) for line in args.in_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    chunks = chunk_documents(documents, args.chunk_size, args.overlap)
    if not chunks:
        print("No chunks produced.")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c)) + "\n")

    lengths = [len(c.text) for c in chunks]
    print(f"Chunked {len(documents)} documents -> {len(chunks)} chunks -> {args.out}")
    print(f"Avg chunk length: {sum(lengths) / len(lengths):.0f} chars (min {min(lengths)}, max {max(lengths)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
