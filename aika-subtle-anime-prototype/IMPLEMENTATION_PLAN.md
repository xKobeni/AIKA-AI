# AIKA Subtle-Anime Companion Prototype — Implementation Plan

Status: **Phases 1–5 and the calm-density design revision are implemented for review. Final responsive and accessibility verification remains in Phase 6.**

## 1. Intended outcome

Create a new standalone HTML/CSS/JavaScript prototype that feels unmistakably like AIKA: a friendly, observant, capable companion who keeps Adrian updated and works beside him.

The design will carry a subtle modern-anime atmosphere without becoming a visual novel, game HUD, character collection screen, or character portrait pasted onto a conventional chatbot.

The interface should communicate three things within the first few seconds:

1. **AIKA is present.** Her character and current state are visible but do not consume the entire interface.
2. **AIKA understands the ongoing context.** She surfaces useful memories, unfinished threads, and current priorities naturally.
3. **AIKA is doing useful work.** Updates show what she finished, found, scheduled, remembered, or needs approval for.

## 2. Core concept: AIKA’s Living Desk

The interface is a shared personal workspace rather than a chat screen.

### Main composition

- **AIKA Presence** — A restrained half-body character occupies roughly 20–25% of the desktop viewport. She is part of the environment, not a full-screen portrait.
- **Companion Pulse** — The primary surface shows AIKA-authored updates such as “I finished checking…”, “Your reminder is coming up…”, “I kept this project thread…”, or “I need your approval before continuing.”
- **Thought Ribbon** — A minimal persistent input invites natural language: “Tell AIKA what’s on your mind.” Responses appear conversationally in the current surface rather than opening a conventional bubble transcript.
- **Constellation Dock** — A compact navigation element opens AIKA’s functional spaces without a permanent sidebar.
- **Ambient Context** — Date, local status, current model lane, privacy, and active work appear as quiet environmental signals rather than dashboard metrics.

### Why this should feel different

- The home screen begins with AIKA’s awareness and updates, not an empty prompt.
- AIKA speaks through short first-person notices supported by honest system metadata.
- Features are organized around the relationship and ongoing work, not product categories.
- The character changes with system state instead of remaining static decoration.
- Conversation, memory, reminders, research, tools, and agents all return to the same shared surface.

## 3. Anime influence: subtle, not overwhelming

### Character treatment

- One consistent **adult anime-style AIKA character**.
- Modern, calm, observant, and approachable—not hyper-cute, chibi, romanticized, or mascot-like.
- Half-body or waist-up presentation with generous negative space.
- Three expression assets for the prototype:
  - **Present:** relaxed, gentle neutral expression.
  - **Bright:** small warm smile for greetings and completed work.
  - **Focused:** attentive expression for research, planning, tools, and approvals.
- Character artwork stays secondary to the current update or task.
- No speech bubbles, exaggerated reaction symbols, school-uniform styling, animal ears, fan-service styling, or neon cyberpunk clutter.

### Interface cues

- Fine linework and subtle cel-shaded accent panels.
- Soft asymmetric framing inspired by illustrated editorial layouts.
- Small amber “presence light” shared between AIKA’s accessory and interface status signals.
- Gentle sage, charcoal, warm ivory, muted clay, and amber palette.
- Motion limited to breathing light, slight character drift, soft state transitions, and restrained eye-line emphasis.
- No Japanese text used decoratively; the anime feeling should come from composition and illustration, not imitation.

## 4. AIKA personality expressed through interface behavior

The character alone will not carry the personality. The interface must make AIKA behave like a good companion.

### Friendly presence

- Time-aware greeting that acknowledges continuity: “Good evening. I kept our place.”
- One gentle observation instead of generic suggestions.
- Natural invitations such as “Want to continue this?” or “We can leave this for later.”
- Occasional light playfulness, used sparingly and never during errors or sensitive actions.

### Proactive updates

AIKA’s home surface will support these update types:

| Update type | Example voice | Visual behavior |
|---|---|---|
| Completed | “I finished organizing the response review.” | Bright expression, sage completion mark |
| Reminder | “Your prototype review is tomorrow at 9:00 AM.” | Calm expression, amber time marker |
| Memory | “I kept your preference for incremental fixes in mind.” | Present expression, subtle memory thread |
| Research | “I found seven useful sources. Three look especially relevant.” | Focused expression, visible source trail |
| Progress | “The evaluation is four of six steps through.” | Focused expression, quiet progress line |
| Approval | “I’m ready to continue, but this step needs your approval.” | Focused expression, clear protected-action card |
| Error/limitation | “The local model is unavailable. I haven’t completed the request.” | Neutral expression, plain recovery action |
| Suggestion | “There’s a smaller way to approach this.” | Present expression, one optional next step |

### Honesty and boundaries

- Every sample result is labeled as prototype data.
- Tool, model, memory, and source use remain observable.
- AIKA never says an action succeeded without a successful result state.
- Warmth must not imply consciousness, real emotions, dependency, or a human personal life.
- High-risk actions always surface a clear approval step.

