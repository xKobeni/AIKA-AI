# AIKA AI — Architecture Overview

AIKA is a CLI-based AI assistant with memory, tool use, planning, research, and multi-agent capabilities. It runs entirely locally via Ollama and stores data in PostgreSQL with vector embeddings.

---

## Directory Structure

```
AIKA AI/
├── .env                  # Environment configuration (git-ignored)
├── requirements.txt      # Python dependencies
├── .gitignore
├── SETUP.md              # Setup guide
├── ARCHITECTURE.md       # This file
├── src/
│   ├── main.py                              # Entry point (CLI loop)
│   ├── create_tables.py                     # DB table initialization
│   ├── migrate_db.py                        # Versioned migration status/dry-run/apply CLI
│   ├── application/
│   │   ├── __init__.py
│   │   ├── events.py                        # Typed application events and results
│   │   ├── confirmation.py                  # Transport-neutral approval coordination
│   │   └── service.py                       # AikaService facade over AikaBrain
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py                      # Settings from .env
│   │   ├── persona.txt                      # Default persona text
│   │   └── personas/                        # Per-agent persona files
│   │       ├── aika.txt                     # Default coordinator persona
│   │       ├── researcher.txt               # Research specialist persona
│   │       ├── planner.txt                  # Planning specialist persona
│   │       └── writer.txt                   # Writing specialist persona
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── agent_profile.py                 # AgentProfile dataclass
│   │   └── agent_registry.py               # Agent registry with JSON persistence
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── brain.py                         # AikaBrain — top-level orchestrator
│   │   ├── router.py                        # Routes decisions to handlers
│   │   ├── intent_classifier.py             # LLM-based intent detection (fast model)
│   │   ├── decision_engine.py               # Decides next action
│   │   ├── context_manager.py               # Builds conversation context
│   │   ├── agent_loop.py                    # LLM-driven tool chaining loop (streaming + native)
│   │   ├── agent_context.py                 # Tracks iterations, tool calls, results
│   │   ├── model_router.py                  # Auto-selects fast/smart model
│   │   ├── tool_call_parser.py              # Parses LLM JSON output (fallback)
│   │   ├── llm_tool_router.py               # LLM-based tool selection (native + fallback)
│   │   ├── tool_result_formatter.py         # Formats tool results for LLM
│   │   ├── reflection.py                    # Task completion reflection
│   │   ├── common.py                        # Shared constants (FAIL_PHRASES, DANGER_PHRASES)
│   │   ├── orchestrator.py                  # Multi-agent orchestration (chain/parallel/team)
│   │   ├── shared_context.py                # Thread-safe shared workspace for agents
│   │   └── agent_message.py                 # Message type for inter-agent communication
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── ollama_client.py                 # Chat inference via Ollama (sync + streaming)
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
│   │   └── models.py                        # ORM models (Memory, Conversation, Session, Agent)
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── memory_repository.py             # Memory CRUD
│   │   ├── conversation_repository.py       # Conversation CRUD + semantic search
│   │   └── session_repository.py            # Session CRUD
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── chat_handler.py                  # Generates chat responses (sync + streaming)
│   │   ├── response_finalizer.py             # Shared response persistence, metrics, and retention
│   │   ├── memory_handler.py                # Memory query handler
│   │   ├── memory_extractor.py              # Background memory extraction
│   │   ├── tool_handler.py                  # Routes to tool execution
│   │   ├── tool_response_handler.py         # Formats tool results
│   │   └── config_handler.py                # Config reload
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tool_manager.py                  # Registry & execution (confirmation + audit)
│   │   ├── default_tools.py                  # Default tool composition/registration
│   │   ├── tool_permission.py               # Permission levels (LOW/MEDIUM/HIGH)
│   │   ├── tool_category.py                 # Tool categorization
│   │   ├── base_tool.py                     # Abstract base class (get_native_schema)
│   │   ├── calculator_tool.py               # Arithmetic evaluations
│   │   ├── file_search_tool.py              # File system search
│   │   ├── file_read_tool.py                # File content reading
│   │   ├── file_read_range_tool.py          # Read specific line ranges
│   │   ├── file_write_tool.py               # File creation/writing (protected paths)
│   │   ├── file_edit_tool.py                # String replacement editing
│   │   ├── file_multi_edit_tool.py          # Multi-file batch editing
│   │   ├── file_delete_tool.py              # File deletion (protected paths)
│   │   ├── file_append_tool.py              # File appending
│   │   ├── file_grep_tool.py                # Content search in files
│   │   ├── file_mkdir_tool.py               # Directory creation
│   │   ├── web_search_tool.py               # DuckDuckGo search
│   │   ├── web_crawl_tool.py                # Web page content crawl
│   │   ├── memory_search_tool.py            # Memory retrieval tool
│   │   ├── shell_tool.py                    # Shell execution (strengthened blocklist)
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
│   ├── research/
│   │   ├── __init__.py
│   │   ├── search_provider.py               # Web search abstraction
│   │   ├── content_processor.py             # Cleans & chunks content
│   │   ├── source_ranker.py                 # Ranks sources by relevance
│   │   └── report_generator.py              # Generates research reports
│   └── models/
│       └── response_metadata.py              # Internal finalized-response metadata
├── tests/
│   ├── __init__.py
│   ├── test_all.py                         # Standalone mocked and optional live test runner
│   ├── demo.py                             # Guided feature tour (11 sections, mocked responses)
│   ├── test_streaming.py                    # Streaming response tests
│   ├── test_native_tool_calling.py          # Native Ollama tool calling tests
│   ├── test_safety.py                       # Safety guardrails tests
│   ├── test_orchestration.py                # Multi-agent orchestration tests
│   ├── test_agent_persona_model.py          # Agent persona/model tests
│   ├── test_tool_scoping.py                 # Per-agent tool access tests
│   ├── test_memory_isolation.py             # Agent-scoped memory tests
│   └── ...                                  # Other existing tests
├── data/                # Runtime memory/conversation storage (git-ignored)
├── logs/                # Execution + audit logs (git-ignored)
├── Trash/               # Archived legacy JSON-storage implementation (not used at runtime)
└── .venv/               # Virtual environment (git-ignored)
```

