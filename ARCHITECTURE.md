# AIKA AI — Architecture Overview

AIKA is a CLI-based AI assistant with memory, tool use, planning, and research capabilities. It runs entirely locally via Ollama and stores data in PostgreSQL with vector embeddings.

---

## Directory Structure

```
AIKA AI/
├── .env                  # Environment configuration (git-ignored)
├── requirements.txt      # Python dependencies
├── .gitignore
├── SETUP.md              # This file
├── ARCHITECTURE.md       # This file
├── src/
│   ├── main.py                              # Entry point (CLI loop)
│   ├── create_tables.py                     # DB table initialization
│   ├── migrate_db.py                        # DB migration script (new columns/tables)
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                      # Settings from .env
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── brain.py                         # AikaBrain — top-level orchestrator
│   │   ├── router.py                        # Routes decisions to handlers
│   │   ├── intent_classifier.py             # LLM-based intent detection (fast model)
│   │   ├── decision_engine.py               # Decides next action
│   │   ├── context_manager.py               # Builds conversation context
│   │   ├── agent_loop.py                    # LLM-driven tool chaining loop
│   │   ├── agent_context.py                 # Tracks iterations, tool calls, results
│   │   ├── model_router.py                  # Auto-selects fast/smart model
│   │   ├── tool_call_parser.py              # Parses LLM JSON output
│   │   ├── llm_tool_router.py               # LLM-based tool selection
│   │   ├── tool_result_formatter.py         # Formats tool results for LLM
│   │   └── reflection.py                    # Task completion reflection
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── ollama_client.py                 # Chat inference via Ollama
│   │   └── embedding_service.py             # Embedding generation via Ollama
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── memory_retrieval_service.py      # Hybrid retrieval (semantic + scoring)
│   │   ├── memory_ranker.py                 # Scores & ranks memories
│   │   ├── memory_intent.py                 # Intent-aware memory matching
│   │   ├── memory_category.py               # Category classification
│   │   └── memory_profile.py                # User profile memory scoring
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py                          # SQLAlchemy DeclarativeBase
│   │   ├── db.py                            # Engine & session factory
│   │   └── models.py                        # ORM models (Memory, Conversation, Session)
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── memory_repository.py             # Memory CRUD
│   │   ├── conversation_repository.py       # Conversation CRUD + semantic search
│   │   └── session_repository.py            # Session CRUD
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── chat_handler.py                  # Generates chat responses
│   │   ├── memory_handler.py                # Memory query handler
│   │   ├── memory_extractor.py              # Background memory extraction
│   │   ├── tool_handler.py                  # Routes to tool execution
│   │   ├── tool_response_handler.py         # Formats tool results
│   │   └── config_handler.py                # Config reload
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tool_manager.py                  # Registry & execution
│   │   ├── tool_permission.py               # Permission checks
│   │   ├── tool_category.py                 # Tool categorization
│   │   ├── base_tool.py                     # Abstract base class
│   │   ├── calculator_tool.py               # Arithmetic evaluations
│   │   ├── file_search_tool.py              # File system search
│   │   ├── file_read_tool.py                # File content reading
│   │   ├── file_read_range_tool.py          # Read specific line ranges
│   │   ├── file_write_tool.py               # File creation/writing
│   │   ├── file_edit_tool.py                # String replacement editing
│   │   ├── file_multi_edit_tool.py          # Multi-file batch editing
│   │   ├── file_delete_tool.py              # File deletion
│   │   ├── file_append_tool.py              # File appending
│   │   ├── file_grep_tool.py                # Content search in files
│   │   ├── file_mkdir_tool.py               # Directory creation
│   │   ├── web_search_tool.py               # DuckDuckGo search
│   │   ├── web_crawl_tool.py                # Web page content crawl
│   │   ├── memory_search_tool.py            # Memory retrieval tool
│   │   ├── shell_tool.py                    # Shell command execution
│   │   ├── app_launcher_tool.py             # Application launcher
│   │   ├── app_registry.py                  # System-wide app scanning
│   │   ├── folder_tool.py                   # Directory listing
│   │   ├── system_info_tool.py              # System information
│   │   ├── git_tool.py                      # Git operations
│   │   └── test_runner_tool.py              # Run pytest/unittest
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── execution_planner.py             # Breaks tasks into steps
│   │   ├── plan_executor.py                 # Executes plan steps
│   │   ├── plan.py                          # Plan data model
│   │   ├── plan_step.py                     # Individual step model
│   │   └── execution_context.py             # Execution state tracking
│   └── research/
│       ├── __init__.py
│       ├── search_provider.py               # Web search abstraction
│       ├── content_processor.py             # Cleans & chunks content
│       ├── source_ranker.py                 # Ranks sources by relevance
│       └── report_generator.py              # Generates research reports
├── tests/
│   ├── __init__.py
│   ├── test_memory_*.py                    # Memory system tests
│   ├── test_router_integration.py
│   ├── test_planner.py
│   ├── test_executor.py
│   ├── test_embedding.py
│   ├── test_web_search_tool.py
│   ├── test_content_processor.py
│   ├── test_report_generator.py
│   └── ...
├── data/                # Runtime memory/conversation storage (git-ignored)
├── logs/                # Execution logs (git-ignored)
└── .venv/               # Virtual environment (git-ignored)
```

