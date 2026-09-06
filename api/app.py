"""Flask API: ask a question, get a grounded answer with citations.

Endpoints:
  POST /api/conversations                        -> {conversation_id}
  GET  /api/conversations/<id>/messages           -> {messages: [...]}
  POST /api/conversations/<id>/messages           -> {question} in, answer + citations out
  GET  /api/health                                -> {status: "ok"}

Storage (api/storage.py) creates its own SQLite schema on first run. The RAG
pipeline (src/rag.py) is called directly, in-process -- no separate service.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from api import storage
from src.rag import answer as rag_answer

app = Flask(__name__)
CORS(app)

storage.init_db()


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/conversations")
def create_conversation():
    conn = storage.get_connection()
    try:
        conversation_id = storage.create_conversation(conn)
        return jsonify({"conversation_id": conversation_id}), 201
    finally:
        conn.close()


@app.get("/api/conversations/<conversation_id>/messages")
def list_messages(conversation_id: str):
    conn = storage.get_connection()
    try:
        if not storage.conversation_exists(conn, conversation_id):
            return jsonify({"error": f"Conversation '{conversation_id}' not found."}), 404
        return jsonify({"messages": storage.get_messages(conn, conversation_id)})
    finally:
        conn.close()


@app.post("/api/conversations/<conversation_id>/messages")
def post_message(conversation_id: str):
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "\"question\" is required and cannot be empty."}), 400

    conn = storage.get_connection()
    try:
        if not storage.conversation_exists(conn, conversation_id):
            return jsonify({"error": f"Conversation '{conversation_id}' not found."}), 404

        try:
            result = rag_answer(question)
        except RuntimeError as exc:
            # Missing API key, upstream LLM/embedding failure, etc. -- a real,
            # expected failure mode, not a bug -- surfaced as a clean 502.
            return jsonify({"error": f"Could not generate an answer: {exc}"}), 502

        # Write the turn only after generation succeeds, so a failed answer can't
        # leave an orphaned user message with no reply sitting in the transcript.
        storage.add_message(conn, conversation_id, "user", question)
        assistant_message_id = storage.add_message(conn, conversation_id, "assistant", result["answer_text"])
        storage.add_citations(
            conn, assistant_message_id, result["retrieved_chunks"], result["source_chunk_ids"]
        )

        cited_ids = set(result["source_chunk_ids"])
        citations = [
            {
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "score": c["score"],
                "metadata": c["metadata"],
                "cited": c["chunk_id"] in cited_ids,
            }
            for c in result["retrieved_chunks"]
        ]

        return jsonify(
            {
                "conversation_id": conversation_id,
                "message_id": assistant_message_id,
                "question": question,
                "answer_text": result["answer_text"],
                "source_chunk_ids": result["source_chunk_ids"],
                "citations": citations,
            }
        )
    finally:
        conn.close()


@app.errorhandler(Exception)
def unhandled_error(exc):
    """Keep every response JSON, including the unexpected ones.

    Covers both cases: Flask's own HTTP errors (404 on an unknown route, 405, ...)
    are re-emitted as JSON with their own status, and anything else is logged and
    returned as a 500. Without this, an unanticipated exception returns Flask's HTML
    error page (or a full traceback in debug mode), which a JSON client can't parse.
    """
    if isinstance(exc, HTTPException):
        return jsonify({"error": exc.description}), exc.code
    app.logger.exception("Unhandled error while serving %s", request.path)
    return jsonify({"error": "Internal server error."}), 500


if __name__ == "__main__":
    # Debug off by default: it exposes tracebacks and an interactive console.
    debug = os.environ.get("CW_FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(debug=debug, port=int(os.environ.get("CW_API_PORT", 5000)))
