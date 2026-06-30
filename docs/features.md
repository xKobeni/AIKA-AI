# AIKA — Features & Functionality

AIKA is a CLI-based AI assistant with persistent memory, tool use, multi-step planning, web research, and OS-level capabilities — all running locally via Ollama.

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

Extraction runs on a background thread — it never blocks your conversation.

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
- Persona (personality traits and behavior)

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

AIKA uses LLM-driven tool calling instead of rule-based prefix matching. The LLM decides which tools to use based on the user's request and available tool schemas.

### How It Works

1. **Tool schemas** are sent to the LLM as JSON definitions
2. **LLM responds** with either:
   - `{"tool": "tool_name", "parameters": {...}}` — to call a tool
   - `{"tool": null, "response": "..."}` — to respond directly
3. **Agent loop** executes the tool, feeds the result back to the LLM
4. **Dynamic chaining** — LLM decides next step based on previous results
5. **Automatic escalation** — If tool fails or task is complex, escalates to smart model

### Example Flow

```
User: "find and read the main file"
→ LLM: {"tool": "file_search", "parameters": {"query": "main"}}
→ Tool: Found: src/main.py
→ LLM: {"tool": "file_read", "parameters": {"path": "src/main.py"}}
→ Tool: (file content)
→ LLM: "The main file contains the entry point for AIKA..."
```

### Legacy Fallback

If `TOOL_CALLING_ENABLED=false` or LLM parsing fails twice, AIKA falls back to the original rule-based DecisionEngine + Router.

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

You > !model smart llama3:8b
AIKA > Model smart: llama3:8b -> llama3:8b
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

Creates or overwrites files. Includes permission checks for high-risk operations.

### File Edit

Edits files using string replacement. Supports multiple edits in a single operation.

### File Multi-Edit

Edits multiple files in a single operation. Useful for batch changes across a codebase.

### File Delete

Deletes files. Requires confirmation for high-risk operations.

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

Runs arbitrary shell commands via `subprocess`.

```
> run pip install requests
> run python script.py
> run dir /s *.py
```

**Security features:**
- `SHELL_ENABLED` toggle (default: `true`)
- `SHELL_TIMEOUT` kills long-running commands (default: 30s)
- `SHELL_BLOCKED_KEYWORDS` prevents dangerous commands (rm -rf, format, shutdown, etc.)

### App Launcher

Opens applications on the host system. In addition to the hardcoded aliases below, AIKA can find *any* installed application by scanning the Windows Registry (`App Paths` keys), Start Menu shortcuts (via `pywin32`), and Microsoft Store / UWP apps (via `Get-StartApps`). Results are cached for 5 minutes with optional file persistence.

| Setting | Default | Description |
|---|---|---|
| `APP_LAUNCHER_ENABLED` | `true` | Enable the app launcher tool |
| `APP_LAUNCHER_UWP_ENABLED` | `true` | Enable UWP/Microsoft Store app scanning (adds ~2s to first scan) |

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

```
> open spotify
> open chrome
> open notepad
```

### Folder Listing

Lists directory contents with file sizes. Sandboxed to the workspace root.

```
> list src/
> show files
> list src/brain/
```

### System Information

Reports OS, CPU, RAM, disk usage, Python version, and uptime using `psutil`.

```
> system info
> how's my system
> system health
```

| Field | Source |
|---|---|
| OS version | `platform.uname()` |
| Python version | `platform.python_version()` |
| CPU usage | `psutil.cpu_percent()` |
| RAM usage | `psutil.virtual_memory()` |
| Disk usage | `psutil.disk_usage()` |
| Uptime | `psutil.boot_time()` |

### Git Operations

Performs git operations on the workspace.

```
> git status
> git diff
> git log
> git commit "message"
> git branch
> git checkout main
> git add .
```

### Test Runner

Runs pytest or unittest tests.

```
> run tests
> test tests/test_agent_loop.py
```

---

## Calculator

Safe arithmetic evaluation using AST parsing (no `eval()`). Supports `+`, `-`, `*`, `/`, `//`, `**`, `%`.

```
> 2 + 2
> (15 * 3) / 2
> 2 ** 10
```

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
| `!log <level>` | Change log level (debug/info/warning/error) |
| `!persona` | Display current persona |
| `!persona reload` | Reload persona from file |

### Categories

`llm`, `database`, `memory`, `context`, `conversation`, `web`, `planner`, `validation`, `tools`, `paths`, `os`, `persona`, `logging`

### Examples

```
> !settings llm
> !set CHAT_MODEL=llama3.1:8b
> !set LOG_LEVEL=INFO
> !save
> !model
> !model fast qwen2.5:3b
> !log warning
```

---

## Persona System

AIKA's personality is defined in a plain text file (`src/config/persona.txt`) that can be edited without touching code.

### Commands

| Command | Description |
|---|---|
| `!persona` | Display current persona |
| `!persona reload` | Reload persona from file |

### Editing

Open `src/config/persona.txt` in any text editor and modify the personality, voice, and behavior sections. Then run `!persona reload` to apply changes without restarting.

You can also switch between multiple persona files:

```
> !set PERSONA_PATH=src/config/my_persona.txt
> !persona reload
```

---

## Intent Classification

When rule-based matching doesn't recognize a command, AIKA falls back to an LLM-based intent classifier that categorizes messages into: `WEB_SEARCH`, `FILE_SEARCH`, `MEMORY_SEARCH`, `PLAN_EXECUTION`, or `CHAT`.

---

## Settings Reference

### LLM

| Variable | Default | Description |
|---|---|---|
| `CHAT_MODEL` | `qwen2.5:3b` | Ollama model for chat |
| `FAST_MODEL` | `qwen2.5:3b` | Fast model for simple tasks |
| `SMART_MODEL` | `llama3:8b` | Smart model for complex tasks |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `LLM_TIMEOUT` | `30` | LLM request timeout (seconds) |
| `TOOL_CALLING_ENABLED` | `true` | Enable LLM-driven tool calling |
| `TOOL_CALL_MAX_PARAMS_LENGTH` | `5000` | Max parameter length for tool calls |
| `TOOL_CALL_CONFIRM_HIGH` | `false` | Confirm high-risk tool operations |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:1234@localhost:5432/AIKA_DB` | PostgreSQL connection string |

### Memory Retrieval

| Variable | Default | Description |
|---|---|---|
| `MEMORY_RETRIEVAL_LIMIT` | `8` | Max memories returned per query |
| `MEMORY_CANDIDATE_MULTIPLIER` | `3` | Candidate pool multiplier |
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
| `MAX_CONTEXT_TOKENS` | `2000` | Max tokens for memory context |
| `MAX_PROFILE_PER_CATEGORY` | `2` | Max profile entries per category |
| `RECENT_CONVERSATIONS_COUNT` | `10` | Recent turns included in context |

### Conversation

| Variable | Default | Description |
|---|---|---|
| `CONVERSATION_MAX_COUNT` | `100` | Max stored conversations before trim |

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

### Tools

| Variable | Default | Description |
|---|---|---|
| `FILE_SEARCH_ROOT_PATH` | `.` | Workspace root for file tools |
| `FILE_READ_ENCODING` | `utf-8` | File read encoding |

### OS / Shell

| Variable | Default | Description |
|---|---|---|
| `SHELL_ENABLED` | `true` | Enable shell execution |
| `SHELL_TIMEOUT` | `30` | Command timeout (seconds) |
| `SHELL_BLOCKED_KEYWORDS` | `rm -rf,format,...` | Dangerous command patterns |
| `APP_LAUNCHER_ENABLED` | `true` | Enable app launcher |

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