---

## Data Flow

```
User Input
    │
    ▼
AikaBrain.process()
    │
    ▼
DecisionEngine.decide()
    │  ┌──────────────────┐
    ├──│ IntentClassifier  │──► Intent (chat / memory / tool / plan)
    │  └──────────────────┘
    │  (quick detection skips LLM for obvious greetings)
    │
    ▼
AgentLoop.run()
    │  ┌──────────────────┐
    ├──│ ModelRouter       │──► Selects fast/smart model
    │  └──────────────────┘
    │  ┌──────────────────┐
    ├──│ LLM (JSON)        │──► {"tool": "web_search", "parameters": {...}}
    │  └──────────────────┘
    │  ┌──────────────────┐
    ├──│ ToolManager       │──► Executes tool
    │  └──────────────────┘
    │  ┌──────────────────┐
    ├──│ ToolResultFormatter│──► Formats result for LLM
    │  └──────────────────┘
    │  (loops until task complete or max iterations)
    │
    ▼
Response
    │
    ▼
Background: MemoryExtractor.extract_memory()
```

### Key Flows

1. **Chat flow** — The most common path. Quick detection identifies simple greetings and skips the intent classifier. The model router selects the fast model (qwen2.5:3b) for simple chat. The agent loop calls the LLM, which responds directly without tool use.

2. **Tool calling flow** — When the LLM determines a tool is needed, it responds with a JSON object `{"tool": "name", "parameters": {...}}`. The agent loop executes the tool, formats the result, and feeds it back to the LLM. This repeats until the task is complete (dynamic chaining).

3. **Auto model switching** — The ModelRouter analyzes each message and selects the appropriate model:
   - **Fast model (qwen2.5:3b)**: Simple greetings, short questions, intent classification, reflection
   - **Smart model (llama3:8b)**: Complex analysis, code writing, multi-step tasks, long messages
   - **Escalation**: If a tool call fails or iteration > 2, automatically escalates to smart model

4. **Memory flow** — Direct memory queries (e.g., "what do I know about X") are handled by the memory handler using hybrid retrieval: semantic similarity + recency + importance + profile scoring.

5. **Plan flow** — Complex multi-step tasks are broken into a plan by the execution planner, then executed step-by-step by the plan executor, with context passed between steps.

---

## Core Components

### Brain (`src/brain/`)
- **`AikaBrain`** — Top-level orchestrator. Initializes all services, repositories, handlers, and tools. Exposes `process(user_message)` which runs the entire pipeline. Manages session lifecycle (create, list, resume, delete, summary generation).
- **`DecisionEngine`** — Uses quick detection for obvious greetings (skips LLM) and falls back to the intent classifier for ambiguous messages.
- **`AgentLoop`** — LLM-driven tool chaining loop. Calls the LLM with tool schemas, parses JSON responses, executes tools, and feeds results back. Supports dynamic multi-step execution with automatic escalation to smart model on failure.
- **`ModelRouter`** — Automatically selects between fast (qwen2.5:3b) and smart (llama3:8b) models based on task complexity, message length, and iteration count.
- **`ToolCallParser`** — Parses LLM JSON output, handles markdown fences, fixes common JSON errors, rejects unknown tools.
- **`LLMToolRouter`** — Builds prompts with tool schemas and context history for the LLM to select tools.
- **`ToolResultFormatter`** — Formats tool results for LLM context, with truncation and per-tool extractors.
- **`ReflectionEngine`** — Evaluates task completion using fast model. Has fail-fast for known error patterns.
- **`ContextManager`** — Builds context windows by merging conversation history (scoped to current session), relevant memories, and profile data.
- **`IntentClassifier`** — Uses the fast LLM model to classify user intent from a set of known intents.

### LLM (`src/llm/`)
- **`OllamaClient`** — Wraps the `ollama` Python library for chat generation. Supports `generate()` and `generate_with_model()` for model override.
- **`EmbeddingService`** — Generates vector embeddings via Ollama's embedding API.