---

## Data Flow

```
User Input
    │
    ▼
AikaService.stream() / submit()
    │  ┌──────────────────────┐
    ├──│ Typed events         │──► text, status, tool, approval, completion, error
    │  └──────────────────────┘
    │
    ▼
AikaBrain.process() / process_stream()
    │
    ▼
Command Routing (agent commands, session commands, config)
    │  ┌──────────────────┐
    ├──│ Delegate/Chain    │──► Orchestrator runs multi-agent workflow
    │  └──────────────────┘
    │
    ▼
DecisionEngine.decide()
    │  ┌──────────────────┐
    ├──│ IntentClassifier  │──► Intent (chat / memory / tool / plan)
    │  └──────────────────┘
    │
    ▼
AgentLoop.run() / run_stream()
    │  ┌──────────────────┐
    ├──│ ModelRouter       │──► Selects fast/smart model
    │  └──────────────────┘
    │  ┌──────────────────┐
    ├──│ LLM (native)     │──► tool_calls: [{function: {name, arguments}}]
    │  └──────────────────┘
    │  ┌──────────────────┐
    ├──│ ToolManager       │──► Confirmation → Execute → Audit log
    │  └──────────────────┘
    │  ┌──────────────────┐
    ├──│ ToolResultFormatter│──► Formats result for LLM
    │  └──────────────────┘
    │  (loops until task complete or max iterations)
    │
    ▼
Response (streamed token-by-token or returned)
    │
    ▼
ResponseFinalizer (persist response, update metrics, enforce retention)
    │
    ▼
Background: MemoryExtractor.extract_memory()
```

### Key Flows

1. **Chat flow** — Quick detection identifies simple greetings and skips the intent classifier. The model router selects the fast model (qwen2.5:3b) for simple chat. The agent loop calls the LLM, which responds directly without tool use.

