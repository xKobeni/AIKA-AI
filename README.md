# AIKA AI

> **Status:** Currently in development. Features and APIs are unstable and subject to change.

A CLI-based AI assistant that runs entirely locally. Features persistent memory with vector search, tool execution, multi-step planning, and web research — all powered by Ollama.

## Features

- **Local LLM** — Chat via Ollama (Qwen, Llama, Mistral, etc.)
- **Long-term Memory** — Semantic search with recency, importance, and profile scoring
- **Tool Use** — Calculator, file search/read, web search (DuckDuckGo), web crawling
- **Planning** — Decomposes complex requests into executable step-by-step plans
- **Research** — Multi-source web research with relevance ranking and report generation

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
# Configure .env, set up PostgreSQL + pgvector, pull Ollama models
python src/create_tables.py
python src/main.py
```

## Documentation

| File | Contents |
|---|---|
| [`SETUP.md`](SETUP.md) | Full setup guide (PostgreSQL, Ollama, env config, troubleshooting) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Project structure, data flow, component descriptions, DB schema |

## Tech Stack

- **LLM:** Ollama (local inference)
- **Database:** PostgreSQL + pgvector
- **Language:** Python 3.10+
- **Key Libraries:** SQLAlchemy, crawl4ai, httpx