### Memory (`src/memory/`)
- **`MemoryRetrievalService`** — Hybrid retrieval combining semantic (cosine similarity), recency, importance, access frequency, and profile matching.
- **`MemoryRanker`** — Scores candidate memories with configurable weights.
- **`MemoryIntent`** — Matches memories based on the detected user intent.
- **`MemoryCategory`** — Classifies memories into categories (fact, project, goal, skill, etc.).
- **`MemoryProfile`** — Scores memories against user profile traits.

### Database (`src/database/`)
- **`models.py`** — Defines `Memory`, `Conversation`, and `Session` via SQLAlchemy ORM. `Conversation` includes session tracking, embeddings, metadata columns. `Session` tracks conversation sessions with summaries.
- **`db.py`** — Creates the engine and session factory from `DATABASE_URL`.

### Tools (`src/tools/`)
- **`ToolManager`** — Registry of all available tools. Looks up and executes tools by name. Includes permission checks for high-risk operations.
- **`base_tool`** — Abstract base class with `execute(input) → result` and `get_schema()` interface.
- **Built-in tools:** Calculator, File Search, File Read, File Read Range, File Write, File Edit, File Multi-Edit, File Delete, File Append, File Grep, File Mkdir, Web Search, Web Crawl, Memory Search, Shell, App Launcher, Folder, System Info, Git, Test Runner.
- **`AppRegistry`** — System-wide application scanner (Registry `App Paths`, Start Menu `.lnk` parsing via `pywin32`, UWP via `Get-StartApps`). Used as fallback by the app launcher tool.

### Planner (`src/planner/`)
- **`ExecutionPlanner`** — Decomposes complex user requests into a sequence of steps.
- **`PlanExecutor`** — Executes each step, passing intermediate results and managing state.

### Handlers (`src/handlers/`)
- **`ChatHandler`** — Generates responses using the LLM, augmented with context. Uses model router to select fast/smart model. Passes session-scoped context, generates embeddings for every message, saves metadata (intent, tool, model, timing, token count). Updates session activity.
- **`MemoryHandler`** — Responds to memory queries and manages memory retrieval.
- **`MemoryExtractor`** — Asynchronously extracts and stores memories from conversations. Links extracted memories to the source conversation via `source_conversation_id`.
- **`ToolHandler`** — Delegates tool requests to the tool manager.
- **`ToolResponseHandler`** — Formats tool output into natural language.
- **`ConfigHandler`** — Handles runtime configuration reload requests. Supports `!model` (shows fast/smart, allows switching), `!log`, `!persona`, `!settings`, `!set`, `!save`, `!reload`.

---

## Database Schema

### `memories` table

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PK` | Auto-increment ID |
| `type` | `VARCHAR(50)` | Memory type |
| `content` | `TEXT` | Memory content |
| `embedding` | `vector(768)` | nomic-embed-text embedding |
| `importance` | `INTEGER` | Importance score (1–10) |
| `category` | `VARCHAR(50)` | Category (fact, project, goal, skill, etc.) |
| `access_count` | `INTEGER` | How many times retrieved |
| `profile_score` | `INTEGER` | User profile relevance |
| `last_accessed` | `TIMESTAMP` | Last retrieval time |
| `created_at` | `TIMESTAMP` | Creation time |
| `source_conversation_id` | `INTEGER` | Links memory to the conversation it was extracted from |

### `conversations` table (updated)

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PK` | Auto-increment ID |
| `session_id` | `VARCHAR(50)` | Groups messages into conversation sessions |
| `role` | `VARCHAR(20)` | `user` or `assistant` |
| `content` | `TEXT` | Message content |
| `tool_used` | `VARCHAR(50)` | Which tool was invoked (nullable) |
| `embedding` | `vector(768)` | Embedding for semantic search (nullable) |
| `intent` | `VARCHAR(50)` | Action classification (chat, use_tool, etc.) |
| `model_used` | `VARCHAR(100)` | LLM that generated the response |
| `response_time_ms` | `INTEGER` | Response latency (milliseconds) |
| `token_count` | `INTEGER` | Estimated response token count |
| `created_at` | `TIMESTAMP` | Creation time |

### `sessions` table (new)

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(50) PK` | Unique session ID (12-char hex) |
| `started_at` | `TIMESTAMP` | Session start time |
| `last_active` | `TIMESTAMP` | Last message time |
| `message_count` | `INTEGER` | Total messages in session |
| `summary` | `TEXT` | Auto-generated session summary (nullable) |

---

## Technologies

| Technology | Purpose |
|---|---|
| **Python 3.10+** | Runtime |
| **Ollama** | Local LLM inference (chat + embeddings) |
| **PostgreSQL + pgvector** | Persistent storage with vector search |
| **SQLAlchemy** | ORM and query building |
| **crawl4ai** | Web page content extraction |
| **ddgs** | DuckDuckGo search API |
| **pywin32** | Windows COM/Registry access (.lnk parsing) |
| **pytest** | Testing |
