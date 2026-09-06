"""SQLite persistence for conversations, messages, and the chunks cited per answer.

Creates its own schema on first run, given a path (CW_DB_PATH, default
api/cyberwell.db). Three tables:
  - conversations(id, created_at)
  - messages(id, conversation_id, role, content, created_at)
  - citations(id, message_id, chunk_id, source_file, title, platform, page, score)

One connection is opened per call (SQLite handles this fine at this scale,
and it avoids sharing a connection across Flask's request threads).
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get("CW_DB_PATH", "api/cyberwell.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL REFERENCES messages(id),
    chunk_id TEXT NOT NULL,
    source_file TEXT,
    title TEXT,
    platform TEXT,
    page INTEGER,
    score REAL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_citations_message ON citations(message_id);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_conversation(conn: sqlite3.Connection) -> str:
    conversation_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO conversations (id, created_at) VALUES (?, ?)",
        (conversation_id, _now()),
    )
    conn.commit()
    return conversation_id


def conversation_exists(conn: sqlite3.Connection, conversation_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row is not None


def add_message(conn: sqlite3.Connection, conversation_id: str, role: str, content: str) -> str:
    message_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (message_id, conversation_id, role, content, _now()),
    )
    conn.commit()
    return message_id


def add_citations(conn: sqlite3.Connection, message_id: str, retrieved_chunks: list[dict]) -> None:
    rows = [
        (
            message_id,
            c["chunk_id"],
            c["metadata"].get("source_file"),
            c["metadata"].get("title"),
            c["metadata"].get("platform"),
            c["metadata"].get("page"),
            c["score"],
        )
        for c in retrieved_chunks
    ]
    conn.executemany(
        "INSERT INTO citations (message_id, chunk_id, source_file, title, platform, page, score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def get_messages(conn: sqlite3.Connection, conversation_id: str) -> list[dict]:
    messages = conn.execute(
        "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conversation_id,),
    ).fetchall()

    result = []
    for m in messages:
        citations = conn.execute(
            "SELECT chunk_id, source_file, title, platform, page, score FROM citations "
            "WHERE message_id = ? ORDER BY score DESC",
            (m["id"],),
        ).fetchall()
        result.append(
            {
                "message_id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": m["created_at"],
                "citations": [dict(c) for c in citations],
            }
        )
    return result