2. **Tool calling flow (native)** — When enabled (`NATIVE_TOOL_CALLING=true`), tool schemas are sent to Ollama via the `tools=` parameter. The LLM responds with structured `tool_calls` — no JSON parsing needed. Falls back to text-parsed JSON if native calling is disabled or the model doesn't support it.

3. **Streaming flow** — When `STREAMING_ENABLED=true`, the final response is streamed token-by-token to the user. During tool-calling iterations, chunks are buffered silently. Only the final free-text answer streams.

4. **Auto model switching** — The ModelRouter analyzes each message and selects the appropriate model:
   - **Fast model (qwen2.5:3b)**: Simple greetings, short questions, intent classification, reflection
   - **Smart model (llama3:8b)**: Complex analysis, code writing, multi-step tasks, long messages
   - **Escalation**: If a tool call fails or iteration > 2, automatically escalates to smart model

5. **Memory flow** — Direct memory queries (e.g., "what do I know about X") are handled by the memory handler using hybrid retrieval: semantic similarity + recency + importance + profile scoring. Memories are scoped per agent when `agent_id` is set.

6. **Multi-agent flow** — The Orchestrator coordinates multiple specialized agents:
   - **Delegation**: One agent hands off a subtask to another
   - **Chaining**: Output of one agent feeds into the next
   - **Parallel**: Multiple agents work simultaneously
   - **Team**: Agents collaborate in a shared conversation thread

7. **Plan flow** — Complex multi-step tasks are broken into a plan by the execution planner, then executed step-by-step by the plan executor, with context passed between steps.

---

## Core Components

### Agents (`src/agents/`)
- **`AgentProfile`** — Dataclass holding agent identity: id, name, persona_path, model, allowed_tools, max_iterations, is_active, role, delegates_to.
- **`AgentRegistry`** — Manages agent profiles with JSON persistence (`data/agents.json`). Supports create, update, set_model, set_persona. Auto-discovers persona files from `src/config/personas/`.

### Application (`src/application/`)
- **`AikaService`** — Transport-neutral facade used by the CLI. Serializes access to the stateful brain, streams typed events, coordinates tool approvals, supports best-effort cancellation, exposes bounded session/history views, and owns runtime shutdown.
- **`AikaEvent` / `AikaResult`** — Stable event and collected-result contracts for text deltas, tool activity, approvals, completion, cancellation, and errors.
- **`ConfirmationCoordinator`** — Holds pending approvals outside stdin so a CLI, GUI, or API client can resolve the same high-permission tool request without bypassing `ToolManager` policy.

### Brain (`src/brain/`)
- **`AikaBrain`** — Top-level composition root and orchestrator. Initializes services, repositories, handlers, and the default tool set. Exposes `process(user_message)` and `process_stream(user_message)`, manages session lifecycle and multi-agent orchestration, and owns explicit `close()`/context-manager lifecycle cleanup.
- **`DecisionEngine`** — Uses quick detection for obvious greetings (skips LLM) and falls back to the intent classifier for ambiguous messages. Detects delegation and orchestration intents.
- **`AgentLoop`** — LLM-driven tool chaining loop. Supports native Ollama tool calling (`tools=` parameter) with fallback to text-parsed JSON. Streams responses via `_run_llm_loop_stream()`. Feeds tool results back with proper `role: "tool"` messages.
- **`Orchestrator`** — Coordinates multi-agent workflows: `delegate()`, `chain()`, `parallel()`, `team()`. Uses ThreadPoolExecutor for concurrent agent execution.
- **`SharedContext`** — Thread-safe workspace for orchestrated agents to share data and results.
- **`AgentMessage`** — Typed message (task/result/handoff) for inter-agent communication.
- **`ModelRouter`** — Automatically selects between fast (qwen2.5:3b) and smart (llama3:8b) models based on task complexity, message length, and iteration count.
- **`ToolCallParser`** — Parses LLM JSON output (fallback mode). Handles markdown fences, fixes common JSON errors, rejects unknown tools.
- **`LLMToolRouter`** — Routes tool selection via LLM. Supports native tool calling (passes `tools=` to Ollama) with legacy JSON fallback.
- **`ToolResultFormatter`** — Formats tool results for LLM context, with truncation and per-tool extractors.
- **`ReflectionEngine`** — Evaluates task completion using fast model. Has fail-fast for known error patterns.
- **`ContextManager`** — Builds context windows by merging conversation history (scoped to current session), relevant memories, and profile data. Reuses one request embedding across memory and cross-session retrieval. The final chat assembler budgets the complete prompt rather than memory sections alone.
- **`IntentClassifier`** — Uses the fast LLM model to classify user intent from a set of known intents.