## 5. Information architecture

The constellation dock will contain seven spaces. Names are relational but remain understandable.

### 1. Together

The companion home and current conversation surface.

- Companion Pulse update feed
- Thought Ribbon input
- Streaming-response state
- Current session and continuity
- Tool activity, model lane, memory-use, and source signals
- Approval and cancellation states

### 2. Memory Garden

Long-term context presented as connected fragments rather than a database table.

- Remembered preferences
- Project threads
- User profile context
- Relevant-memory explanation
- Search, inspect, and remove controls
- Session summaries and source-conversation links

### 3. Dayline

Tasks and time-based work shown as a calm personal timeline.

- Plans and next steps
- One-time and recurring reminders
- Due and acknowledged occurrences
- Durable background jobs
- Progress, retry, pause, cancellation, and restart recovery
- Persistent orchestration runs and approval waits

### 4. Crew

AIKA’s specialized agents shown as collaborators she can bring into the work.

- AIKA coordinator
- Researcher
- Planner
- Writer
- Delegate, chain, parallel, and team modes
- Agent model, persona, and permitted tools
- Clear ownership of each active step

### 5. Research Trail

Research organized around findings and evidence.

- Reflexive web search
- Multi-step research
- Crawled pages
- Relevance-ranked sources
- Structured reports
- Follow-up questions that reuse existing sources when appropriate
- Saved research in the library

### 6. Workshop

Tools and operating-system capabilities presented as actions AIKA can carefully perform.

- Calculator
- File search, read, ranges, write, edit, append, grep, mkdir, and delete
- Shell execution
- App launching
- Folder browsing
- System information
- Git operations
- Test runner
- Tool permission level, confirmation, and audit state

### 7. Inner Room

Transparent system and personality controls.

- Local Ollama models
- Fast/smart automatic model routing
- Native tool calling and fallback mode
- Streaming preference
- Memory and context settings
- Editable AIKA persona
- Per-agent configuration
- Protected paths, audit logging, and command safety
- Runtime lifecycle and service status
- Light/dark appearance

## 6. Layout plan

### Desktop

- **Top ambient bar:** AIKA identity, local/private state, current time, appearance toggle.
- **Left character zone (20–25%):** waist-up AIKA with current expression and a small plain-language state label.
- **Center living surface (50–55%):** Companion Pulse and the selected feature space.
- **Right awareness rail (20–25%):** upcoming reminder, active task, relevant memory, and one useful observation. This rail changes with the selected space.
- **Bottom:** Thought Ribbon plus the Constellation Dock.

The layout will use open space and asymmetry. It must not resemble a three-column analytics dashboard; the boundaries between zones will be soft and editorial rather than boxed.

### Tablet

- Character reduces to a bust portrait beside the current AIKA update.
- Awareness rail becomes a horizontally scrollable context strip.
- Dock remains fixed and touch-friendly.

### Mobile

- Compact character portrait and AIKA update share the first viewport.
- Thought Ribbon stays reachable above the dock.
- Feature spaces become full-width scenes.
- Secondary context appears as expandable cards.
- No desktop sidebar is introduced.

## 7. Visual design system

### Color

Two complete themes:

- **Twilight:** charcoal, warm black, muted sage, amber, soft ivory.
- **Daylight:** warm paper, ink gray, moss green, muted terracotta, restrained amber.

Accent colors communicate meaning:

- Sage: ready, safe, complete
- Amber: attention, reminder, active thinking
- Clay: approval or careful action
- Muted plum: memory and continuity
- Red only for genuine destructive or failed states

### Typography

- Humanist sans-serif for controls and system clarity.
- Restrained editorial serif for AIKA’s short companion voice.
- AIKA’s words remain readable and calm; no handwritten novelty font.
- Compact metadata never falls below accessible reading sizes in the final implementation.

### Shape and texture

- Mostly borderless surfaces with occasional fine dividers.
- Softly asymmetric corners on AIKA-authored updates.
- Minimal paper-like grain created in CSS.
- Character frame blends into the environment instead of resembling a profile card.
- No excessive glassmorphism, gradients, glowing neon, or rows of identical dashboard cards.

### Motion

- 180–320 ms interface transitions.
- Character expression cross-fade rather than abrupt image replacement.
- Small presence-light pulse while listening.
- Slow line movement while thinking or performing work.
- Streaming text only for the final user-visible response.
- Full `prefers-reduced-motion` support.

## 8. Interaction and state model

AIKA will have these visible UI states:

| State | Character | Interface signal | Required text behavior |
|---|---|---|---|
| Present | Present expression | Slow sage presence light | Natural greeting or observation |
| Listening | Present expression | Focus ring around Thought Ribbon | No fake processing claim |
| Thinking | Focused expression | Amber moving line | State what AIKA is considering only at a high level |
| Using a tool | Focused expression | Named tool activity | Show tool name and permission level |
| Researching | Focused expression | Source trail grows | Show search/crawl progress and sources |
| Needs approval | Focused expression | Clay protected-action panel | Explain the exact action and consequence |
| Complete | Bright expression | Sage completion transition | Preserve successful result visibly |
| Limited/error | Present expression | Plain recovery panel | Say what failed and what remains known |
| Offline/local unavailable | Present expression | Muted presence light | Never imply the request completed |

