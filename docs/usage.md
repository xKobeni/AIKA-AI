# AIKA — Usage Guide

Practical examples for every feature. Run AIKA with `python src\main.py`.

---

## Chat

Just type naturally. AIKA responds with context from your memories and recent conversation.

```
You > hello Aika
AIKA > Hey! How's it going?

You > what's the weather like?
AIKA > Let me check... (automatically searches the web)
```

---

## Memory

AIKA auto-extracts memories from your messages, but you can also manage them manually.

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

All file operations are sandboxed to `FILE_SEARCH_ROOT_PATH` (default: the project root). Path traversal is blocked.

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

You > read .env
AIKA > (returns .env content)
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
```

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

Dangerous commands (rm -rf, format, shutdown, etc.) are blocked by default.

### Open applications

Beyond the built-in aliases, AIKA finds *any* installed application by scanning the Windows Registry, Start Menu, and Microsoft Store apps.

```
You [a3f2] > open spotify
AIKA > Opened spotify

You [a3f2] > open chrome
AIKA > Opened chrome

You [a3f2] > open vscode
AIKA > Opened vscode

You [a3f2] > open notepad
AIKA > Opened notepad

You [a3f2] > open calculator
AIKA > Opened calculator

You [a3f2] > open settings
AIKA > Opened settings
```

### List directories

```
You > list src/
AIKA > src/
       brain/
       config/
       handlers/
       ...

You > list src/brain/
AIKA > brain/
       __init__.py
       brain.py
       router.py
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

You > how's my system
AIKA > (same output)

You > system health
AIKA > (same output)
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

You > 100 / 3
AIKA > 33.333...
```

---

## Configuration

All settings can be viewed and changed at runtime.

### View settings

```
You > !settings
AIKA > chat_model = qwen2.5:3b
       embedding_model = nomic-embed-text
       ollama_host = http://localhost:11434
       ...
```

### View settings by category

```
You > !settings llm
AIKA > chat_model = qwen2.5:3b
       embedding_model = nomic-embed-text
       ollama_host = http://localhost:11434
       llm_timeout = 30

You > !settings memory
AIKA > memory_retrieval_limit = 8
       memory_min_score = 0.3
       ...
```

Available categories: `llm`, `database`, `memory`, `context`, `conversation`, `web`, `planner`, `validation`, `tools`, `paths`, `os`, `persona`, `logging`

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

---

## Persona

AIKA's personality is defined in `src/config/persona.txt`. You can view and reload it without restarting.

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

1. Edit `src/config/persona.txt` in any text editor
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
        shell_timeout = 30
        shell_blocked_keywords = ['rm -rf', 'format', ...]
        app_launcher_enabled = True
        app_launcher_uwp_enabled = True
```

If the app launcher's UWP scan is too slow, toggle it off with `!set APP_LAUNCHER_UWP_ENABLED=false`.

### Database connection

If AIKA can't connect to the database, check `DATABASE_URL` in `.env` and verify PostgreSQL is running.

### LLM not responding

```
You > !set OLLAMA_HOST=http://localhost:11434
You > !reload
```

Also confirm Ollama is running (`ollama serve`) and the model is pulled (`ollama pull qwen2.5:3b`).

---

## Exit

```
You > exit
```
