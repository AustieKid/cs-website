# Local RAG Layer for the UMass Boston CS Website

This directory adds a **lightweight Retrieval-Augmented Generation (RAG)** layer
that improves the existing Ollama-powered chatbot by retrieving relevant website
context *before* sending a prompt.

> **This does NOT train or fine-tune any model.**
> It only adds a retrieval step so the model can answer questions about the site.

---

## Files

| File | Purpose |
|------|---------|
| `build_chunks.py` | Normalize site data into text chunks with metadata |
| `build_embeddings.py` | Embed chunks with `all-MiniLM-L6-v2`; save to `index/` |
| `retrieve.py` | Hybrid retrieval: exact-match boost + BM25 + vector similarity |
| `rag_chat.py` | CLI: retrieve → grounded prompt → Ollama → answer + sources |
| `requirements.txt` | Python dependencies |
| `index/` | Generated index files (not committed to Git) |

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r rag/requirements.txt
```

Also make sure [Ollama](https://ollama.com) is installed and running:

```bash
ollama serve          # start the server (if not already running)
ollama pull llama3.2:3b   # download the model (~2 GB)
```

### 2. (Recommended) Build the Jekyll site first

The chunks builder reads `_site/ai-search.json` when available.
If Jekyll has not been built, it falls back to reading source Markdown files
directly — which works but may miss some computed fields.

```bash
bundle exec jekyll build --config _config.yml,_config_csserver.yml
```

If you do not have Jekyll installed, skip this step; the fallback will still
produce a usable index.

### 3. Build chunks

```bash
python3 rag/build_chunks.py
```

Output: `rag/index/chunks.json`

### 4. Build embeddings

```bash
python3 rag/build_embeddings.py
```

This downloads `sentence-transformers/all-MiniLM-L6-v2` (~90 MB) the first
time it runs.

Output:
- `rag/index/embeddings.npy` — float32 array (N × 384)
- `rag/index/chunk_ids.json` — ordered chunk IDs

### 5. Test RAG chat

```bash
python3 rag/rag_chat.py --model llama3.2:3b "What are the prerequisites for CS310?"
```

Other useful flags:

```bash
# Show the context chunks that were retrieved (debugging)
python3 rag/rag_chat.py --show-context "Who teaches CS410?"

# Show context only; do NOT call Ollama
python3 rag/rag_chat.py --context-only "What programs does UMass Boston CS offer?"

# Use a different number of context chunks
python3 rag/rag_chat.py --top-k 8 --model llama3.2:1b "Tell me about the CS PhD program"
```

---

## How retrieval works

Each question goes through three retrieval passes, whose scores are merged:

1. **Exact-match boost** — if the query contains a course code (`CS310`),
   professor name, program name, or page title, matching chunks receive a
   large additive bonus.  This ensures highly specific entities always surface.

2. **BM25 keyword search** — sparse term-frequency retrieval over the chunk
   text.  Good for keyword-heavy queries.

3. **Dense vector similarity** — the query is encoded with the same
   `all-MiniLM-L6-v2` model used to build the index.  Cosine similarity is
   computed via a dot product (vectors are pre-normalised).  Good for
   paraphrased or semantic queries.

The three normalised scores are summed (exact-match weight = 5×, BM25 = 1×,
vector = 2×) and the top-*k* chunks are passed to Ollama.

---

## How this differs from training the model

| RAG (this) | Fine-tuning / training |
|------------|------------------------|
| No GPU required | Requires GPU |
| Index rebuilds in seconds | Training takes hours |
| Works with any Ollama model | Tied to one trained model |
| Knowledge is auditable JSON | Knowledge is hidden in weights |
| Fresh run after site update | Must re-train after site update |

---

## Rebuilding after a site update

```bash
bundle exec jekyll build --config _config.yml,_config_csserver.yml
python3 rag/build_chunks.py
python3 rag/build_embeddings.py
```

---

## Relationship to existing MCP files

The files in `mcp/` (`server.py`, `site_index.py`, `ollama_grounded_chat.py`)
are **not modified or removed** by this RAG layer.  The two systems run
independently:

- `mcp/` — MCP tool-server approach (structured entity lookup, rule-based context building)
- `rag/` — embedding-based retrieval approach (semantic similarity + BM25 + exact match)

Both call Ollama locally.  You may use either or both.
