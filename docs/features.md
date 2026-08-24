# AIKA — Features & Functionality

AIKA is a CLI-based AI assistant with persistent memory, tool use, multi-step planning, web research, multi-agent orchestration, and OS-level capabilities — all running locally via Ollama.

---

## Streaming Responses

When `STREAMING_ENABLED=true` (default), AIKA streams response tokens as they're generated. You see text appear word-by-word instead of waiting for the full response.

- During tool-calling iterations, chunks are buffered silently — only the final free-text answer streams to the user.
- Streaming works with both native tool calling and legacy JSON mode.

---

## Native Tool Calling

When `NATIVE_TOOL_CALLING=true` (default), AIKA sends tool schemas to Ollama via the `tools=` parameter. The LLM responds with structured `tool_calls` — no JSON parsing needed.

- Falls back to text-parsed JSON automatically if the model doesn't support native calling.
- Tool schemas are converted from AIKA's `get_schema()` format to Ollama's OpenAI-compatible format.
- Simplified system prompts in native mode — no JSON format instructions needed.

---

## Memory System

AIKA retains information across sessions using PostgreSQL with vector embeddings.

### Automatic Memory Extraction

When you chat, AIKA scans your messages for patterns and automatically stores memories without you asking.

| Pattern | Category | Default Importance |
|---|---|---|
| "I am building...", "my project..." | `project` | 9 |
| "I want to...", "my goal..." | `goal` | 8 |
| "I like...", "my favorite..." | `preference` | 6 |
| "I know...", "I can..." | `skill` | 7 |
| "I am...", "I have...", "I live..." | `fact` | 5 |

Extraction runs on a background thread — it never blocks your conversation. Memories are scoped per agent — each agent has its own isolated memory store.

### Semantic Search

Memories are retrieved using hybrid scoring:

- **Semantic similarity** (cosine distance on vector embeddings) — 50% weight
- **Recency** (exponential decay with configurable half-life) — 15% weight
- **Importance** (static score assigned at creation) — 20% weight
- **Access frequency** (log-scaled) — 5% weight
- **Profile relevance** — 10% weight
- **Category boost** — project (+0.3), goal (+0.2), skill (+0.1)

### Profile Building

AIKA builds a user profile by scoring memories against categories (project, goal, skill, preference, fact, person). The profile is injected into the context window on every chat to personalize responses.

### Memory Commands

| Command | Description |
|---|---|
| `remember <text>` | Manually store a memory (supports `type: content` syntax) |
| `search <query>` | Search stored memories by keyword |
| `memories` | List all stored memories |
| `forget <id>` | Delete a memory by ID |

---

## Multi-Agent System

AIKA coordinates specialized agents that handle different types of work.

### Agent Profile

Each agent has:
- **id** — Unique identifier (e.g. "aika", "researcher")
- **name** — Display name
- **persona_path** — Custom persona file
- **model** — Model override (null = use global)
- **allowed_tools** — List of tool names the agent can use (null = all tools)
- **max_iterations** — Max tool-calling loop iterations (default: 5)
- **role** — Description of the agent's specialty
- **delegates_to** — Which agents this agent can delegate to

### Default Agents

| Agent | Role | Model | Allowed Tools |
|---|---|---|---|
| `aika` | Coordinator | llama3:8b | All tools |
| `researcher` | Research specialist | llama3:8b | web_search, web_crawl, file_read |
| `planner` | Planning specialist | llama3:8b | file_read, file_search, calculator |
| `writer` | Writing specialist | llama3:8b | file_read, file_write, file_edit |

### Orchestration Modes

| Mode | Description |
|---|---|
| **Delegate** | One agent hands off a subtask to another. Returns the specialist's result. |
| **Chain** | Output of one agent feeds into the next as context. |
| **Parallel** | Multiple agents work simultaneously, results are combined. |
| **Team** | Agents collaborate in a shared conversation thread with a shared workspace. Terminates on `[TEAM_DONE]` marker or max turns (default: 10). |

