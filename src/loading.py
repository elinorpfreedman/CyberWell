"""Load raw files from data/raw/ into a common Document shape.

Walks data/raw/<platform>/<doc_id>.<ext>, parses HTML (BeautifulSoup) or PDF
(pypdf) into cleaned plain text, and writes one JSON object per Document to
data/processed/documents.jsonl. PDFs produce one Document per page so page
numbers survive into citations; HTML produces a single Document (page=None).

Usage: python src/loading.py [--raw-dir data/raw] [--out data/processed/documents.jsonl]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

RAW_DIR = Path("data/raw")
OUT_PATH = Path("data/processed/documents.jsonl")
SKIP_NAMES = {"fetch_log.json"}


@dataclass
class Document:
    doc_id: str
    source_file: str
    title: str
    platform: str
    page: Optional[int]  # None for HTML; 1-indexed page number for PDF
    text: str


def load_html(path: Path) -> Document:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    # Note: <header> is deliberately NOT stripped here -- unlike <nav>/<footer>, it isn't
    # reliably just site chrome (one source page had its entire real article wrapped in a
    # <header> tag, and stripping it silently zeroed out the whole document).
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else path.stem
    text = " ".join(soup.get_text(separator=" ").split())
    return Document(
        doc_id=path.stem,
        source_file=str(path),
        title=title,
        platform=path.parent.name,
        page=None,
        text=text,
    )


def load_pdf(path: Path) -> list[Document]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    docs = []
    for i, page in enumerate(reader.pages, start=1):
        text = " ".join((page.extract_text() or "").split())
        if not text:
            continue
        docs.append(
            Document(
                doc_id=path.stem,
                source_file=str(path),
                title=path.stem,
                platform=path.parent.name,
                page=i,
                text=text,
            )
        )
    return docs


def load_documents(raw_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES:
            continue
        try:
            if path.suffix.lower() == ".html":
                documents.append(load_html(path))
            elif path.suffix.lower() == ".pdf":
                documents.extend(load_pdf(path))
            else:
                print(f"Skipping unrecognized file type: {path}")
        except Exception as exc:
            print(f"Failed to load {path}: {exc}")
    return documents


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    documents = load_documents(args.raw_dir)
    if not documents:
        print(f"No documents loaded from {args.raw_dir}.")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(asdict(doc)) + "\n")

    empty = sum(1 for d in documents if len(d.text) < 200)
    print(f"Loaded {len(documents)} documents -> {args.out}")
    if empty:
        print(f"Warning: {empty} document(s) have under 200 chars of text (likely a JS shell or bad fetch).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
