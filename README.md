# AIKA AI

> **Status:** Currently in development. Features and APIs are unstable and subject to change.

AIKA is a living desktop companion that observes, remembers, and grows with its user through memory, intelligent behavior, and OS-level capabilities — powered entirely by local Ollama models and PostgreSQL with vector search.

## Features

- **Local LLM** — Chat via Ollama (Qwen, Llama, Mistral, etc.)
- **LLM Tool Calling** — LLM decides which tools to use via JSON output, with dynamic multi-step chaining
- **Auto Model Switching** — Automatically uses fast model (qwen2.5:3b) for simple tasks and smart model (llama3:8b) for complex reasoning
- **Long-term Memory** — Automatic extraction, semantic search with recency/importance/profile scoring, user profile building
- **Session Management** — Sessions with scoped context, new/list/resume/delete commands, auto-generated summaries
- **Tool Use** — Calculator, file search/read/write/edit/delete, web search, web crawling, git operations, test runner
- **OS Tools** — Shell execution (with safety controls), app launcher (with system-wide Registry + Start Menu + UWP scanning), folder listing, system information
- **Planning** — Decomposes complex requests into executable step-by-step plans
- **Research** — Multi-source web research with relevance ranking and structured report generation
- **Configuration System** — View and change all settings at runtime (`!settings`, `!set`, `!save`, `!reload`, `!model`, `!log`)
- **Editable Persona** — Personality defined in a plain text file, editable without restarting (`!persona`, `!persona reload`)

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
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
| [`docs/features.md`](docs/features.md) | Complete feature reference with settings table |
| [`docs/usage.md`](docs/usage.md) | Practical usage guide with command examples |

## Tech Stack

- **LLM:** Ollama (local inference)
- **Database:** PostgreSQL + pgvector
- **Language:** Python 3.10+
- **Key Libraries:** SQLAlchemy, crawl4ai, httpx, psutil, pywin32