The original commands execute synchronously. Persistent variants use `start`
commands and store every run and step in PostgreSQL. Durable independent-mode
steps retain independent inputs but are currently processed one at a time by the
single managed job worker.

Persistent orchestration commands:

```text
start delegate researcher | Investigate the issue
start chain researcher,writer | Research and write a report
start parallel researcher,planner | Analyze the project independently
start team researcher,planner,writer turns=3 | Produce a proposal
list orchestrations
show orchestration <run_id>
cancel orchestration <run_id>
resume orchestration <run_id>
```

Add `--allow-high` after the mode to request autonomous access to
high-permission tools. Such a run waits for `approve orchestration <run_id>` or
`reject orchestration <run_id>` before its first step. Interrupted unsafe work
also waits for explicit approval before it can repeat.

### Tool Scoping

Three-layer defense for per-agent tool access:
1. **Prompt filtering** — System prompt only lists allowed tools
2. **Parser rejection** — AgentLoop rejects tool calls for disallowed tools
3. **Execution blocking** — ToolManager checks `allowed_tool_names` before execution

### Agent Commands

| Command | Description |
|---|---|
| `list agents` | Show all registered agents |
| `use <id>` | Switch to a specific agent |
| `create agent <id> <name> [model=<model>]` | Create a new agent |
| `set agent model <id> <model>` | Set agent's model |
| `set agent tools <id> [tool1,tool2]` | Set agent's allowed tools |
| `set agent persona <id> <path>` | Set agent's persona file |
| `show agent model <id>` | View agent's model |
| `show agent tools <id>` | View agent's allowed tools |
| `show agent persona <id>` | View agent's persona file |
| `agents status` | Show all agents with status, model, and tools |
| `delegate to <agent>: <task>` | Delegate a task to a specialist |
| `chain <agent1>,<agent2>: <task>` | Chain agents sequentially |
| `parallel <agent1>,<agent2>: <task>` | Run agents in parallel |
| `team <agent1>,<agent2>: <task>` | Team conversation mode |

---

## Conversation

### Chat with LLM

All chat is processed through a local Ollama model with automatic model selection:

- **Fast model (qwen2.5:3b)** — Simple greetings, short questions, intent classification, reflection
- **Smart model (llama3:8b)** — Complex analysis, code writing, multi-step tasks, long messages

Context is built from:

- User profile (relevant memories by category)
- Recent conversation history (scoped to current session)
- Web search results (when automatically triggered)
- Current time and date
- Agent persona (loaded from file)

### Session-Scoped Context

Conversations are grouped into **sessions**. The AI only sees messages from the current session — previous sessions are not included in context, keeping the focus on the active conversation.

### Auto-Trimming

Conversations are trimmed when they exceed `CONVERSATION_MAX_COUNT` (default 100). Oldest entries are deleted first.

---

## Session Management

Conversations are organized into sessions, each representing a fresh conversation thread.

### How Sessions Work

- A session is created automatically when AIKA starts
- All messages during a session are tagged with the same `session_id`
- Context is scoped to the current session — previous sessions are not visible
- When a session ends, its conversation is automatically summarized and stored

### Commands

| Command | Description |
|---|---|
| `new conversation` | End current session and start a new one |
| `list sessions` | Show all sessions with summary, date, and message count |
| `resume <id>` | Switch to a previous session (supports partial ID match) |
| `delete session <id>` | Remove a session from the database (conversations preserved) |
| `help` | Show all available commands |

### Listing, Resuming, and Deleting Sessions

The prompt displays the current session ID: `You [a3f2] >`. Commands use partial ID matching — `resume a3f2` matches any session starting with `a3f2`. If multiple sessions match, all candidates are shown. Deleting the current session automatically creates a new one.

### Auto-Generated Summaries

When a new session is started, the previous session's conversation is automatically summarized (2-3 sentences) by the LLM in the background. Summaries are stored in the `sessions` table and shown when listing or resuming sessions.

