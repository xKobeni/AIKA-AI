# Local AIKA Skills

AIKA skills are local, declarative instruction packages. A skill can guide how
AIKA approaches a task, but it cannot add tools, expand an agent's permissions,
run bundled scripts automatically, or connect to external services.

## Directory layout

Place each skill in a direct child directory of `SKILLS_PATH` (the default is
`skills`):

```text
skills/
└── research_assistant/
    ├── skill.json
    └── SKILL.md
```

The directory and manifest ID must use the same lowercase identifier.

## Manifest

```json
{
  "id": "research_assistant",
  "name": "Research Assistant",
  "description": "Conducts structured web research.",
  "version": "1.0",
  "required_tools": ["web_search", "web_crawl"],
  "allowed_agents": ["aika"],
  "enabled": true
}
```

`allowed_agents` is optional. If omitted, the skill may be used by any agent
that already has all of its required tools. `enabled` is optional and defaults
to `true`.

`SKILL.md` contains the task-specific instructions. Its contents are inserted
through AIKA's shared prompt budget and cannot override grounding, safety, or
tool-permission rules. Script references remain text; Phase 9 does not execute
skill-provided scripts.

## Commands

```text
list skills
show skill <id>
use skill <id>
deactivate skill
reload skills
```

Activation is explicit and belongs to the current conversation session. A new
session starts without a skill. Resuming an earlier session during the same AIKA
process restores that session's in-memory activation. Activations are not stored
in the database and do not survive an application restart.

## Limits

The following environment settings are read at startup:

- `SKILLS_PATH` (default `skills`)
- `SKILL_MAX_COUNT` (default `100`)
- `SKILL_MAX_MANIFEST_BYTES` (default `16384`)
- `SKILL_MAX_INSTRUCTION_BYTES` (default `12000`)

Use `reload skills` after editing a package. Invalid packages are rejected
individually and reported by `list skills`; they do not prevent AIKA from
starting or other valid skills from loading.
