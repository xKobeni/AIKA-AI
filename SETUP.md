# AIKA AI — Setup Guide

## Prerequisites

- **Python** 3.10 or later
- **Ollama** — local LLM runner
- **PostgreSQL** 14+ with the `pgvector` extension

---

## 1. Clone the Repository & Enter the Project

```bash
cd AIKA\ AI
```

---

## 2. Create and Activate a Virtual Environment

```bash
python -m venv .venv
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (cmd):**
```cmd
.venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

---

## 3. Install Python Dependencies

```bash
pip install -r requirements.txt
playwright install          # Required by crawl4ai for web crawling
```

Key packages:
| Package | Purpose |
|---|---|
| `ollama` | Chat & embedding inference |
| `sqlalchemy` | ORM for PostgreSQL |
| `psycopg2-binary` | PostgreSQL adapter |
| `python-dotenv` | Environment variable loading |
| `pgvector` | Vector similarity search |
| `crawl4ai` | Web crawling (requires Playwright) |
| `playwright` | Browser automation for crawl4ai |
| `ddgs` | DuckDuckGo search |
| `httpx` | HTTP client |
| `numpy` | Numerical operations |
| `psutil` | System information (CPU, RAM, disk) |
| `rich` | Formatted terminal output for test suite |
| `tzdata` | IANA timezone data for reminders, including Windows support |

---

## 4. Set Up PostgreSQL

