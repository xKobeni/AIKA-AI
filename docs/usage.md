# AIKA — Usage Guide

Practical examples for every feature. Run AIKA with `python src\main.py`.

---

## Chat

Just type naturally. AIKA responds with streaming tokens (you see text appear as it's generated). The model auto-switches between fast (qwen2.5:3b) for simple tasks and smart (llama3:8b) for complex ones.

```
You > hello Aika
AIKA > Hey! How's it going?   (streams token-by-token, uses fast model)

You > analyze the architecture of this codebase
AIKA > (uses smart model for complex analysis, streams response)

You > what's the weather like?
AIKA > Let me check... (automatically searches the web)
```

---

## Memory

AIKA auto-extracts memories from your messages, but you can also manage them manually. Memories are scoped per agent — when using a specialized agent, only that agent's memories are retrieved.

### Store a memory

```
You > remember I live in Tokyo
AIKA > Stored: User fact: I live in Tokyo

You > remember project: building an AI assistant
AIKA > Stored: User project: building an AI assistant
```

Supported types: `project`, `goal`, `preference`, `skill`, `fact`, `person`

### Search memories

```
You > search Tokyo
AIKA > Found: User fact: I live in Tokyo

You > search my goals
AIKA > Found: User goal: learn quantum computing
```

### List all memories

```
You > memories
AIKA > 1: User project: building an AI assistant (importance: 9)
       2: User fact: I live in Tokyo (importance: 5)
```

### Delete a memory

```
You > forget 2
AIKA > Memory deleted.
```

---

## Multi-Agent System

AIKA coordinates specialized agents that handle different types of work. You can delegate tasks, chain outputs, run agents in parallel, or have them collaborate in a team conversation.

### Default Agents

| Agent | Role | Model | Tools |
|---|---|---|---|
| `aika` | Coordinator | llama3:8b | All tools |
| `researcher` | Research specialist | llama3:8b | web_search, web_crawl, file_read |
| `planner` | Planning specialist | llama3:8b | file_read, file_search, calculator |
| `writer` | Writing specialist | llama3:8b | file_read, file_write, file_edit |

### Delegate a task

Ask AIKA to hand off work to a specialist:

```
You > delegate to researcher: what are the latest AI papers on memory systems?
AIKA > (researcher agent runs the web search and report, then returns the result)
```

### Chain agents

Chain one agent's output into the next:

```
You > chain researcher,planner,writer: investigate rust vs go for a web backend
AIKA > (researcher gathers info → planner structures the comparison → writer produces a report)
```

### Run agents in parallel

```
You > parallel researcher,writer: research quantum computing AND draft an intro about it
AIKA > (both agents run simultaneously, results combined)
```

### Team conversation

Agents collaborate in a shared conversation thread:

```
You > team researcher,planner,writer: plan and write a blog post about AI safety
AIKA > (agents take turns contributing, sharing context, until [TEAM_DONE] or max 10 turns)
```

### List agent status

```
You > agents status
AIKA > Agent Status:
         aika        : active | model: llama3:8b | tools: all
         researcher  : active | model: llama3:8b | tools: web_search, web_crawl, file_read
         planner     : active | model: llama3:8b | tools: file_read, file_search, calculator
         writer      : active | model: llama3:8b | tools: file_read, file_write, file_edit
```

### Agent-specific chat

Chat directly as a specific agent:

```
You > use researcher
AIKA > Switched to agent: researcher

You > what do you know about vector databases?
AIKA > (researcher agent responds with its persona and tool access)
```

### Configure agents

```
You > create agent analyst Data Analyst model=qwen2.5:3b
AIKA > Agent 'analyst' created.

You > set agent model writer llama3.1:8b
AIKA > Model for 'writer' set to llama3.1:8b

You > set agent tools analyst ["web_search", "file_read"]
AIKA > Tools for 'analyst' set to: web_search, file_read

You > show agent tools writer
AIKA > writer tools: file_read, file_write, file_edit

You > show agent model writer
AIKA > writer model: llama3.1:8b
```

---

## Questions & Research

### Automatic web search

AIKA automatically searches the web for time-sensitive or factual questions.

```
You > what's the latest news on AI?
You > who won the super bowl?
You > weather in London
```

### Multi-step research

Use `research` or `investigate` for deep, multi-source reports.

```
You > research quantum computing advancements 2026
AIKA > Searches the web → crawls top sources → processes content →
       summarizes findings → generates structured report with citations

You > investigate the impact of AI on healthcare
AIKA > (same workflow)
```

### Summarization

```
You > summarize machine learning basics
AIKA > Searches → reads → summarizes

You > analyze the pros and cons of rust vs go
AIKA > Researches → generates analysis
```

---

## File Operations

All file operations are sandboxed to `FILE_SEARCH_ROOT_PATH` (default: the project root). Path traversal is blocked. Protected paths (`.env`, `*.key`, `*.pem`, `.git/`) are blocked from write and delete operations.

### Find files

```
You > find main.py
AIKA > Found: src\main.py

You > find settings
AIKA > Found: src\config\settings.py
           .env
```

### Read files

```
You > read src/main.py
AIKA > (returns file content)

You > read src/main.py lines 1-50
AIKA > (returns lines 1-50)
```

### Combined find and read

```
You > find and read settings.py
AIKA > Searches for settings.py → reads it → returns content

You > read and summarize main.py
AIKA > Reads main.py → generates LLM summary

You > find and summarize config
AIKA > Searches for "config" → reads found file → summarizes
```

### Edit files

```
You > edit src/config/settings.py "old_value" "new_value"
AIKA > (performs string replacement)

You > multi-edit src/config/settings.py src/.env
AIKA > (edits multiple files in one operation)
```

### Git operations

```
You > git status
AIKA > (shows git status)

You > git commit "fix: update settings"
AIKA > (commits changes)

You > git diff
AIKA > (shows diff)
```

### Run tests

```
You > run tests
AIKA > (runs pytest)

You > test tests/test_agent_loop.py
AIKA > (runs specific test file)
```

---

## Session Management

The prompt shows the current session's short ID: `You [a3f2] >`. All session commands support partial ID matching — `resume a3f` matches any session starting with `a3f`.

### Start a new conversation

```
You [a3f2] > new conversation
AIKA > New conversation started.

You [b7d1] > what was I building again?
AIKA > I'm not sure — this is a fresh session. Tell me about it!
```

The previous session is automatically summarized in the background and stored in the database.

### List all sessions

```
You [b7d1] > list sessions
AIKA > **Sessions:**
  * `b7d1c0f3a2e5`  2026-06-30 14:02  0 msgs  _No summary yet_
     `a3f28b1c4d6e`  2026-06-30 13:45  12 msgs  _User asked about memory system and project architecture..._
```

### Resume a previous session

```
You [b7d1] > resume a3f2
AIKA > Resumed session `a3f28b1c4d6e`.
**Session summary:** User asked about memory system and project architecture, discussed PostgreSQL setup...
```

### Delete a session

```
You [a3f2] > delete session b7d1
AIKA > Deleted session `b7d1c0f3a2e5`.
```

Deleting the current session automatically creates a new one.

### Help

```
You [a3f2] > help
AIKA > Commands: new session, list sessions, resume <id>, delete session <id>, clear, help, exit
       Config: !settings, !set, !save, !reload, !model, !log, !persona
       Agents: list agents, use <id>, delegate, chain, team, agents status
```

---

## Reminders

AIKA stores reminders in PostgreSQL, so schedules and unacknowledged due
occurrences survive application restarts. Use an explicit offset in the ISO
timestamp when possible. A timestamp without an offset uses
`REMINDER_DEFAULT_TIMEZONE` (UTC by default).

### Create a one-time reminder

```text
You > remind 2026-08-24T09:00:00+08:00 | Drink water
AIKA > Reminder scheduled: <reminder_id>
```

### Create a recurring interval reminder

```text
You > remind every 30m starting 2026-08-24T09:00:00+08:00 | Stand and stretch
AIKA > Reminder scheduled: <reminder_id>
```

Intervals accept `m`, `h`, or `d`. They must meet the configured
`REMINDER_MIN_INTERVAL_SECONDS` safety limit. AIKA's reminder tool also supports
daily and weekly local-time recurrence when a model creates the schedule.

### Review and manage reminders

```text
You > list reminders
You > due reminders
You > ack reminder <occurrence_id>
You > cancel reminder <reminder_id>
You > reschedule reminder <reminder_id> 2026-08-25T10:00:00+08:00
```

`due reminders` lists triggered occurrences that have not been acknowledged.
Acknowledging an occurrence clears that notification without cancelling future
occurrences. Rescheduling retains an existing recurrence rule; cancelling stops
future delivery.

---

## Persistent Orchestration

The existing `delegate`, `chain`, `parallel`, and `team` commands still run
synchronously. Use the explicit `start` form when a run must preserve its steps,
progress, and result across application restarts.

```text
You > start delegate researcher | Investigate the database error
You > start chain researcher,writer | Research and write a report
You > start parallel researcher,planner | Analyze the project independently
You > start team researcher,planner,writer turns=3 | Produce a proposal
```

Durable independent-mode steps currently execute one at a time through AIKA's
single managed worker. Their inputs remain independent; the command does not yet
provide concurrent background model calls.

### Inspect and control runs

```text
You > list orchestrations
You > show orchestration <run_id>
You > cancel orchestration <run_id>
You > resume orchestration <run_id>
```

`show` includes persisted step status, attempt counts, generic errors, and the
bounded final result. `resume` approves an interrupted run or creates a new
revision for an explicitly retried failed step. Completed and cancelled runs
cannot be resumed.

### High-permission tools

High-permission tools are denied for durable runs by default. To request them:

```text
You > start chain --allow-high planner,writer | Update the approved files
You > approve orchestration <run_id>
```

Use `reject orchestration <run_id>` to cancel instead. Approval applies to the
named run, its agents, and its bounded task; it is not a global permission
change. If AIKA stops while an unsafe step is running, the job waits for another
explicit approval before repeating that step.

---

## OS Commands

### Run shell commands

```
You > run pip install requests
AIKA > (stdout/stderr/exit code)

You > run python -c "print('hello')"
AIKA > hello

You > run dir /s *.py
AIKA > (lists all Python files recursively)
```

Commands run without a system shell by default. Pipes, redirects, command
chaining, and other shell operators are rejected unless
`SHELL_UNSAFE_ENABLED=true` and the tool call explicitly requests unsafe mode.
Working directories must remain in `SHELL_ALLOWED_WORKDIRS` beneath the
workspace. Dangerous commands remain blocked, and shell execution remains a
high-permission operation requiring confirmation when configured.

### Open applications

Beyond the built-in aliases, AIKA finds *any* installed application by scanning the Windows Registry, Start Menu, and Microsoft Store apps.

```
You [a3f2] > open spotify
AIKA > Opened spotify

You [a3f2] > open chrome
AIKA > Opened chrome

You [a3f2] > open vscode
AIKA > Opened vscode
```

### List directories

```
You > list src/
AIKA > src/
       brain/
       config/
       handlers/
       ...

You > show files
AIKA > (lists current directory)
```

### System information

```
You > system info
AIKA > OS: Windows 10 10.0.19045
       Python: 3.12.0
       CPU: 23% used (16 logical cores)
       RAM: 62% used (16 GB / 32 GB)
       Disk: 45% used (200 GB / 500 GB)
       Uptime: 5d 12h 34m
```

---

## Calculator

Just type a math expression.

```
You > 2 + 2
AIKA > 4

You > (15 * 3) / 2
AIKA > 22.5

You > 2 ** 10
AIKA > 1024
```

---

## Configuration

All settings can be viewed and changed at runtime.

### View settings

```
You > !settings
AIKA > chat_model = qwen2.5:3b
       fast_model = qwen2.5:3b
       smart_model = llama3:8b
       ...
```

### View settings by category

```
You > !settings llm
AIKA > chat_model = qwen2.5:3b
       fast_model = qwen2.5:3b
       smart_model = llama3:8b
       native_tool_calling = True
       streaming_enabled = True
       ...

You > !settings safety
AIKA > tool_call_confirm_high = True
       audit_log_enabled = True
       audit_log_path = logs/audit.log
       protected_paths = .env,.git,.gitignore,*.key,*.pem,*.env
```

Available categories: `llm`, `database`, `memory`, `context`, `conversation`, `web`, `planner`, `validation`, `tools`, `paths`, `os`, `persona`, `logging`, `safety`

### Change a setting

```
You > !set CHAT_MODEL=llama3.1:8b
AIKA > chat_model changed from qwen2.5:3b to llama3.1:8b. Use !save to persist.

You > !set LOG_LEVEL=INFO
AIKA > log_level changed from DEBUG to INFO. Use !save to persist.
```

Changes take effect immediately but are lost on restart unless saved.

### Persist settings

```
You > !save
AIKA > Settings saved to .env.
```

### Reload settings

Reloads all values from `.env`, discarding runtime changes.

```
You > !reload
AIKA > Settings reloaded from environment.
```

### Model switching

View and switch between fast and smart models:

```
You > !model
AIKA > Models:
         fast:  qwen2.5:3b
         smart: llama3:8b
         chat:  llama3:8b

You > !model fast qwen2.5:3b
AIKA > Model fast: qwen2.5:3b -> qwen2.5:3b
```

### List available models

```
You > !model list
AIKA > Available Ollama models:
         qwen2.5:3b
         llama3:8b
         nomic-embed-text
```

### Log level

```
You > !log
AIKA > Current log level: DEBUG
       Usage: !log <level>
       Levels: debug, info, warning, error

You > !log warning
AIKA > Log level: DEBUG -> WARNING
```

---

## Persona

AIKA's personality is defined in a plain text file. The default persona is in `src/config/persona.txt`. Each agent has its own persona file in `src/config/personas/`.

### View current persona

```
You > !persona
AIKA > Current persona:

       You are AIKA — a warm, intelligent AI companion with memory.

       PERSONALITY:
       - Warm, friendly, and conversational — like a close friend
       - Natural and human, never robotic or scripted
       ...
```

### Reload after editing

1. Edit the persona file in any text editor
2. Run this without restarting:

```
You > !persona reload
AIKA > Persona reloaded.
```

### Switch persona files

```
You > !set PERSONA_PATH=src/config/my_custom_persona.txt
You > !persona reload
AIKA > Persona reloaded.
```

### View agent-specific persona

```
You > show agent persona researcher
AIKA > researcher persona:
       You are a research specialist. Focus on gathering accurate information...
```

### Set agent persona

```
You > set agent persona writer src/config/personas/writer.txt
AIKA > Persona for 'writer' set to src/config/personas/writer.txt
```

---

## Safety & Audit

### Confirmation prompts

High-risk tools (file_delete, file_write, shell) require user confirmation when `TOOL_CALL_CONFIRM_HIGH=true` (default):

```
You > delete src/old_file.txt
AIKA > Confirm deletion of src/old_file.txt? (y/n):
```

### Audit logging

All tool calls are logged to `logs/audit.log` in JSONL format when `AUDIT_LOG_ENABLED=true` (default). Each entry includes timestamp, tool name, parameters, result status, and agent_id.

### Protected paths

Files matching protected patterns cannot be written or deleted:

```
You > delete .env
AIKA > Error: File is protected: .env

You > write *.key content
AIKA > Error: File is protected: *.key
```

Default protected patterns: `.env`, `.git`, `.gitignore`, `*.key`, `*.pem`, `*.env`

### Strengthened shell blocklist

Dangerous shell commands are blocked by default. The blocklist includes patterns for:

- File destruction: `rm -rf`, `rmdir /s`, `Remove-Item -Recurse`
- Disk formatting: `format`, `mkfs`
- System operations: `shutdown`, `bcdedit`, `diskpart`
- Registry: `reg add`, `reg delete`
- User management: `net user`, `net localgroup`
- Encoding: `certutil`

---

## Error Recovery

### Shell commands timeout

If a command runs too long, it's killed automatically. Adjust the timeout:

```
You > !set SHELL_TIMEOUT=60
```

### Blocked command

If a command is falsely blocked, check the keyword list:

```
You > !settings os
AIKA > shell_enabled = True
        shell_unsafe_enabled = False
        shell_timeout = 30
        shell_allowed_workdirs = ['.']
        shell_blocked_keywords = ['rm -rf', 'format', ...]
        app_launcher_enabled = True
        app_launcher_uwp_enabled = True
```

### Database connection

If AIKA can't connect to the database, check `DATABASE_URL` in `.env` and verify PostgreSQL is running.

### LLM not responding

```
You > !set OLLAMA_HOST=http://localhost:11434
You > !reload
```

Also confirm Ollama is running (`ollama serve`) and the model is pulled (`ollama pull qwen2.5:3b`).

### Model not found

```
You > !model list
AIKA > Available Ollama models:
         qwen2.5:3b
         llama3:8b
         nomic-embed-text
```

Pull missing models: `ollama pull <model_name>`

---

## Testing

### Run the test suite

```bash
python tests/test_all.py                  # All 108 tests (mocked, ~1.5s)
python tests/test_all.py --verbose        # Show input/output per test
python tests/test_all.py --list           # List all test names
python tests/test_all.py --category "Memory System"  # Run one category
python tests/test_all.py --live           # Real integration (needs Ollama + PostgreSQL)
```

### 15 test categories

Settings & Config, Memory System, Tools (Math, File Ops, Web, System, Memory), Agent System, Brain & Routing, Agent Loop & Tool Calling, Orchestration, Safety, Streaming, Planner & Research, Live Integration.

### Live integration tests

The `--live` flag runs 8 tests against real Ollama and PostgreSQL. These tests auto-skip if the services aren't available.

### Feature tour

```bash
python tests/demo.py                      # Guided 11-section tour (no dependencies)
```

---

## Exit

```
You > exit
```
