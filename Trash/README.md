# Legacy Archive

This directory contains an early JSON-based memory and conversation implementation retained only as a historical snapshot:

- `conversations.json`
- `memories.json`
- `memory_manager.py`

These files are not imported or used by the current AIKA runtime. Active conversations and memories are stored in PostgreSQL, while agent profiles are persisted separately in `data/agents.json`.

Do not treat the JSON files here as a backup of the current database. They remain in place for manual historical recovery and can be removed in a future housekeeping phase after their retention value is reviewed.
