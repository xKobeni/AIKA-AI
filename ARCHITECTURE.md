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
│   ├── jobs/
│   │   ├── types.py                         # Job state, definitions, control exceptions
│   │   └── runtime.py                       # Registered handlers and managed worker
│   ├── reminders/
│   │   ├── recurrence.py                    # Timezone and recurrence calculations
│   │   ├── scheduler.py                     # Reminder jobs and reconciliation
│   │   ├── commands.py                      # Explicit CLI reminder controls
│   │   └── types.py                         # Reminder lifecycle state
│   ├── orchestration/
│   │   ├── runtime.py                       # Persistent run execution and recovery
│   │   ├── commands.py                      # Explicit CLI run controls
│   │   └── types.py                         # Run and step lifecycle state
│   ├── security/
│   │   └── redaction.py                     # Shared credential redaction
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
│   │   └── models.py                        # ORM models, jobs, and reminders
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── memory_repository.py             # Memory CRUD
│   │   ├── conversation_repository.py       # Conversation CRUD + semantic search
│   │   ├── session_repository.py            # Session CRUD
│   │   ├── job_repository.py                # Atomic job transitions and event history
│   │   ├── reminder_repository.py           # Schedules and occurrence outbox
│   │   └── orchestration_repository.py      # Transactional runs and steps
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
│   │   ├── reminder_tool.py                 # AI-facing reminder operations
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

Durable work follows a separate application path: a caller registers a bounded
job handler, `AikaService.enqueue_job()` validates and persists the request, and
the managed `JobWorker` atomically claims it from PostgreSQL. Each transition is
recorded in `job_events`. Retry-safe interrupted work is requeued on startup;
unknown or unsafe interrupted work waits for explicit approval. Phase 8B supplies
this substrate for reminder scheduling and persistent orchestration.

Phase 8C adds reminders as a consumer of that substrate. A reminder has a stable
database identity and revision; each due time is a delayed `reminder.deliver`
job. Delivery atomically creates a unique occurrence record before calculating
the next recurrence. The occurrence remains in the due outbox until acknowledged.
Startup reconciliation restores missing delayed jobs, while revision checks make
old jobs harmless after rescheduling or cancellation.

Phase 8D adds persistent orchestration without replacing the original synchronous
commands. Each durable run owns an ordered set of PostgreSQL-backed steps and one
non-retry-safe `orchestration.execute` job. Step input and output are committed
between agent calls. An interrupted running step waits for explicit approval
before its bounded second attempt, preventing silent repetition of tool side
effects. A shared service execution lock prevents background agent calls from
racing interactive use of the stateful brain.

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
- **`AikaService`** — Transport-neutral facade used by the CLI. Serializes access to the stateful brain, streams typed events, coordinates tool approvals, supports best-effort cancellation, exposes bounded session/history/job views, and owns brain and job-worker shutdown.
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
- **Runtime performance controls** — Model-routing thresholds are configurable, prompt budgeting uses conservative word/character estimates, and background response work uses bounded admission over a configurable executor. `STREAMING_ENABLED=false` routes requests through the synchronous brain path.
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

### Durable Jobs (`src/jobs/`)
- **`JobRuntime`** — Registry and public facade for validated job definitions. Only registered job types can be enqueued or executed.
- **`JobWorker`** — One managed daemon worker that polls PostgreSQL, cooperatively handles cancellation, and never executes unregistered payloads.
- **`JobContext`** — Handler interface for progress, cancellation checks, and explicit approval gates.
- **Recovery policy** — Retry-safe interrupted jobs may resume within their attempt bound. Unsafe or unknown interrupted work waits for approval when an attempt remains; exhausted work fails without exceeding the hard limit.

### Reminders (`src/reminders/`)
- **`ReminderScheduler`** — Registers the retry-safe reminder job, creates delayed occurrences, emits transport callbacks, and reconciles active schedules before the worker starts.
- **Recurrence policy** — Supports bounded intervals plus daily and weekly local-wall-time schedules using IANA timezones. Missed intervals advance to the first future occurrence instead of flooding the user.
- **Occurrence outbox** — Every triggered reminder creates one unique, durable occurrence. CLI and future transports can list and acknowledge due occurrences independently of job history.
- **`ReminderTool`** — Makes create/list/due/acknowledge/cancel/reschedule operations available to AIKA's normal native/fallback tool-calling loop.

### Persistent Orchestration (`src/orchestration/`)
- **`PersistentOrchestrator`** — Registers one non-retry-safe durable handler and commits every delegate, chain, independent, or team contribution as a separate step.
- **Recovery policy** — Interrupted steps move to durable approval instead of automatically repeating. Explicit resume can retry a failed run with a new revision and reset attempt bound.
- **Dependency policy** — Chain and team steps depend on the previous step; independent-mode steps have no dependencies. The current single job worker executes durable steps one at a time even when they are logically independent.
- **Tool safety** — High-permission tools are denied by default for durable runs. `--allow-high` requires run-level approval and installs a temporary fail-closed execution policy independent of the global confirmation setting.
- **Compatibility** — Existing `delegate`, `chain`, `parallel`, and `team` commands remain synchronous. Durable commands use the explicit `start ... | ...` syntax.

### Database (`src/database/`)
- **`models.py`** — Defines memory, conversation, session, job, reminder, and orchestration persistence. Durable records carry owner, agent, and session scope where applicable.
- **`db.py`** — Creates the engine and session factory from `DATABASE_URL`.
- **Vector retrieval** — Memory cosine search and conversation L2 search use matching HNSW indexes. Profile selection is bounded per category, and retrieval access/profile updates are batched into one transaction each.
- **`JobRepository`** — Owns transactional enqueue, `FOR UPDATE SKIP LOCKED` claims, progress, retry, cancellation, approval, recovery, and append-only job events.

