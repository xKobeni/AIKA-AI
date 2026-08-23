# AIKA AI

> **Status:** Currently in development. Features and APIs are unstable and subject to change.

AIKA is a living desktop companion that observes, remembers, and grows with its user through memory, intelligent behavior, and OS-level capabilities — powered entirely by local Ollama models and PostgreSQL with vector search.

## Features

- **Local LLM** — Chat via Ollama (Qwen, Llama, Mistral, etc.)
- **Streaming Responses** — Tokens appear as they're generated, no waiting for full response
- **Native Tool Calling** — Uses Ollama's built-in function calling API with automatic fallback to text-parsed JSON
- **Multi-Agent System** — Specialized agents (researcher, planner, writer) with delegation, chaining, parallel execution, and team conversations
- **Auto Model Switching** — Automatically uses fast model (qwen2.5:3b) for simple tasks and smart model (llama3:8b) for complex reasoning
- **Long-term Memory** — Automatic extraction, semantic search with recency/importance/profile scoring, user profile building, agent-scoped isolation
- **Session Management** — Sessions with scoped context, new/list/resume/delete commands, auto-generated summaries
- **Tool Use** — Calculator, file search/read/write/edit/delete, web search, web crawling, git operations, test runner
- **OS Tools** — Shell execution (with safety controls), app launcher (with system-wide Registry + Start Menu + UWP scanning), folder listing, system information
- **Planning** — Decomposes complex requests into executable step-by-step plans
- **Research** — Multi-source web research with relevance ranking and structured report generation
- **Safety Guardrails** — Confirmation prompts for high-risk operations, audit logging, protected paths, strengthened command blocklist
- **Per-Agent Configuration** — Custom persona, model, and tool access per agent
- **Configuration System** — View and change all settings at runtime (`!settings`, `!set`, `!save`, `!reload`, `!model`, `!log`)
- **Editable Persona** — Personality defined in a plain text file, editable without restarting (`!persona`, `!persona reload`)
- **Managed Runtime Lifecycle** — Shared sync/stream response finalization and explicit shutdown of background and Ollama client resources
- **Transport-Neutral Application Service** — Typed streaming, tool approval, cancellation, session/history, agent/model status, and lifecycle events shared by the CLI and future interfaces
- **Durable Background Job Foundation** — Registered, validated handlers backed by PostgreSQL with idempotent enqueue, atomic claims, progress/events, bounded retries, cancellation, approval waits, and restart recovery
- **Scheduling and Reminders** — One-time and recurring timezone-aware reminders with live CLI notifications, durable due occurrences, acknowledgement, cancellation, rescheduling, and startup reconciliation
- **Persistent Orchestration** — Restart-safe delegate, chain, parallel-plan, and team runs with durable steps, bounded results, cancellation, explicit recovery approval, and protected high-permission tool execution

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
# Configure .env, set up PostgreSQL + pgvector, pull Ollama models
python src/create_tables.py
python src/migrate_db.py --status
python src/migrate_db.py --apply     # Back up an existing database first
python src/main.py
```

## Documentation

| File | Contents |
|---|---|
| [`SETUP.md`](SETUP.md) | Full setup guide (PostgreSQL, Ollama, env config, troubleshooting) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Project structure, data flow, component descriptions, DB schema |
| [`docs/features.md`](docs/features.md) | Complete feature reference with settings table |
| [`docs/usage.md`](docs/usage.md) | Practical usage guide with command examples |

## Testing

```bash
python tests/test_all.py                  # Run the standalone mocked test suite
python tests/test_all.py --verbose        # Show input/output per test
python tests/test_all.py --list           # List all test names
python tests/test_all.py --category "Memory System"  # Run one category
python tests/test_all.py --live           # Real integration tests (needs Ollama + PostgreSQL)
```

The suite covers settings, memory, tools, agents, routing, orchestration, safety, streaming, planning, research, and optional live integration. The pytest suite adds focused regression coverage for stabilization phases and lifecycle behavior.

```bash
python -m pytest                        # Run the complete pytest suite
```

```bash
python tests/demo.py                      # Guided feature tour (no dependencies needed)
```

## Tech Stack

- **LLM:** Ollama (local inference)
- **Database:** PostgreSQL + pgvector
- **Language:** Python 3.10+
- **Key Libraries:** SQLAlchemy, crawl4ai, httpx, psutil, pywin32, rich