1. **Install PostgreSQL** (if not already installed).  
   [Download link](https://www.postgresql.org/download/).

2. **Create the database:**
   ```sql
   CREATE DATABASE AIKA_DB;
   ```

3. **Enable the `pgvector` extension:**
   ```sql
   CREATE EXTENSION vector;
   ```

4. **Verify the extension is installed:**
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

---

## 5. Set Up Ollama & Pull Models

1. **Install Ollama** from [ollama.com](https://ollama.com).

2. **Start the Ollama service:**
   ```bash
   ollama serve
   ```

3. **Pull the required models:**

   ```bash
   ollama pull qwen2.5:3b        # Fast model (simple tasks, intent classification)
   ollama pull llama3:8b          # Smart model (complex reasoning, tool calling)
   ollama pull nomic-embed-text   # Embedding model
   ```

   > AIKA auto-switches between fast and smart models based on task complexity.

---

## 6. Configure Environment Variables

Copy the example environment file and adjust values to match your system:

```bash
# Edit .env with your settings
```

Required variables:

| Variable | Default | Description |
|---|---|---|
| `CHAT_MODEL` | `qwen2.5:3b` | Ollama model for chat responses |
| `FAST_MODEL` | `qwen2.5:3b` | Fast model for simple tasks (greetings, intent classification) |
| `SMART_MODEL` | `llama3:8b` | Smart model for complex tasks (analysis, code writing) |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `DATABASE_URL` | `postgresql://postgres:1234@localhost:5432/AIKA_DB` | PostgreSQL connection string |
| `TOOL_CALLING_ENABLED` | `true` | Enable LLM-driven tool calling |
| `LOG_LEVEL` | `DEBUG` | Logging verbosity |

Optional variables:

| Variable | Default | Description |
|---|---|---|
| `STREAMING_ENABLED` | `true` | Stream response tokens as they're generated |
| `NATIVE_TOOL_CALLING` | `true` | Use Ollama's native function calling API |
| `TOOL_CALL_CONFIRM_HIGH` | `true` | Prompt for confirmation before high-risk tool execution |
| `AUDIT_LOG_ENABLED` | `true` | Log all tool calls to audit file |
| `AUDIT_LOG_PATH` | `logs/audit.log` | Path to audit log file |
| `PROTECTED_PATHS` | `.env,.git,.gitignore,*.key,*.pem,*.env` | Files/patterns blocked from write/delete |
| `MAX_CONTEXT_TOKENS` | `6000` | Approximate budget for the complete assembled chat prompt |
| `FILE_SEARCH_MAX_RESULTS` | `20` | Maximum filename matches returned per search |
| `FILE_SCAN_MAX_FILES` | `10000` | Maximum files inspected per search or grep request |
| `WEB_CRAWL_MAX_WORKERS` | `4` | Maximum concurrent workers for multi-page crawling |
| `WEB_CRAWL_MAX_URLS` | `10` | Maximum URLs accepted by one crawl request |
| `WEB_CRAWL_MAX_REDIRECTS` | `5` | Maximum validated redirects per crawl |
| `WEB_CRAWL_TIMEOUT` | `15` | Crawler HTTP timeout in seconds |
| `WEB_CRAWL_MAX_RESPONSE_BYTES` | `5000000` | Maximum downloaded page size |
| `WEB_CRAWL_ALLOW_PRIVATE_NETWORK` | `false` | Allow private/local crawler destinations; leave disabled unless explicitly required |
| `SHELL_UNSAFE_ENABLED` | `false` | Permit explicit system-shell execution |
| `SHELL_ALLOWED_WORKDIRS` | `.` | Allowed shell working directories beneath the workspace |

> **Security note:** `.env` is git-ignored. Never commit secrets to the repository.
> Safe shell execution and public-network-only crawling are enabled by default.
> Windows Registry, Start Menu, and UWP discovery require Windows; `pywin32`
> is conditionally installed only on that platform.

---

## 7. Initialize Database Tables

```bash
python src/create_tables.py
```

This creates the `memories`, `conversations`, `sessions`, `jobs`,
`job_events`, `reminders`, `reminder_occurrences`, `orchestration_runs`, and
`orchestration_steps` tables with
validated `pgvector` columns and `agent_id` columns for multi-agent isolation.
Agent profiles are stored authoritatively in `data/agents.json`.

Expected output:
```
Tables created and embedding dimensions validated.
```

For an existing database, inspect pending migrations before applying anything:

```bash
python src/migrate_db.py --status
python src/migrate_db.py --dry-run
```

Back up the database and resolve any reported orphan records before applying:

```bash
python src/migrate_db.py --apply
```

Each migration runs in its own transaction. Migration 1 adds the documented
session cascade and memory-source foreign keys. Migration 2 preserves the
unused ORM agent table by renaming it to `agents_legacy`, leaving
`data/agents.json` as the only active agent source of truth. Migration 3 adds
the durable job and job-event schema used by the managed background worker.
Migration 4 adds durable reminder schedules and acknowledgement records.
Migration 5 adds persistent orchestration runs, dependency-linked steps, and
restart-safe execution state.

---

## 8. Run AIKA

```bash
python src\main.py
```

You should see:
```
AIKA Online
Type 'exit' to quit

You >
```

---

## 9. Run Tests (Optional)

```bash
python tests/test_all.py                  # Run the standalone mocked suite
python tests/test_all.py --verbose        # Show input/output per test
python tests/test_all.py --list           # List all test names and categories
python tests/test_all.py --category "Memory System"  # Run one category
python tests/test_all.py --live           # Real integration (requires Ollama + PostgreSQL)
```

The standalone runner covers settings, memory, tools, agents, routing, orchestration, safety, streaming, planning, research, and optional live integration. Use `python -m pytest` for the complete regression suite.

> **Windows note:** Set `PYTHONIOENCODING=utf-8` if Rich output shows garbled characters.

```bash
python tests/demo.py                      # Guided feature tour (no dependencies needed)
```

---

## Troubleshooting

### `psycopg2` / database connection fails
- Confirm PostgreSQL is running.
- Verify the `DATABASE_URL` in `.env` matches your PostgreSQL credentials.
- Ensure the `AIKA_DB` database exists.
- Ensure `pgvector` extension is created (`CREATE EXTENSION vector;`).

### `ollama` connection refused
- Run `ollama serve` in a separate terminal.
- Confirm `OLLAMA_HOST=http://localhost:11434` in `.env`.
- Verify the required models are pulled (`ollama list`).
- For auto model switching, ensure both `FAST_MODEL` and `SMART_MODEL` are pulled.

### Model not found
- If you see "model not found" errors, run `ollama list` to see available models.
- Pull missing models: `ollama pull <model_name>`.
- Check `FAST_MODEL` and `SMART_MODEL` in `.env` match your pulled models.

### `pgvector` type "vector" does not exist
- Connect to the `AIKA_DB` database and run `CREATE EXTENSION vector;`.

### `ModuleNotFoundError`
- Ensure the virtual environment is activated.
- Re-run `pip install -r requirements.txt`.

### GPU / performance
- For better performance, use a GPU-capable Ollama build.
- On Windows, run Ollama with DirectML support if available.
