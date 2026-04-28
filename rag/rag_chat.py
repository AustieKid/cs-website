"""RAG-grounded chat with a local Ollama model.

Usage
-----
  python3 rag/rag_chat.py "What are the prerequisites for CS310?"
  python3 rag/rag_chat.py --model llama3.2:3b "What are the prerequisites for CS310?"
  python3 rag/rag_chat.py --show-context "Who teaches CS410?"
  python3 rag/rag_chat.py --context-only "What programs does UMass Boston CS offer?"
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from rag.retrieve import Retriever  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_TOP_K = 5
MAX_CONTEXT_CHARS = 2800   # fits comfortably in 3 B-param prompt budget
MAX_EXCERPT_CHARS = 400    # per-chunk text length in the grounding block


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _chunk_summary(chunk: dict[str, Any]) -> str:
    """One-paragraph description of a chunk, used inside the grounding block."""
    lines: list[str] = []
    title = chunk.get("title") or ""
    etype = chunk.get("entity_type") or ""
    url = chunk.get("url") or ""
    text = chunk.get("text") or ""

    header = f"[{etype.upper()}] {title}"
    if url:
        header += f"  ({url})"
    lines.append(header)
    # Truncate text to keep prompt compact
    excerpt = text[:MAX_EXCERPT_CHARS].rstrip()
    if len(text) > MAX_EXCERPT_CHARS:
        excerpt = excerpt.rsplit(" ", 1)[0] + "…"
    lines.append(excerpt)
    return "\n".join(lines)


def build_prompt(query: str, chunks: list[dict[str, Any]]) -> str:
    context_parts: list[str] = []
    total = 0
    for chunk in chunks:
        part = _chunk_summary(chunk)
        if total + len(part) > MAX_CONTEXT_CHARS:
            break
        context_parts.append(part)
        total += len(part) + 2

    context_block = "\n\n".join(context_parts)

    prompt = textwrap.dedent(f"""\
        You are a helpful assistant for the UMass Boston Computer Science Department.
        Answer the question using ONLY the context below.
        If the answer is not in the context, say "I don't have that information."

        === Context ===
        {context_block}

        === Question ===
        {query}

        === Answer ===
    """)
    return prompt


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

def call_ollama(prompt: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except urllib.error.URLError as exc:
        return (
            f"[ERROR] Could not reach Ollama at {OLLAMA_URL}.\n"
            f"Make sure Ollama is running (`ollama serve`) and the model is pulled "
            f"(`ollama pull {model}`).\nDetails: {exc}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG-grounded chat using a local Ollama model."
    )
    parser.add_argument("query", help="Question to ask")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Ollama model tag (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K,
        help=f"Number of chunks to retrieve (default: {DEFAULT_TOP_K})"
    )
    parser.add_argument(
        "--show-context", action="store_true",
        help="Print retrieved context chunks before the answer"
    )
    parser.add_argument(
        "--context-only", action="store_true",
        help="Only print retrieved context; do NOT call Ollama"
    )
    args = parser.parse_args()

    retriever = Retriever()
    chunks = retriever.retrieve(args.query, top_k=args.top_k)

    if args.show_context or args.context_only:
        print("=== Retrieved Context ===")
        for i, chunk in enumerate(chunks, 1):
            print(f"\n[{i}] score={chunk['score']}  id={chunk['id']}")
            print(f"    Title   : {chunk.get('title')}")
            print(f"    Type    : {chunk.get('entity_type')}")
            print(f"    URL     : {chunk.get('url')}")
            print(f"    Text    : {chunk.get('text', '')[:200]}…")
        print()

    if args.context_only:
        return

    prompt = build_prompt(args.query, chunks)
    print(f"Calling Ollama ({args.model}) …\n")
    answer = call_ollama(prompt, args.model)

    print("=== Answer ===")
    print(answer)
    print()

    # Print source links
    seen: set[str] = set()
    sources: list[tuple[str, str]] = []
    for chunk in chunks:
        url = chunk.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            sources.append((chunk.get("title") or url, url))

    if sources:
        print("=== Sources ===")
        for title, url in sources:
            print(f"  • {title}  →  {url}")


if __name__ == "__main__":
    main()
