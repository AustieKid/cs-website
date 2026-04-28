"""Build sentence-transformer embeddings for all text chunks.

Reads  rag/index/chunks.json  (produced by build_chunks.py)
Writes rag/index/embeddings.npy  – float32 array, shape (N, 384)
       rag/index/chunk_ids.json  – ordered list of chunk ids matching rows

Model: sentence-transformers/all-MiniLM-L6-v2  (384-dim, ~90 MB)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = REPO_ROOT / "rag" / "index"
CHUNKS_FILE = INDEX_DIR / "chunks.json"
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"
IDS_FILE = INDEX_DIR / "chunk_ids.json"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 64


def build_embeddings() -> None:
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"{CHUNKS_FILE} not found – run `python3 rag/build_chunks.py` first."
        )

    chunks: list[dict] = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    if not chunks:
        raise ValueError("chunks.json is empty – nothing to embed.")

    texts = [c["text"] for c in chunks]
    ids = [c["id"] for c in chunks]

    print(f"Loading model {MODEL_NAME} …")
    model = SentenceTransformer(MODEL_NAME)

    print(f"Encoding {len(texts)} chunks (batch_size={BATCH_SIZE}) …")
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,   # unit vectors → cosine = dot product
    )
    embeddings = embeddings.astype(np.float32)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_FILE, embeddings)
    IDS_FILE.write_text(json.dumps(ids, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved embeddings {embeddings.shape} → {EMBEDDINGS_FILE}")
    print(f"Saved chunk IDs  ({len(ids)})       → {IDS_FILE}")


if __name__ == "__main__":
    build_embeddings()