### LLM (`src/llm/`)
- **`OllamaClient`** — Wraps the `ollama` Python library. Provides sync methods (`generate()`, `generate_with_model()`) and streaming generators (`generate_stream()`, `chat_stream()`). Captures exact Ollama prompt-token, response-token, and model-duration metrics when the server returns them.
- **`EmbeddingService`** — Generates vector embeddings via Ollama's embedding API. Both LLM services expose `close()` so their HTTP resources are released during brain shutdown.

### Memory (`src/memory/`)
- **`MemoryRetrievalService`** — Hybrid retrieval combining semantic (cosine similarity), recency, importance, access frequency, and profile matching. Accepts `agent_id` for agent-scoped retrieval.
- **`MemoryRanker`** — Scores candidate memories with configurable weights.
- **`MemoryIntent`** — Matches memories based on the detected user intent.
- **`MemoryCategory`** — Classifies memories into categories (fact, project, goal, skill, etc.).
- **`MemoryProfile`** — Scores memories against user profile traits.

### Database (`src/database/`)
- **`models.py`** — Defines `Memory`, `Conversation`, `Session`, and `Agent` via SQLAlchemy ORM. All tables include `agent_id` columns for multi-agent isolation.
- **`db.py`** — Creates the engine and session factory from `DATABASE_URL`.

### Tools (`src/tools/`)
- **`ToolManager`** — Registry of all available tools. Includes confirmation flow for HIGH permission tools (`TOOL_CALL_CONFIRM_HIGH`), audit logging (`AUDIT_LOG_ENABLED`), and `get_native_tool_schemas()` for Ollama's function calling API.
- **`default_tools.py`** — Keeps construction of the built-in tool set outside `AikaBrain`, reducing composition-root coupling while preserving the existing registry and tool interfaces.
- **`base_tool`** — Abstract base class with `execute(input) → result`, `get_schema()`, and `get_native_schema()` (OpenAI-compatible format).
- **`ToolPermission`** — Three-tier enum: LOW, MEDIUM, HIGH.
- **Built-in tools:** Calculator, File Search, File Read, File Read Range, File Write (protected paths), File Edit, File Multi-Edit, File Delete (protected paths), File Append, File Grep, File Mkdir, Web Search, Web Crawl, Memory Search, Shell (strengthened blocklist), App Launcher, Folder, System Info, Git, Test Runner.
- **Bounded scans and guarded crawling:** File search/grep prune dependency and cache directories and enforce a maximum inspected-file count. Multi-URL crawling uses a bounded worker pool. HTTP fetches validate schemes, DNS addresses, response sizes, and every redirect before Crawl4AI processes the content offline.
- **Safe shell execution:** Commands use argument arrays and `shell=False` by default. Explicit unsafe mode is disabled by default, and all working directories must remain in configured workspace subdirectories.
- **`AppRegistry`** — Windows-only application scanner (Registry `App Paths`, Start Menu `.lnk` parsing via `pywin32`, UWP via `Get-StartApps`). Non-Windows platforms skip these capabilities cleanly; `pywin32` is installed only on Windows.

### Planner (`src/planner/`)
- **`ExecutionPlanner`** — Decomposes complex user requests into a sequence of steps.
- **`PlanExecutor`** — Executes each step, passing intermediate results and managing state.