## 9. Prototype implementation structure

After approval, implementation will be created in this folder without changing the earlier prototypes:

```text
aika-subtle-anime-prototype/
├── IMPLEMENTATION_PLAN.md
├── index.html
├── styles.css
├── script.js
└── assets/
    └── aika/
        ├── present.png
        ├── bright.png
        └── focused.png
```

Technical boundaries:

- Plain HTML, CSS, and JavaScript only.
- No framework, package installation, external font, or icon dependency.
- No connection to PostgreSQL, Ollama, live tools, or the operating system.
- Local storage only for appearance and harmless prototype preferences.
- Sample data will demonstrate the real AIKA capabilities without pretending they are live.
- Character assets will be generated only after the character direction is approved.

## 10. Phased implementation sequence

Implementation will stop after each review gate if Adrian asks for phase-by-phase approval.

### Phase 1 — Visual foundation and first meaningful preview

**Implementation status: complete for review.**

- Create the new standalone folder structure.
- Implement Twilight and Daylight design tokens.
- Build the desktop shell, AIKA character zone, one Companion Pulse update, Thought Ribbon, and Constellation Dock.
- Use one temporary character treatment only until the final three expressions are approved.
- Verify the page loads and open the first recognizable preview.

**Review gate:** Does the interface feel like a subtle anime companion rather than a chatbot or visual novel?

### Phase 2 — Companion behavior

**Implementation status: complete for expanded prototype review.**

- Add present, listening, thinking, complete, approval, and error states.
- Implement time-aware greetings and sample continuity.
- Add friendly proactive updates and state-to-expression transitions.
- Add Thought Ribbon interaction and simulated streaming response.

**Review gate:** Does AIKA’s friendliness come from behavior, not merely the character image?

### Phase 3 — Core personal spaces

**Implementation status: complete for expanded prototype review.**

- Implement Together, Memory Garden, and Dayline.
- Add sample memories, session continuity, reminders, jobs, progress, and orchestration.
- Ensure every update can explain why it appeared.

**Review gate:** Are the most personal AIKA features useful without becoming a dashboard?

### Phase 4 — Capability spaces

**Implementation status: complete for expanded prototype review.**

- Implement Crew, Research Trail, Workshop, and Inner Room.
- Represent all documented agents, tools, research, models, configuration, persona, and safety features.
- Add approvals, source trails, model/tool labels, and system limitations.

**Review gate:** Are all system features discoverable while the interface remains calm?

### Phase 5 — Character assets and refinement

**Implementation status: complete for expression-system review.**

- Generate the approved adult AIKA character in calm, talking, happy, sad, and controlled angry/protective expressions.
- Preserve identity, outfit, palette, crop, and proportions across expressions.
- Integrate non-destructively and verify asset edges and responsive crops.
- Refine animation, theme consistency, copy, and empty states.

**Review gate:** Does AIKA look consistent and recognizable across states without overpowering the workspace?

### Phase 6 — Responsive and accessibility verification

- Verify keyboard navigation, focus visibility, readable contrast, labels, live regions, and reduced motion.
- Check desktop, tablet, and mobile layouts.
- Validate JavaScript syntax, navigation/state parity, unique IDs, asset loading, and local HTTP responses.
- Clearly identify every simulated feature.

## 11. Acceptance criteria

The prototype is complete only when:

- The first viewport does not resemble ChatGPT, Claude, or a typical sidebar-and-chat layout.
- Anime influence is recognizable but restrained.
- AIKA’s character occupies no more than roughly one quarter of the desktop working area.
- Friendliness is demonstrated through updates, continuity, wording, and useful suggestions.
- AIKA never implies human consciousness or fabricated memory.
- All documented AIKA feature families are represented and reachable.
- Successful work, approvals, sources, memory use, model/tool activity, and failures remain visible.
- Twilight and Daylight themes both feel intentional and persist locally.
- The interface works at desktop, tablet, and mobile widths.
- Reduced-motion and keyboard use remain supported.
- No live service or operating-system action occurs in the prototype.
- Previous prototype folders remain unchanged.

## 12. Review decisions requested before implementation

Please approve or change these three design decisions:

1. **Character presence:** adult waist-up AIKA using approximately 20–25% of the desktop viewport.
2. **Visual tone:** charcoal/ivory/sage/amber with subtle anime editorial composition and no visual-novel chrome.
3. **Home experience:** Companion Pulse updates are primary; conversation is available through the Thought Ribbon rather than a chat transcript.

Adrian approved implementation and then requested the full feature layer, larger typography, and a collapsible awareness sidebar. The prototype therefore implements Phases 1–4 while preserving Phases 5–6 as separate review gates.