### Metadata Per Message

Every message stores additional metadata:

| Field | Description |
|---|---|
| `session_id` | Links to the parent session |
| `embedding` | Vector embedding for semantic search |
| `intent` | Action classification (chat, use_tool, etc.) |
| `tool_used` | Which tool was invoked (if any) |
| `model_used` | LLM that generated the response |
| `response_time_ms` | Response latency |
| `token_count` | Estimated response tokens |

---

## Web & Research

### Reflexive Web Search

AIKA automatically searches the web when it detects:

- **Time-sensitive topics:** weather, news, latest, current, year numbers
- **Questions:** what, who, where, when, why, how
- **Not for:** greetings, personal/memory queries

Search results are injected into the chat prompt. Web search is blocked for personal queries to protect your privacy.

### Multi-Step Research Workflow

When you use keywords like `research`, `investigate`, or `find information about`, AIKA executes an autonomous multi-step plan:

1. **Web Search** — DuckDuckGo search
2. **Web Crawl** — Scrapes top sources
3. **Content Processing** — Cleans and chunks crawled content
4. **Summarize** — LLM summarization of findings
5. **Generate Report** — Structured report with section headers and source citations

### Other Plan Workflows

| Trigger | Steps |
|---|---|
| `research <topic>` | web_search → web_crawl → content_process → summarize → generate_report |
| `read and summarize <path>` | file_read → summarize |
| `summarize <file>` or `analyze <file>` | file_search → file_read → summarize |
| `summarize memories` or `analyze memories` | memory_search → summarize |
| `find and read <name>` | file_search → file_read |
| `read <path>` | file_read |

---

## LLM Tool Calling

AIKA uses LLM-driven tool calling with native Ollama function calling and fallback to JSON text-parsing.

### Native Mode (default)

1. **Tool schemas** are sent to Ollama via the `tools=` parameter
2. **LLM responds** with structured `tool_calls` array
3. **Agent loop** executes tools, feeds results back with `role: "tool"` messages
4. **Dynamic chaining** — LLM decides next step based on previous results
5. **Automatic escalation** — If tool fails or task is complex, escalates to smart model

### Legacy Mode (fallback)

If `NATIVE_TOOL_CALLING=false`, AIKA uses text-parsed JSON:

1. Tool schemas are included in the system prompt as JSON definitions
2. LLM responds with `{"tool": "tool_name", "parameters": {...}}`
3. AgentLoop parses the JSON, executes the tool, feeds result back

### Auto-Fallback

