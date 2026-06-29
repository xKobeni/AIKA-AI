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
   ollama pull qwen2.5:3b        # Chat model
   ollama pull nomic-embed-text   # Embedding model
   ```

   > You can change the models later via the `.env` file.

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
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `DATABASE_URL` | `postgresql://postgres:1234@localhost:5432/AIKA_DB` | PostgreSQL connection string |
| `LOG_LEVEL` | `DEBUG` | Logging verbosity |

> **Security note:** `.env` is git-ignored. Never commit secrets to the repository.

---

## 7. Initialize Database Tables

```bash
python src/create_tables.py
```

This creates the `memories` and `conversations` tables with the `pgvector` vector column.

Expected output:
```
Tables created.
```

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
python -m pytest tests/
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

### `pgvector` type "vector" does not exist
- Connect to the `AIKA_DB` database and run `CREATE EXTENSION vector;`.

### `ModuleNotFoundError`
- Ensure the virtual environment is activated.
- Re-run `pip install -r requirements.txt`.

### GPU / performance
- For better performance, use a GPU-capable Ollama build.
- On Windows, run Ollama with DirectML support if available.
