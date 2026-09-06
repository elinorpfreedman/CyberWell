"""Generate a grounded, cited answer from retrieved chunks using Gemini.

The model is instructed to answer strictly from the provided chunks, cite
every claim with the chunk_id it came from (e.g. "[DOC-12-000]"), and say
plainly when the chunks don't contain an answer. cited_chunk_ids is parsed
back out of the answer text and filtered against the chunks actually
retrieved, so a hallucinated citation id can never be reported as a source.

Requires GEMINI_API_KEY (see .env.example).
"""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ.get("CW_GEN_MODEL", "gemini-flash-lite-latest")
NOT_FOUND_MESSAGE = "I could not find an answer to this in the corpus."

SYSTEM_PROMPT = f"""You are a policy-question answering assistant for CyberWell, a non-profit \
that researches online hate speech and content moderation. You answer questions about social \
media platforms' hate-speech and moderation policies using ONLY the context chunks provided \
in each user message. You do not use any outside knowledge about these platforms, even if you \
are confident it is correct — policies change and paraphrasing from memory is exactly the \
failure mode this system exists to avoid.

Rules:
1. Every factual claim in your answer must be followed by the chunk id it came from, in \
square brackets, e.g. "Accounts get a strike after the first violation [DOC-15-002]."
2. If a claim is supported by more than one chunk, cite all of them: [DOC-15-002][DOC-16-000].
3. If the provided chunks do not contain enough information to answer the question, respond \
with exactly this sentence and nothing else: "{NOT_FOUND_MESSAGE}"
4. Never fill gaps with general knowledge, speculation, or information from outside the \
provided chunks, even partially.
5. Keep the answer concise and directly responsive to the question."""


def build_user_prompt(question: str, chunks: list[dict]) -> str:
    context_blocks = []
    for c in chunks:
        meta = c["metadata"]
        location = f"{meta['platform']} / {meta['title']}"
        if meta.get("page"):
            location += f" (page {meta['page']})"
        context_blocks.append(f"[{c['chunk_id']}] ({location})\n{c['text']}")
    context = "\n\n".join(context_blocks)
    return f"Context chunks:\n\n{context}\n\nQuestion: {question}"


def extract_cited_chunk_ids(answer_text: str, retrieved_chunk_ids: set[str]) -> list[str]:
    """Pull [chunk_id] citations out of the answer, keeping only real retrieved ids."""
    found = re.findall(r"\[([\w-]+)\]", answer_text)
    # Preserve first-seen order, drop duplicates and anything not actually retrieved.
    seen = set()
    cited = []
    for chunk_id in found:
        if chunk_id in retrieved_chunk_ids and chunk_id not in seen:
            seen.add(chunk_id)
            cited.append(chunk_id)
    return cited


def generate_answer(question: str, chunks: list[dict]) -> dict:
    """Call Gemini with the retrieved chunks and return {answer_text, source_chunk_ids}."""
    if not chunks:
        return {"answer_text": NOT_FOUND_MESSAGE, "source_chunk_ids": []}

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    user_prompt = build_user_prompt(question, chunks)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,
            ),
        )
    except Exception as exc:
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

    answer_text = (response.text or "").strip()
    retrieved_ids = {c["chunk_id"] for c in chunks}
    source_chunk_ids = extract_cited_chunk_ids(answer_text, retrieved_ids)

    return {"answer_text": answer_text, "source_chunk_ids": source_chunk_ids}
