"""Fetch data/MANIFEST.md's URLs into data/raw/<platform>/<doc-id>.<ext>.

Idempotent: a doc_id with a file already on disk is skipped. Delete the file
(or data/raw/) to force a re-fetch. Extension is taken from the response's
Content-Type, falling back to the manifest's declared HTML/PDF label.

Usage: python src/fetch_corpus.py [--only PLATFORM] [--doc-id DOC-05]
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

MANIFEST_PATH = Path("data/MANIFEST.md")
RAW_DIR = Path("data/raw")
LOG_NAME = "fetch_log.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT = 20
DELAY = 0.75

HEADING_RE = re.compile(r"^###\s+[A-Z]\.\s+(?P<platform>.+?)\s+[—-]\s+\d+\s+[Dd]ocuments?\s*$")
ROW_RE = re.compile(
    r"^\|\s*(?P<doc_id>DOC-\d+)\s*\|\s*(?P<title>.+?)\s*\|\s*"
    r"(?P<fetch_mode>direct|wayback)\s*\|\s*(?P<file_type>HTML|PDF)\s*\|\s*"
    r"(?P<url>https?://\S+?)\s*\|\s*$"
)


@dataclass
class Entry:
    doc_id: str
    title: str
    fetch_mode: str
    file_type: str
    url: str
    platform: str


@dataclass
class Result:
    doc_id: str
    title: str
    platform: str
    url: str
    status: str  # ok | skipped_existing | http_error | request_error
    http_status: Optional[int]
    content_type: Optional[str]
    file_path: Optional[str]
    error: Optional[str]
    fetched_at: str


def slugify(name: str) -> str:
    word = re.split(r"[\s(]", name.strip(), maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]", "", word.lower())


def parse_manifest(path: Path) -> list[Entry]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    entries, platform = [], "unknown"
    for line in path.read_text(encoding="utf-8").splitlines():
        h = HEADING_RE.match(line.strip())
        if h:
            platform = slugify(h.group("platform"))
            continue
        r = ROW_RE.match(line.strip())
        if r:
            entries.append(Entry(platform=platform, **r.groupdict()))
    if not entries:
        raise ValueError(f"No document rows parsed from {path}; check ROW_RE.")
    return entries


def guess_extension(entry: Entry, content_type: Optional[str]) -> str:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if "pdf" in ct:
            return "pdf"
        if "html" in ct:
            return "html"
    return "pdf" if entry.file_type.upper() == "PDF" else "html"


def existing_file(raw_dir: Path, entry: Entry) -> Optional[Path]:
    d = raw_dir / entry.platform
    matches = sorted(d.glob(f"{entry.doc_id}.*")) if d.exists() else []
    return matches[0] if matches else None


def fetch_one(entry: Entry, raw_dir: Path, session: requests.Session) -> Result:
    now = datetime.now(timezone.utc).isoformat()
    existing = existing_file(raw_dir, entry)
    if existing is not None:
        return Result(entry.doc_id, entry.title, entry.platform, entry.url,
                       "skipped_existing", None, None, str(existing), None, now)

    try:
        resp = session.get(entry.url, headers={"User-Agent": USER_AGENT},
                            timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        return Result(entry.doc_id, entry.title, entry.platform, entry.url,
                       "request_error", None, None, None, str(exc), now)

    if resp.status_code != 200:
        return Result(entry.doc_id, entry.title, entry.platform, entry.url,
                       "http_error", resp.status_code, resp.headers.get("Content-Type"),
                       None, f"HTTP {resp.status_code}", now)

    content_type = resp.headers.get("Content-Type")
    ext = guess_extension(entry, content_type)
    out_dir = raw_dir / entry.platform
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{entry.doc_id}.{ext}"
    file_path.write_bytes(resp.content)
    return Result(entry.doc_id, entry.title, entry.platform, entry.url,
                   "ok", resp.status_code, content_type, str(file_path), None, now)


def load_previous_log(log_path: Path) -> dict[str, dict]:
    if not log_path.exists():
        return {}
    try:
        return {r["doc_id"]: r for r in json.loads(log_path.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, KeyError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--only", type=str, default=None, help="platform slug, e.g. 'reddit'")
    ap.add_argument("--doc-id", type=str, default=None, help="e.g. 'DOC-05'")
    ap.add_argument("--delay", type=float, default=DELAY)
    args = ap.parse_args()

    entries = parse_manifest(args.manifest)
    if args.only:
        entries = [e for e in entries if e.platform == args.only]
    if args.doc_id:
        entries = [e for e in entries if e.doc_id == args.doc_id]
    if not entries:
        print("No manifest entries matched the given filters.")
        return 1

    log_path = args.raw_dir / LOG_NAME
    previous = load_previous_log(log_path)

    results = []
    session = requests.Session()
    for i, entry in enumerate(entries):
        result = fetch_one(entry, args.raw_dir, session)
        results.append(result)
        print(f"[{i + 1}/{len(entries)}] {entry.doc_id} ({entry.platform}) -> "
              f"{result.status.upper()} {result.error or result.file_path or ''}")
        if result.status == "ok":
            time.sleep(args.delay)

    merged = {**previous, **{r.doc_id: asdict(r) for r in results}}
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(sorted(merged.values(), key=lambda r: r["doc_id"]), indent=2),
                         encoding="utf-8")

    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped_existing")
    failed = [r for r in results if r.status in ("http_error", "request_error")]
    print(f"\nDone: {ok} fetched, {skipped} already present, {len(failed)} failed.")
    print(f"Log written to {log_path}")
    if failed:
        print("\nFailed (need a manifest fix or replacement URL):")
        for r in failed:
            print(f"  - {r.doc_id} [{r.platform}] {r.title}\n      {r.url}\n      {r.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