### Handlers (`src/handlers/`)
- **`ChatHandler`** — Generates responses using the LLM, augmented with context. Provides both sync (`chat()`) and streaming (`chat_stream()`) methods. Uses model router, agent persona, and agent-scoped context.
- **`ResponseFinalizer`** — Shared post-response pipeline used by synchronous and streaming flows. Stores the assistant response and embedding, updates session metrics, applies conversation retention, and returns structured `ResponseMetadata` for downstream memory extraction.
- **`MemoryHandler`** — Responds to memory queries and manages memory retrieval. Accepts `agent_id`.
- **`MemoryExtractor`** — Asynchronously extracts and stores memories from conversations. Links extracted memories to the source conversation via `source_conversation_id`. Accepts `agent_id`.
- **`ToolHandler`** — Delegates tool requests to the tool manager.
- **`ToolResponseHandler`** — Formats tool output into natural language.
- **`ConfigHandler`** — Handles runtime configuration reload requests. Supports `!model`, `!log`, `!persona`, `!settings`, `!set`, `!save`, `!reload`.

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
| `agent_id` | `VARCHAR(50)` | Agent scope (NULL = shared/default) |

### `conversations` table

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
| `agent_id` | `VARCHAR(50)` | Agent scope (NULL = shared/default) |

### `sessions` table

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(50) PK` | Unique session ID (12-char hex) |
| `started_at` | `TIMESTAMP` | Session start time |
| `last_active` | `TIMESTAMP` | Last message time |
| `message_count` | `INTEGER` | Total messages in session |
| `summary` | `TEXT` | Auto-generated session summary (nullable) |
| `agent_id` | `VARCHAR(50)` | Agent scope (NULL = shared/default) |

### `agents` table

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(50) PK` | Agent identifier (e.g. "aika", "researcher") |
| `name` | `VARCHAR(100)` | Display name |
| `persona_path` | `VARCHAR(500)` | Path to persona text file (nullable) |
| `model` | `VARCHAR(100)` | Custom LLM model override (nullable) |
| `allowed_tools` | `TEXT` | JSON list of allowed tool names (NULL = all tools) |
| `max_iterations` | `INTEGER` | Max agent loop iterations (default: 5) |
| `is_active` | `BOOLEAN` | Whether agent is active (default: true) |
| `created_at` | `TIMESTAMP` | Creation time |

---

## Testing

AIKA uses a standalone test runner (`tests/test_all.py`) with Rich-formatted output. It mocks all external dependencies (Ollama, PostgreSQL) for fast execution in normal mode, and supports real integration tests with `--live`.

### Test Runner Architecture

- **Standalone script** — Not pytest. Run directly: `python tests/test_all.py`
- **Register-and-run pattern** — Tests register via `register_test(category, name, func)`, then `run_all()` executes them
- **Runner object** — `TestRunner` holds live mode, verbose mode, and result tracking. Passed to test functions that accept a `runner` parameter via `inspect.signature` introspection
- **15 categories, 108 tests** — Settings & Config, Memory System, Tools (Math, File Ops, Web, System, Memory), Agent System, Brain & Routing, Agent Loop & Tool Calling, Orchestration, Safety, Streaming, Planner & Research, Live Integration

### Test Modes

| Mode | Command | Description |
|---|---|---|
| Mocked | `python tests/test_all.py` | All 108 tests, mocked responses, ~1.5s |
| Verbose | `python tests/test_all.py --verbose` | Shows input/output details per test |
| Live | `python tests/test_all.py --live` | Real Ollama + PostgreSQL integration |
| Category | `python tests/test_all.py --category "Safety"` | Run one category |
| List | `python tests/test_all.py --list` | List all test names |

### Demo Script

`tests/demo.py` runs a guided 11-section feature tour with mocked responses. No external dependencies required. Sections: Settings, Memory, Tools, Tool Scoping, Agents, Orchestration, Streaming, Native Tool Calling, Safety, Planner, Test Suite.

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
| **rich** | Test suite terminal formatting |
