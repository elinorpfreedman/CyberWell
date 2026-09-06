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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, request
from flask_cors import CORS

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

        storage.add_message(conn, conversation_id, "user", question)

        try:
            result = rag_answer(question)
        except RuntimeError as exc:
            # Missing API key, upstream LLM/embedding failure, etc. -- a real,
            # expected failure mode, not a bug -- surfaced as a clean 502.
            return jsonify({"error": f"Could not generate an answer: {exc}"}), 502

        assistant_message_id = storage.add_message(conn, conversation_id, "assistant", result["answer_text"])
        storage.add_citations(conn, assistant_message_id, result["retrieved_chunks"])

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


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Not found."}), 404


@app.errorhandler(500)
def server_error(_):
    return jsonify({"error": "Internal server error."}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