If native tool calling fails (model doesn't support it), AIKA automatically falls back to legacy mode on the next iteration.

---

## Auto Model Switching

AIKA automatically selects between a fast model and a smart model based on task complexity.

### Model Tiers

| Tier | Model | Use For |
|------|-------|---------|
| Fast | qwen2.5:3b | Simple chat, greetings, intent classification, reflection |
| Smart | llama3:8b | Complex analysis, code writing, multi-step reasoning |

### Selection Logic

The `ModelRouter` analyzes each message and selects the appropriate model:

| Factor | Fast Model | Smart Model |
|--------|-----------|-------------|
| Task type | Intent, reflection, simple_chat | Plan, report, file_content |
| Keywords | (none) | analyze, research, write code, debug, refactor |
| Message length | ≤ 20 words | > 20 words |
| Question complexity | Simple (≤ 12 words) | Complex (> 12 words) |
| Iteration count | 0-1 | ≥ 2 (escalation) |
| Tool failure | — | Auto-escalate to smart |

### Configuration

| Variable | Default | Description |
|---|---|---|
| `FAST_MODEL` | `qwen2.5:3b` | Fast model for simple tasks |
| `SMART_MODEL` | `llama3:8b` | Smart model for complex tasks |

### Runtime Commands

```
You > !model
AIKA > Models:
         fast:  qwen2.5:3b
         smart: llama3:8b
         chat:  llama3:8b

You > !model fast qwen2.5:3b
AIKA > Model fast: qwen2.5:3b -> qwen2.5:3b

You > !model list
AIKA > Available Ollama models:
         qwen2.5:3b
         llama3:8b
         nomic-embed-text
```

---

## File Operations

### File Search

Recursively searches the workspace for files by name. Sandboxed to `FILE_SEARCH_ROOT_PATH` (default: `.`).

### File Read

Reads file content and returns it. Path traversal is blocked — any resolved path outside the configured root is rejected.

### File Read Range

Reads specific line ranges from files. Useful for reading portions of large files.

### File Write

Creates or overwrites files. Protected paths (`.env`, `*.key`, `*.pem`, `.git/`) are blocked. Content limited to 1MB.

### File Edit

Edits files using string replacement. Supports multiple edits in a single operation.

### File Multi-Edit

Edits multiple files in a single operation. Useful for batch changes across a codebase.

### File Delete

Deletes files. Protected paths are blocked. Requires confirmation when `TOOL_CALL_CONFIRM_HIGH=true`.

### File Append

Appends content to existing files.

### File Grep

Searches file contents using regex patterns.

### File Mkdir

Creates directories.

### Commands

| Command | Description |
|---|---|
| `find <name>` | Search for files matching name |
| `read <path>` | Read file content |
| `read <path> lines 10-20` | Read specific line range |
| `find and read <name>` | Search then read |
| `write <path> <content>` | Create/overwrite file |
| `edit <path> "old" "new"` | String replacement edit |
| `multi-edit <files>` | Edit multiple files |
| `delete <path>` | Delete file |
| `append <path> <content>` | Append to file |
| `grep <pattern> [path]` | Search file contents |
| `mkdir <path>` | Create directory |

---

## OS Tools

System-level tooling with granular enable/disable controls.

### Shell Execution

Runs commands as argument arrays with `shell=False` by default. Shell operators
such as pipes, redirects, command chaining, and substitutions are rejected in
safe mode.

```
> run pip install requests
> run python script.py
> run dir /s *.py
```

**Security features:**
- `SHELL_ENABLED` toggle (default: `true`)
- `SHELL_UNSAFE_ENABLED` explicit opt-in for commands that require the system shell (default: `false`)
- `SHELL_ALLOWED_WORKDIRS` restricts working directories to approved locations under the workspace
- `SHELL_TIMEOUT` kills long-running commands (default: 30s)
- `SHELL_BLOCKED_KEYWORDS` prevents dangerous commands (13 patterns including rm -rf, format, shutdown, reg add, net user, bcdedit, etc.)

Unsafe mode remains a HIGH-permission operation and still passes through
confirmation, blocklist, audit logging, timeout, and working-directory checks.

### App Launcher

Opens applications on the host system. In addition to the hardcoded aliases below, AIKA can find *any* installed application by scanning the Windows Registry (`App Paths` keys), Start Menu shortcuts (via `pywin32`), and Microsoft Store / UWP apps (via `Get-StartApps`). Results are cached for 5 minutes with optional file persistence.

| Setting | Default | Description |
|---|---|---|
| `APP_LAUNCHER_ENABLED` | `true` | Enable the app launcher tool |
| `APP_LAUNCHER_UWP_ENABLED` | `true` | Enable UWP/Microsoft Store app scanning |

| Alias | App |
|---|---|
| `spotify` | Spotify |
| `chrome` / `google chrome` | Google Chrome |
| `firefox` | Firefox |
| `vscode` / `vs code` / `visual studio code` | VS Code |
| `notepad` | Notepad |
| `calculator` / `calc` | Windows Calculator |
| `explorer` / `file explorer` | File Explorer |
| `terminal` / `cmd` | Command Prompt |
| `powershell` | PowerShell |
| `settings` | Windows Settings |
| `control panel` | Control Panel |

### Folder Listing

Lists directory contents with file sizes. Sandboxed to the workspace root.

### System Information

Reports OS, CPU, RAM, disk usage, Python version, and uptime using `psutil`.

| Field | Source |
|---|---|
| OS version | `platform.uname()` |
| Python version | `platform.python_version()` |
| CPU usage | `psutil.cpu_percent()` |
| RAM usage | `psutil.virtual_memory()` |
| Disk usage | `psutil.disk_usage()` |
| Uptime | `psutil.boot_time()` |

### Git Operations

Performs git operations on the workspace (status, diff, log, commit, branch, checkout, add).

### Test Runner

Runs pytest or unittest tests within AIKA. Supports running specific test files.

---

## Testing & Test Suite

AIKA includes a comprehensive standalone test suite (`tests/test_all.py`) with Rich-formatted output. It runs without external dependencies (all Ollama/PostgreSQL calls are mocked).

### Commands

| Command | Description |
|---|---|
| `python tests/test_all.py` | Run all 108 tests (mocked, ~1.5s) |
| `python tests/test_all.py --verbose` | Show input/output details per test |
| `python tests/test_all.py --list` | List all test names and categories |
| `python tests/test_all.py --category "Safety"` | Run one category |
| `python tests/test_all.py --live` | Real integration tests (needs Ollama + PostgreSQL) |

### Categories (15)

Settings & Config, Memory System, Tools (Math, File Ops, Web, System, Memory), Agent System, Brain & Routing, Agent Loop & Tool Calling, Orchestration, Safety, Streaming, Planner & Research, Live Integration.

### Live Integration Tests

The `--live` flag runs 8 tests against real Ollama and PostgreSQL:
- `test_live_ollama_generate` — Real Ollama generate call
- `test_live_ollama_chat` — Chat with system prompt
- `test_live_ollama_stream` — Streaming response
- `test_live_calculator_then_llm` — Calculator result fed to LLM
- `test_live_web_search` — Real DuckDuckGo search
- `test_live_memory_store_and_search` — Real PostgreSQL memory ops
- `test_live_full_agent_loop` — Full agent loop with real LLM
- `test_live_agent_loop_stream` — Streaming agent loop

### Demo Script

`tests/demo.py` runs a guided 11-section feature tour with mocked responses. No external dependencies required.

Sections: Settings, Memory, Tools, Tool Scoping, Agents, Orchestration, Streaming, Native Tool Calling, Safety, Planner, Test Suite.

---

## Calculator

Safe arithmetic evaluation using AST parsing (no `eval()`). Supports `+`, `-`, `*`, `/`, `//`, `**`, `%`.

---

## Safety Guardrails

### Confirmation Prompts

High-risk tools (file_delete, file_write, shell) require user confirmation when `TOOL_CALL_CONFIRM_HIGH=true` (default: true).

### Audit Logging

All tool calls are logged to `logs/audit.log` in JSONL format when `AUDIT_LOG_ENABLED=true` (default: true). Each entry includes:
- Timestamp
- Tool name
- Input parameters
- Result status (success/error)
- Agent ID (if applicable)

### Protected Paths

Files matching protected patterns cannot be written or deleted. Default patterns: `.env`, `.git`, `.gitignore`, `*.key`, `*.pem`, `*.env`

Configurable via `PROTECTED_PATHS` env var (comma-separated list, supports fnmatch glob patterns).

### Shell Blocklist

Dangerous shell commands are blocked. 13 patterns covering:
- File destruction: `rm -rf`, `rmdir /s`, `Remove-Item -Recurse`
- Disk formatting: `format`, `mkfs`
- System operations: `shutdown`, `bcdedit`, `diskpart`
- Registry: `reg add`, `reg delete`
- User management: `net user`, `net localgroup`
- Encoding: `certutil`

---

## Configuration System

All settings are configurable at runtime without restarting via the `!` command prefix.

### Commands

| Command | Description |
|---|---|
| `!settings` | List all settings |
| `!settings <category>` | List settings in a category |
| `!set KEY=value` | Change a setting at runtime |
| `!save` | Persist changes to `.env` file |
| `!reload` | Reload all settings from `.env` |
| `!model` | Show current models (fast/smart/chat) |
| `!model <name>` | Switch chat model |
| `!model fast <name>` | Switch fast model |
| `!model smart <name>` | Switch smart model |
| `!model list` | List available Ollama models |
| `!log <level>` | Change log level (debug/info/warning/error) |
| `!persona` | Display current persona |
| `!persona reload` | Reload persona from file |

### Categories

`llm`, `database`, `memory`, `context`, `conversation`, `web`, `planner`, `validation`, `tools`, `paths`, `os`, `persona`, `logging`, `safety`

---

## Persona System

AIKA's personality is defined in a plain text file that can be edited without touching code. Each agent has its own persona file.

### Default Persona

`src/config/persona.txt` — Main AIKA persona.

### Agent Personas

`src/config/personas/` — Per-agent persona files:
- `aika.txt` — Coordinator persona
- `researcher.txt` — Research specialist
- `planner.txt` — Planning specialist
- `writer.txt` — Writing specialist

### Commands

| Command | Description |
|---|---|
| `!persona` | Display current persona |
| `!persona reload` | Reload persona from file |
| `show agent persona <id>` | View agent's persona file |
| `set agent persona <id> <path>` | Set agent's persona file |

---

## Intent Classification

When rule-based matching doesn't recognize a command, AIKA falls back to an LLM-based intent classifier that categorizes messages into: `WEB_SEARCH`, `FILE_SEARCH`, `MEMORY_SEARCH`, `PLAN_EXECUTION`, or `CHAT`.

Quick detection also handles obvious greetings and simple questions without calling the intent classifier, saving LLM calls.

---

## Settings Reference

### LLM

| Variable | Default | Description |
|---|---|---|
| `CHAT_MODEL` | `qwen2.5:3b` | Ollama model for chat |
| `FAST_MODEL` | `qwen2.5:3b` | Fast model for simple tasks |
| `SMART_MODEL` | `llama3:8b` | Smart model for complex tasks |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `EMBEDDING_DIMENSION` | `768` | Startup-only vector size; must match the PostgreSQL schema |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `LLM_TIMEOUT` | `30` | LLM request timeout (seconds) |
| `TOOL_CALLING_ENABLED` | `true` | Enable LLM-driven tool calling |
| `TOOL_CALL_MAX_PARAMS_LENGTH` | `5000` | Max parameter length for tool calls |
| `STREAMING_ENABLED` | `true` | Stream response tokens |
| `NATIVE_TOOL_CALLING` | `true` | Use Ollama's native function calling API |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:1234@localhost:5432/AIKA_DB` | PostgreSQL connection string |

### Durable Background Jobs

| Variable | Default | Description |
|---|---|---|
| `JOB_WORKER_POLL_INTERVAL` | `0.5` | Idle worker polling interval in seconds |
| `JOB_PAYLOAD_MAX_CHARS` | `50000` | Maximum serialized job payload size |
| `JOB_RESULT_MAX_CHARS` | `200000` | Maximum serialized job result size |
| `JOB_DEFAULT_MAX_ATTEMPTS` | `3` | Default hard attempt limit |
| `JOB_RETRY_DELAY_SECONDS` | `5` | Initial retry delay before exponential backoff |

### Reminders

| Variable | Default | Description |
|---|---|---|
| `REMINDER_DEFAULT_TIMEZONE` | `UTC` | IANA timezone used for naive reminder times |
| `REMINDER_MESSAGE_MAX_CHARS` | `2000` | Maximum stored reminder message length |
| `REMINDER_MIN_INTERVAL_SECONDS` | `60` | Fastest allowed recurring interval |
| `REMINDER_RECONCILE_LIMIT` | `1000` | Active schedules checked during startup recovery |

Reminder recurrence supports fixed intervals, daily local times, and weekly
local times. Missed intervals produce one due occurrence and advance to the
first future time. Every due occurrence remains visible until acknowledged.

CLI examples:

```text
remind 2026-08-24T09:00:00+08:00 | Drink water
remind every 30m starting 2026-08-24T09:00:00+08:00 | Stand and stretch
list reminders
due reminders
ack reminder <occurrence_id>
cancel reminder <reminder_id>
reschedule reminder <reminder_id> 2026-08-25T10:00:00+08:00
```

### Persistent Orchestration

| Variable | Default | Description |
|---|---|---|
| `ORCHESTRATION_TASK_MAX_CHARS` | `10000` | Maximum persisted task length |
| `ORCHESTRATION_RESULT_MAX_CHARS` | `50000` | Maximum persisted step/final result size |
| `ORCHESTRATION_MAX_AGENTS` | `8` | Maximum agents named in one run |
| `ORCHESTRATION_MAX_STEPS` | `80` | Maximum precomputed durable steps |
| `ORCHESTRATION_MAX_TEAM_TURNS` | `10` | Maximum persistent team turns |
| `ORCHESTRATION_STEP_MAX_ATTEMPTS` | `2` | Per-step interruption/resume bound |
| `ORCHESTRATION_JOB_MAX_ATTEMPTS` | `5` | Hard durable job claim bound |
| `ORCHESTRATION_RECONCILE_LIMIT` | `1000` | Nonterminal runs checked at startup |

### Memory Retrieval

| Variable | Default | Description |
|---|---|---|
| `MEMORY_RETRIEVAL_LIMIT` | `8` | Max memories returned per query |
| `MEMORY_CANDIDATE_MULTIPLIER` | `3` | Repository candidate pool multiplier (applied once) |
| `MEMORY_MIN_SCORE` | `0.3` | Minimum similarity score |
| `MEMORY_RECENCY_HALF_LIFE` | `720` | Recency decay half-life (hours) |
| `MEMORY_SIM_WEIGHT` | `0.50` | Similarity score weight |
| `MEMORY_IMPORTANCE_WEIGHT` | `0.20` | Importance score weight |
| `MEMORY_PROFILE_WEIGHT` | `0.10` | Profile score weight |
| `MEMORY_ACCESS_WEIGHT` | `0.05` | Access count weight |
| `MEMORY_RECENCY_WEIGHT` | `0.15` | Recency score weight |
| `MEMORY_BOOST_PROJECT` | `0.3` | Category boost for projects |
| `MEMORY_BOOST_GOAL` | `0.2` | Category boost for goals |
| `MEMORY_BOOST_SKILL` | `0.1` | Category boost for skills |
| `MEMORY_MAX_PER_CATEGORY` | `2` | Max memories per category in context |
| `MEMORY_VALIDATOR_MIN_SCORE` | `0.92` | Validator threshold (reserved) |

### Context

| Variable | Default | Description |
|---|---|---|
| `MAX_CONTEXT_TOKENS` | `6000` | Conservative limit for each complete Ollama request, including messages and tool schemas |
| `MAX_PROFILE_PER_CATEGORY` | `2` | Max profile entries per category |
| `RECENT_CONVERSATIONS_COUNT` | `10` | Recent turns included in context |
| `MODEL_ROUTER_LONG_MESSAGE_WORDS` | `20` | Smart-model long-message threshold |
| `MODEL_ROUTER_COMPLEX_QUESTION_WORDS` | `12` | Smart-model question threshold |
| `MODEL_ROUTER_ESCALATION_ITERATION` | `2` | Smart-model agent-loop escalation point |

### Conversation

| Variable | Default | Description |
|---|---|---|
| `CONVERSATION_MAX_COUNT` | `100` | Max stored conversations before trim |
| `SESSION_LIST_LIMIT` | `50` | Maximum sessions fetched by one list request |

### Performance

| Variable | Default | Description |
|---|---|---|
| `BACKGROUND_MAX_WORKERS` | `1` | Background extraction/summary workers; restart required |
| `BACKGROUND_MAX_PENDING` | `20` | Maximum admitted pending background tasks; restart required |
| `ORCHESTRATOR_MAX_WORKERS` | `4` | Synchronous parallel-agent worker limit |

### Web

| Variable | Default | Description |
|---|---|---|
| `WEB_SEARCH_MAX_RESULTS` | `5` | Web search result count |

### Planner & Research

| Variable | Default | Description |
|---|---|---|
| `PLAN_WEB_SEARCH_MAX_RESULTS` | `5` | Research web search count |
| `PLAN_TOP_SOURCES_COUNT` | `3` | Top sources to crawl |
| `CRAWL_CONTENT_MAX_CHARS` | `2000` | Max chars per crawled page |
| `WEB_CRAWL_MAX_WORKERS` | `4` | Maximum concurrent workers for multi-URL crawling |
| `WEB_CRAWL_MAX_URLS` | `10` | Maximum URLs accepted by one crawl request |
| `WEB_CRAWL_MAX_REDIRECTS` | `5` | Maximum validated HTTP redirects |
| `WEB_CRAWL_TIMEOUT` | `15` | HTTP fetch timeout in seconds |
| `WEB_CRAWL_MAX_RESPONSE_BYTES` | `5000000` | Maximum downloaded response size |
| `WEB_CRAWL_ALLOW_PRIVATE_NETWORK` | `false` | Allow private/local crawler destinations (unsafe) |
| `FILE_SEARCH_MAX_RESULTS` | `20` | Maximum filename search results |
| `FILE_SCAN_MAX_FILES` | `10000` | Maximum files inspected by one search or grep request |

### Tools

| Variable | Default | Description |
|---|---|---|
| `FILE_SEARCH_ROOT_PATH` | `.` | Workspace root for file tools |
| `FILE_READ_ENCODING` | `utf-8` | File read encoding |

### OS / Shell

| Variable | Default | Description |
|---|---|---|
| `SHELL_ENABLED` | `true` | Enable shell execution |
| `SHELL_UNSAFE_ENABLED` | `false` | Permit explicit `shell=True` execution |
| `SHELL_TIMEOUT` | `30` | Command timeout (seconds) |
| `SHELL_ALLOWED_WORKDIRS` | `.` | Allowed working directories beneath the workspace |
| `SHELL_BLOCKED_KEYWORDS` | `rm -rf,format,...` | Dangerous command patterns |
| `APP_LAUNCHER_ENABLED` | `true` | Enable app launcher |
| `APP_LAUNCHER_UWP_ENABLED` | `true` | Enable UWP app scanning |

### Safety

| Variable | Default | Description |
|---|---|---|
| `TOOL_CALL_CONFIRM_HIGH` | `true` | Confirm high-risk tool operations |
| `AUDIT_LOG_ENABLED` | `true` | Log all tool calls to audit file |
| `AUDIT_LOG_PATH` | `logs/audit.log` | Path to audit log file |
| `PROTECTED_PATHS` | `.env,.git,.gitignore,*.key,*.pem,*.env` | Files/patterns blocked from write/delete |

### Persona

| Variable | Default | Description |
|---|---|---|
| `PERSONA_PATH` | `src/config/persona.txt` | Path to persona text file |

### Paths

| Variable | Default | Description |
|---|---|---|
| `EXECUTION_LOG_PATH` | `logs/execution.log` | Plan execution log |
| `MEMORY_DATA_PATH` | `data/memories` | Memory data directory |
| `CONVERSATION_DATA_PATH` | `data/conversations` | Conversation data directory |

### Logging

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `DEBUG` | Logging verbosity |
| `LOG_FORMAT` | `[%(levelname)s] %(message)s` | Log format string |

### Input Validation

| Variable | Default | Description |
|---|---|---|
| `MAX_INPUT_LENGTH` | `10000` | Max user message length |
| `MAX_CALCULATION_LENGTH` | `200` | Max calculator expression length |
