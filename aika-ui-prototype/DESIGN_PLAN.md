# AIKA Interface Prototype — Design Plan

## Goal

Create a calm, minimalist desktop interface that makes AIKA feel like a personal companion rather than a conventional dashboard. The conversation is the primary surface; memory, tools, tasks, and system state remain available without competing for attention.

## Experience principles

1. **Conversation first** — The current exchange owns the largest area of the screen.
2. **Quiet intelligence** — AIKA's activity is shown through small, readable status cues instead of dense diagnostics.
3. **Personal, not corporate** — Warm copy, generous spacing, soft geometry, and restrained color make the interface feel familiar.
4. **Progressive disclosure** — Secondary detail appears only when a person opens a panel or selects a workspace.
5. **Trust through clarity** — Local model, memory use, sources, and tool activity are visible in plain language.

## Visual direction

- Dark graphite canvas with warm off-white text.
- One restrained sage accent for focus, active states, and AIKA's presence.
- Border-led surfaces with minimal shadows and no decorative gradients.
- Rounded rectangles, generous whitespace, and compact typography.
- A small animated presence mark instead of a character illustration or logo-heavy treatment.

## Layout

- **Left rail:** AIKA identity, primary destinations, recent conversations, and user profile.
- **Main conversation:** greeting, contextual prompt suggestions, conversation thread, and a persistent composer.
- **Context panel:** current session details, active memory, upcoming reminders, and privacy/model state.
- On narrow screens, the left rail becomes a drawer and the context panel moves below the conversation.

## Full-system workspace map

- **Conversation:** streaming-style replies, model mode, tool activity, approvals, and source signals.
- **Memory:** extracted memories, user preferences, project context, and profile-aware recall.
- **Tasks:** plans, reminders, durable background jobs, and persistent orchestration runs.
- **Agents:** coordinator, researcher, planner, and writer profiles with delegation, chain, parallel, and team modes.
- **Research:** research prompts, multi-source progress, ranked sources, and saved reports.
- **Library:** saved answers, research reports, notes, and generated work.
- **System:** a complete capability map covering local models, tools, operating-system access, safety, lifecycle, and configuration.
- **Settings:** appearance, model routing, memory, streaming, native tools, persona, privacy, and permission preferences.

## Prototype interactions

- Send a message and receive a short simulated AIKA response.
- Use suggestion chips to populate and submit common prompts.
- Switch between Chat, Memory, Tasks, and Library views.
- Explore Agents, Research, System, and Settings views.
- Start a fresh conversation.
- Collapse or reopen the navigation on smaller screens.
- Open or close the contextual details panel.
- Keyboard support: `Enter` sends, `Shift+Enter` creates a new line, and `/` focuses the composer.
- Toggle between dark and light appearance; the choice persists in local browser storage.
- Change prototype setting switches and run a sample research interaction.

## Content strategy

Use AIKA-specific language and realistic capabilities from the current project: local Ollama inference, long-term memory, reminders, research sources, tools, sessions, and privacy. Avoid presenting prototype data as live system state.

## Implementation boundaries

- Plain HTML, CSS, and JavaScript only.
- No frameworks, external fonts, icon libraries, network calls, or backend integration.
- Responsive and keyboard-accessible.
- All visible system data is explicitly framed as prototype/sample state.