### Tools (`src/tools/`)
- **`ToolManager`** — Registry of all available tools. Includes confirmation flow for HIGH permission tools (`TOOL_CALL_CONFIRM_HIGH`), audit logging (`AUDIT_LOG_ENABLED`), and `get_native_tool_schemas()` for Ollama's function calling API.
- **`default_tools.py`** — Keeps construction of the built-in tool set outside `AikaBrain`, reducing composition-root coupling while preserving the existing registry and tool interfaces.
- **`base_tool`** — Abstract base class with `execute(input) → result`, `get_schema()`, and `get_native_schema()` (OpenAI-compatible format).
- **`ToolPermission`** — Three-tier enum: LOW, MEDIUM, HIGH.
- **Built-in tools:** Calculator, Reminder, File Search, File Read, File Read Range, File Write (protected paths), File Edit, File Multi-Edit, File Delete (protected paths), File Append, File Grep, File Mkdir, Web Search, Web Crawl, Memory Search, Shell (strengthened blocklist), App Launcher, Folder, System Info, Git, Test Runner.
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

### `jobs` table

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(32) PK` | Durable job identifier |
| `job_type` | `VARCHAR(100)` | Registered handler name |
| `payload` | `JSONB` | Validated, bounded, redacted request |
| `status` | `VARCHAR(30)` | Queued/running/approval/terminal state |
| `idempotency_key` | `VARCHAR(200)` | Optional unique request key |
| `progress` | `INTEGER` | Bounded completion percentage |
| `attempt_count` / `max_attempts` | `INTEGER` | Retry accounting and hard limit |
| `result` / `error_type` | `JSONB` / `VARCHAR(200)` | Bounded output or generic failure type |
| `cancel_requested` | `BOOLEAN` | Cooperative cancellation signal |
| `approval_request` / `approval_granted` | `JSONB` / `BOOLEAN` | Durable approval state |
| `available_at` | `TIMESTAMPTZ` | Earliest atomic-claim time |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Lifecycle timestamps |
| `started_at` / `finished_at` | `TIMESTAMPTZ` | Execution timestamps |

### `job_events` table

| Column | Type | Description |
|---|---|---|
| `id` | `BIGSERIAL PK` | Ordered event identifier |
| `job_id` | `VARCHAR(32) FK` | Owning job; cascades on deletion |
| `event_type` | `VARCHAR(50)` | Lifecycle transition name |
| `data` | `JSONB` | Bounded, redacted event metadata |
| `created_at` | `TIMESTAMPTZ` | Event timestamp |

### `reminders` table

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(32) PK` | Stable reminder identifier |
| `message` | `TEXT` | Bounded, redacted reminder text |
| `timezone` | `VARCHAR(64)` | IANA timezone for local recurrences |
| `recurrence` | `JSONB` | Interval, daily, or weekly rule; NULL for one-time |
| `status` | `VARCHAR(20)` | Active, completed, or cancelled |
| `revision` | `INTEGER` | Invalidates stale jobs after rescheduling |
| `next_run_at` / `next_job_id` | `TIMESTAMPTZ` / `VARCHAR(32)` | Next occurrence and linked delayed job |
| `trigger_count` / `last_triggered_at` | `INTEGER` / `TIMESTAMPTZ` | Delivery summary |
| `owner_id` / `agent_id` / `session_id` | `VARCHAR` | Scope metadata |

### `reminder_occurrences` table

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(32) PK` | Due occurrence identifier |
| `reminder_id` | `VARCHAR(32) FK` | Owning reminder; cascades on deletion |
| `revision` / `scheduled_for` | `INTEGER` / `TIMESTAMPTZ` | Unique scheduled occurrence |
| `job_id` | `VARCHAR(32) FK` | Delivery job, retained as nullable history |
| `triggered_at` | `TIMESTAMPTZ` | Actual trigger time |
| `acknowledged_at` | `TIMESTAMPTZ` | NULL while still due |

### `orchestration_runs` table

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(32) PK` | Stable persistent run identifier |
| `kind` / `status` | `VARCHAR` | Delegate/chain/parallel/team and lifecycle state |
| `task` / `agent_ids` | `TEXT` / `JSONB` | Bounded redacted task and selected agents |
| `revision` / `current_job_id` | `INTEGER` / `VARCHAR(32)` | Manual-resume generation and linked durable job |
| `allow_high_tools` / `approved_at` | `BOOLEAN` / `TIMESTAMPTZ` | Explicit autonomous high-permission policy |
| `total_steps` / `completed_steps` | `INTEGER` | Durable progress summary |
| `result` / `error_type` | `JSONB` / `VARCHAR(200)` | Bounded final result or generic failure type |
| `owner_id` / `agent_id` / `session_id` | `VARCHAR` | Scope metadata |

### `orchestration_steps` table

| Column | Type | Description |
|---|---|---|
| `id` / `run_id` | `VARCHAR(32)` | Step identity and cascading parent run |
| `position` / `agent_id` / `turn` | `INTEGER` / `VARCHAR` / `INTEGER` | Stable execution order and assignee |
| `depends_on_step_id` | `VARCHAR(32)` | Nullable dependency link |
| `status` | `VARCHAR(20)` | Pending/running/completed/failed/cancelled/skipped |
| `input_text` / `result_text` | `TEXT` | Bounded persisted execution context and result |
| `attempt_count` / `max_attempts` | `INTEGER` | Recovery attempt bound |

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
