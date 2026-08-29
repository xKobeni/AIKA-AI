const root = document.documentElement;
const body = document.body;
const themeSwitch = document.getElementById("themeSwitch");
const railToggle = document.getElementById("railToggle");
const railClose = document.getElementById("railClose");
const moreToggle = document.getElementById("moreToggle");
const moreMenu = document.getElementById("moreMenu");
const activeSpaceName = document.getElementById("activeSpaceName");
const activeSpaceIcon = document.getElementById("activeSpaceIcon");
const thoughtForm = document.getElementById("thoughtForm");
const thoughtInput = document.getElementById("thoughtInput");
const thoughtStatus = document.getElementById("thoughtStatus");
const spaceKicker = document.getElementById("spaceKicker");
const characterPresence = document.querySelector(".character-presence");
const characterPortrait = document.getElementById("characterPortrait");
const characterMotionPortrait = document.getElementById("characterMotionPortrait");
const characterState = document.getElementById("characterState");
const expressionCycle = document.getElementById("expressionCycle");
const expressionName = document.getElementById("expressionName");
const voiceToggle = document.getElementById("voiceToggle");
const voiceSession = document.getElementById("voiceSession");
const voicePhase = document.getElementById("voicePhase");
const voicePrompt = document.getElementById("voicePrompt");
const voiceTranscript = document.getElementById("voiceTranscript");
const voiceTimer = document.getElementById("voiceTimer");
const voiceCancel = document.getElementById("voiceCancel");
const voicePause = document.getElementById("voicePause");
const voiceAdvance = document.getElementById("voiceAdvance");
const workDemo = document.getElementById("workDemo");
const workPresence = document.getElementById("workPresence");
const workTitle = document.getElementById("workTitle");
const workSentence = document.getElementById("workSentence");
const workTimer = document.getElementById("workTimer");
const workHonesty = document.getElementById("workHonesty");
const workStop = document.getElementById("workStop");
const workResultTurn = document.getElementById("workResultTurn");
const conversationJournal = document.getElementById("conversationJournal");
const conversationDayTime = document.getElementById("conversationDayTime");
const emptySessionState = document.getElementById("emptySessionState");
const emptySessionKicker = document.getElementById("emptySessionKicker");
const emptySessionCopy = document.getElementById("emptySessionCopy");
const companionPulse = document.querySelector(".companion-pulse");
const olderTurnsToggle = document.getElementById("olderTurnsToggle");
const jumpLatest = document.getElementById("jumpLatest");
const globalWorkIndicator = document.getElementById("globalWorkIndicator");
const globalWorkText = document.getElementById("globalWorkText");
const composerAdd = document.getElementById("composerAdd");
const composerTray = document.getElementById("composerTray");
const attachFileAction = document.getElementById("attachFileAction");
const attachmentInput = document.getElementById("attachmentInput");
const comfortTextToggle = document.getElementById("comfortTextToggle");
const workResume = document.getElementById("workResume");
const conversationSearchToggle = document.getElementById("conversationSearchToggle");
const conversationSearchPanel = document.getElementById("conversationSearchPanel");
const conversationSearchInput = document.getElementById("conversationSearchInput");
const conversationSearchStatus = document.getElementById("conversationSearchStatus");
const conversationSearchClose = document.getElementById("conversationSearchClose");
const conversationSummarize = document.getElementById("conversationSummarize");
const conversationMoreToggle = document.getElementById("conversationMoreToggle");
const conversationMoreMenu = document.getElementById("conversationMoreMenu");
const conversationHistoryToggle = document.getElementById("conversationHistoryToggle");
const sessionHistoryPanel = document.getElementById("sessionHistoryPanel");
const sessionHistoryClose = document.getElementById("sessionHistoryClose");
const sessionHistoryNew = document.getElementById("sessionHistoryNew");
const sessionHistoryCount = document.getElementById("sessionHistoryCount");
const sessionHistorySearch = document.getElementById("sessionHistorySearch");
const sessionHistoryList = document.getElementById("sessionHistoryList");
const sessionHistoryEmpty = document.getElementById("sessionHistoryEmpty");
const sessionHistoryFilters = [...document.querySelectorAll("[data-history-filter]")];
const conversationNewSession = document.getElementById("conversationNewSession");
const voicePreference = document.getElementById("voicePreference");
const voiceRate = document.getElementById("voiceRate");
const voiceRateValue = document.getElementById("voiceRateValue");
const voiceInputMode = document.getElementById("voiceInputMode");
const interruptSensitivity = document.getElementById("interruptSensitivity");
const interruptValue = document.getElementById("interruptValue");
const autoSpeakToggle = document.getElementById("autoSpeakToggle");
const captionsToggle = document.getElementById("captionsToggle");

let currentSpace = "together";
let responseTimer;
let portraitSwapTimer;
let motionReturnTimer;
let characterBlinkTimer;
let currentCharacterMotion = "idle";
let expressionIndex = 0;
let voiceClock;
let voiceTranscriptClock;
let voiceStageTimer;
let voiceElapsed = 0;
let workClock;
let workStageClock;
let workElapsed = 0;
let workStage = -1;
let speechRecognition;
let speechIsLive = false;
let liveVoiceTranscript = "";
let voiceOutputPaused = false;
let conversationRecords = [];
let sessionStore = { activeSessionId: "", sessions: [] };
let activeStream = null;
let messageSequence = 0;
let attachmentReplaceTargetId = "";
let activeHistoryFilter = "all";
let voiceSettings = {
  voiceName: "",
  rate: 0.95,
  inputMode: "push",
  sensitivity: 2,
  autoSpeak: true,
  captions: true,
};

const expressions = {
  calm: {
    src: "assets/aika/expression-calm-matte.png",
    label: "Calm",
    state: "present with you",
  },
  talking: {
    src: "assets/aika/expression-talking-matte.png",
    label: "Talking",
    state: "speaking with you",
  },
  happy: {
    src: "assets/aika/expression-happy-matte.png",
    label: "Happy",
    state: "bright response",
  },
  sad: {
    src: "assets/aika/expression-sad-matte.png",
    label: "Sad",
    state: "gentle concern",
  },
  angry: {
    src: "assets/aika/expression-angry-matte.png",
    label: "Angry",
    state: "protective focus",
  },
};

const expressionOrder = Object.keys(expressions);

const characterMotionLabels = {
  idle: "present with you",
  listening: "listening closely",
  thinking: "thinking beside you",
  talking: "speaking with you",
  working: "focused on the work",
  reaction: "responding naturally",
};

Object.values(expressions).forEach(({ src }) => {
  const preload = new Image();
  preload.src = src;
});

const spaces = {
  together: {
    label: "Together",
    icon: "◉",
    kicker: "Here with you",
    aside: "I’m keeping the important pieces close, without crowding you.",
  },
  memory: {
    label: "Memory",
    icon: "◇",
    kicker: "Memory Garden",
    aside: "These are the details that help me understand your direction over time.",
  },
  dayline: {
    label: "Dayline",
    icon: "⌁",
    kicker: "Dayline",
    aside: "I can hold the rhythm of the day while you focus on the part in front of you.",
  },
  crew: {
    label: "Crew",
    icon: "◎",
    kicker: "AIKA Crew",
    aside: "When a task grows, I can bring in a specialist and still stay beside you.",
  },
  research: {
    label: "Research",
    icon: "↗",
    kicker: "Research Trail",
    aside: "Evidence stays visible here, so a confident answer never hides where it came from.",
  },
  workshop: {
    label: "Workshop",
    icon: "⌘",
    kicker: "Workshop",
    aside: "These are the abilities I can reach for when a conversation needs real action.",
  },
  inner: {
    label: "Inner room",
    icon: "◌",
    kicker: "Inner Room",
    aside: "This is where you decide how I think, what I can touch, and when I should ask first.",
  },
};

const companionReplies = [
  {
    terms: ["feature", "system", "capability", "can you do"],
    title: "You want the whole system to feel visible",
    body: "I’ve opened every space now: memories, reminders, durable jobs, specialist agents, research with sources, tools, models, settings, and safety controls.",
    lead: "We can explore them without leaving this shared desk.",
  },
  {
    terms: ["design", "anime", "style", "interface"],
    title: "The personality should come through quietly",
    body: "I’m keeping the interface restrained: a subtle character presence, softer language, spatial features, and fewer dashboard-like panels.",
    lead: "It should feel like meeting AIKA, not operating a generic chatbot.",
  },
  {
    terms: ["overwhelmed", "stuck", "tired", "too much"],
    title: "Let’s make the next step smaller",
    body: "We don’t need to solve everything at once. Choose one feature space below and I’ll keep the rest of the system quiet until you need it.",
    lead: "One manageable step is enough for now.",
  },
];

function readPreference(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function savePreference(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // The prototype remains usable when storage is unavailable.
  }
}

function setTheme(theme) {
  const daylight = theme === "daylight";
  root.dataset.theme = daylight ? "daylight" : "twilight";
  themeSwitch.querySelector("span").textContent = daylight ? "☾" : "☼";
  themeSwitch.querySelector("small").textContent = daylight ? "Twilight" : "Daylight";
  themeSwitch.setAttribute("aria-label", daylight ? "Switch to Twilight theme" : "Switch to Daylight theme");
  savePreference("aika-living-desk-theme", root.dataset.theme);
}

function setRail(collapsed) {
  body.classList.toggle("rail-collapsed", collapsed);
  railToggle.setAttribute("aria-expanded", String(!collapsed));
  railToggle.querySelector("small").textContent = collapsed ? "Show updates" : "Awareness";
  savePreference("aika-awareness-collapsed-v2", String(collapsed));
}

function setMoreMenu(open) {
  moreMenu.hidden = !open;
  moreToggle.setAttribute("aria-expanded", String(open));
  moreToggle.classList.toggle("is-open", open);
}

function setExpression(name) {
  const expression = expressions[name];
  if (!expression) return;

  expressionIndex = expressionOrder.indexOf(name);
  expressionName.textContent = expression.label;
  if (currentCharacterMotion === "idle" || currentCharacterMotion === "reaction") characterState.textContent = expression.state;
  characterPresence.dataset.expression = name;
  expressionCycle.setAttribute("aria-label", `AIKA expression: ${expression.label}. Select to preview the next expression.`);

  if (characterPortrait.dataset.expression === name) return;

  clearTimeout(portraitSwapTimer);
  characterPortrait.classList.add("is-changing");
  portraitSwapTimer = window.setTimeout(() => {
    characterPortrait.src = expression.src;
    characterPortrait.alt = `AIKA with a ${expression.label.toLowerCase()} expression`;
    characterPortrait.dataset.expression = name;
    window.requestAnimationFrame(() => characterPortrait.classList.remove("is-changing"));
  }, 180);
}

function scheduleCharacterBlink() {
  clearTimeout(characterBlinkTimer);
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || currentCharacterMotion !== "idle") return;
  characterBlinkTimer = window.setTimeout(() => {
    characterPresence.classList.add("is-blinking");
    window.setTimeout(() => {
      characterPresence.classList.remove("is-blinking");
      scheduleCharacterBlink();
    }, 210);
  }, 2800 + Math.random() * 3200);
}

function setCharacterMotion(state, label = characterMotionLabels[state]) {
  clearTimeout(motionReturnTimer);
  currentCharacterMotion = state;
  characterPresence.dataset.motion = state;
  characterState.textContent = label;
  if (state === "idle") scheduleCharacterBlink();
  else {
    clearTimeout(characterBlinkTimer);
    characterPresence.classList.remove("is-blinking");
  }
}

function playCharacterReaction(expressionName) {
  const expression = expressions[expressionName] || expressions.calm;
  setExpression(expressionName);
  setCharacterMotion(expressionName === "calm" ? "idle" : "reaction", expression.state);
  if (expressionName !== "calm") {
    motionReturnTimer = window.setTimeout(() => setCharacterMotion("idle", expression.state), 1400);
  }
}

function expressionForThought(thought) {
  const normalized = thought.toLowerCase();
  if (["angry", "mad", "annoyed", "frustrated", "hate"].some((term) => normalized.includes(term))) return "angry";
  if (["sad", "hurt", "lonely", "tired", "overwhelmed", "upset"].some((term) => normalized.includes(term))) return "sad";
  if (["happy", "great", "excited", "love", "good news", "thank"].some((term) => normalized.includes(term))) return "happy";
  return "calm";
}

function updateAmbientTime() {
  const now = new Date();
  const hour = now.getHours();
  const period = hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
  document.getElementById("timeState").textContent = `${new Intl.DateTimeFormat([], { weekday: "long" }).format(now)} ${period}`;
  document.getElementById("currentDate").textContent = new Intl.DateTimeFormat([], {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(now);
}

function resizeThoughtInput() {
  thoughtInput.style.height = "auto";
  thoughtInput.style.height = `${Math.min(thoughtInput.scrollHeight, 88)}px`;
}

function formatElapsed(seconds) {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function saveVoiceSettings() {
  try { localStorage.setItem("aika-voice-settings-v1", JSON.stringify(voiceSettings)); } catch { /* Defaults remain active. */ }
}

function loadVoiceSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem("aika-voice-settings-v1") || "null");
    if (saved && typeof saved === "object") voiceSettings = { ...voiceSettings, ...saved };
  } catch {
    // Use calm defaults when preferences are unavailable.
  }
  voiceRate.value = String(voiceSettings.rate);
  voiceRateValue.textContent = `${Number(voiceSettings.rate).toFixed(2)}×`;
  voiceInputMode.value = voiceSettings.inputMode;
  interruptSensitivity.value = String(voiceSettings.sensitivity);
  interruptValue.textContent = ["Gentle", "Balanced", "Immediate"][Number(voiceSettings.sensitivity) - 1] || "Balanced";
  autoSpeakToggle.setAttribute("aria-checked", String(voiceSettings.autoSpeak));
  autoSpeakToggle.classList.toggle("is-on", voiceSettings.autoSpeak);
  captionsToggle.setAttribute("aria-checked", String(voiceSettings.captions));
  captionsToggle.classList.toggle("is-on", voiceSettings.captions);
  body.classList.toggle("captions-hidden", !voiceSettings.captions);
}

function populateVoiceOptions() {
  if (!("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  voicePreference.querySelectorAll("option:not(:first-child)").forEach((option) => option.remove());
  voices.forEach((voice) => {
    const option = document.createElement("option");
    option.value = voice.name;
    option.textContent = `${voice.name} · ${voice.lang}`;
    voicePreference.append(option);
  });
  voicePreference.value = voiceSettings.voiceName;
}

function conversationTime() {
  return new Intl.DateTimeFormat([], { hour: "numeric", minute: "2-digit" }).format(new Date());
}

function readConversationRecords() {
  try {
    const saved = JSON.parse(localStorage.getItem("aika-prototype-conversation-v1") || "[]");
    return Array.isArray(saved) ? saved.slice(-30) : [];
  } catch {
    return [];
  }
}

const sessionStorageKey = "aika-prototype-sessions-v2";
const seedConversationRecords = [
  { id: "seed-user", type: "user", text: "Can you show me how the conversation would feel?", meta: "Voice transcript · 00:12" },
  {
    id: "seed-aika",
    type: "aika",
    lead: "I’m here. Let’s keep it natural.",
    title: "The conversation can feel like a shared journal.",
    body: "Your thoughts stay distinct, while my responses remain open and calm. Voice transcripts, active work, and results become part of the same continuous conversation.",
    context: ["Current conversation", "Minimal interface preference", "Prototype structure"],
    expression: "calm",
  },
];

function sessionId() {
  return window.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function makeSession(records = [], title = "Fresh page", id = sessionId(), createdAt = new Date().toISOString()) {
  return { id, title, createdAt, updatedAt: createdAt, pinned: false, archived: false, draft: "", records };
}

function readSessionStore() {
  try {
    const saved = JSON.parse(localStorage.getItem(sessionStorageKey) || "null");
    if (saved?.activeSessionId && Array.isArray(saved.sessions) && saved.sessions.length) {
      saved.sessions.forEach((session) => {
        if (session.title === "New conversation") session.title = "Fresh page";
      });
      return saved;
    }
  } catch {
    // Fall through to the legacy conversation migration.
  }

  const legacy = readConversationRecords();
  let current = makeSession([...seedConversationRecords], "AIKA companion interface", "session-seed");
  const sessions = [current];
  legacy.forEach((record) => {
    if (record.type === "divider") {
      current = makeSession([], record.label || "New conversation", record.id || sessionId());
      sessions.push(current);
    } else {
      current.records.push(record);
    }
  });
  const legacyMeta = readSessionHistoryMeta();
  sessions.forEach((session) => Object.assign(session, legacyMeta[session.id] || {}));
  const migrated = { activeSessionId: sessions.at(-1).id, sessions };
  try { localStorage.setItem(sessionStorageKey, JSON.stringify(migrated)); } catch { /* Keep the migrated state in memory. */ }
  return migrated;
}

function activeSession() {
  return sessionStore.sessions.find((session) => session.id === sessionStore.activeSessionId) || sessionStore.sessions[0];
}

function saveSessionStore() {
  try {
    localStorage.setItem(sessionStorageKey, JSON.stringify(sessionStore));
  } catch {
    // Sessions remain available until the page closes when storage is blocked.
  }
}

function storeConversationRecords() {
  const session = activeSession();
  if (!session) return;
  session.records = conversationRecords.slice(-100).map(({ previewUrl, ...record }) => record);
  session.updatedAt = new Date().toISOString();
  const firstUser = session.records.find((record) => record.type === "user" && record.text)?.text?.trim();
  if (session.title === "Fresh page" && firstUser) session.title = firstUser.length > 48 ? `${firstUser.slice(0, 48)}…` : firstUser;
  saveSessionStore();
}

function createMessageActions(role) {
  const actions = document.createElement("div");
  actions.className = "message-actions";
  const definitions = role === "user"
    ? [["copy", "Copy"], ["edit", "Edit"], ["continue", "Continue"]]
    : [["copy", "Copy"], ["retry", "Retry"], ["memory", "Save to Memory"]];
  definitions.forEach(([action, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.messageAction = action;
    button.textContent = label;
    actions.append(button);
  });
  return actions;
}

function createUserTurn(text, meta = "Typed just now", id = "", branch = "") {
  const article = document.createElement("article");
  article.className = "conversation-turn user-turn";
  article.dataset.conversationEntry = "";
  if (id) article.dataset.recordId = id;
  const header = document.createElement("header");
  const label = document.createElement("span");
  const time = document.createElement("time");
  label.textContent = "You";
  time.textContent = conversationTime();
  header.append(label, time);
  const message = document.createElement("p");
  message.textContent = text;
  const detail = document.createElement("small");
  detail.textContent = meta;
  article.append(header, message, detail);
  if (branch) {
    const branchLabel = document.createElement("span");
    branchLabel.className = "branch-label";
    branchLabel.textContent = branch;
    article.append(branchLabel);
  }
  article.append(createMessageActions("user"));
  return article;
}

function createAikaTurn(record, pending = false) {
  const article = document.createElement("article");
  article.className = `conversation-turn aika-turn journal-aika-turn${pending ? " is-pending" : ""}`;
  article.dataset.conversationEntry = "";
  if (record.id) article.dataset.recordId = record.id;
  const mark = document.createElement("span");
  mark.className = "aika-turn-mark";
  mark.setAttribute("aria-hidden", "true");
  mark.append(document.createElement("i"));
  const content = document.createElement("div");
  content.className = "journal-aika-copy";
  const lead = document.createElement("p");
  lead.className = "voice-lead";
  lead.textContent = record.lead;
  const title = document.createElement("h2");
  title.textContent = record.title;
  const bodyCopy = document.createElement("p");
  bodyCopy.textContent = record.body;
  content.append(lead, title, bodyCopy);
  article.append(mark, content);
  if (!pending) {
    article.append(createContextTrace(record.context));
    article.append(createMessageActions("aika"));
  }
  return article;
}

function createContextTrace(context = ["Current conversation", "AIKA companion style"]) {
  const details = document.createElement("details");
  details.className = "context-trace";
  const summary = document.createElement("summary");
  summary.append("Why this response ");
  const plus = document.createElement("span");
  plus.textContent = "＋";
  summary.append(plus);
  const items = document.createElement("div");
  context.forEach((item) => {
    const chip = document.createElement("span");
    chip.textContent = item;
    items.append(chip);
  });
  details.append(summary, items);
  return details;
}

function createAttachmentTurn(record) {
  const article = createUserTurn(record.name, `${record.kind} · ${record.size}${record.detail ? ` · ${record.detail}` : ""}`, record.id);
  article.classList.add("attachment-turn");
  const preview = document.createElement("span");
  preview.className = "attachment-mark";
  preview.textContent = record.kind.startsWith("image") ? "IMG" : "FILE";
  article.prepend(preview);
  if (record.previewUrl) {
    const image = document.createElement("img");
    image.className = "attachment-thumbnail";
    image.src = record.previewUrl;
    image.alt = `Preview of ${record.name}`;
    article.insertBefore(image, article.querySelector(".message-actions"));
  } else {
    const facts = document.createElement("div");
    facts.className = "attachment-facts";
    const language = document.createElement("span");
    const detail = document.createElement("small");
    language.textContent = record.language || "Local file";
    detail.textContent = record.detail || "Preview represented by metadata";
    facts.append(language, detail);
    article.insertBefore(facts, article.querySelector(".message-actions"));
  }
  article.querySelector(".message-actions")?.remove();
  const actions = document.createElement("div");
  actions.className = "message-actions attachment-actions";
  actions.innerHTML = '<button type="button" data-attachment-action="replace">Replace</button><button type="button" data-attachment-action="remove">Remove</button>';
  article.append(actions);
  return article;
}

function createConversationEvent(record) {
  const article = document.createElement("article");
  article.className = `conversation-event conversation-event--${record.kind}`;
  article.dataset.conversationEntry = "";
  const mark = document.createElement("span");
  mark.className = "event-mark";
  mark.textContent = record.kind === "approval" || record.kind === "summary" ? "◇" : record.kind === "offline" ? "⌁" : "!";
  const copy = document.createElement("div");
  const label = document.createElement("small");
  label.textContent = record.label;
  const title = document.createElement("h3");
  title.textContent = record.title;
  const bodyCopy = document.createElement("p");
  bodyCopy.textContent = record.body;
  copy.append(label, title, bodyCopy);
  article.append(mark, copy);
  if (record.kind === "approval") {
    const footer = document.createElement("footer");
    footer.innerHTML = '<button type="button" data-approval="review">Review changes</button><button type="button" data-approval="allow">Allow</button><button type="button" data-approval="later">Not now</button>';
    article.append(footer);
  } else if (record.kind !== "summary") {
    const action = document.createElement("button");
    action.type = "button";
    action.dataset.eventRecovery = record.kind;
    action.textContent = record.kind === "offline" ? "Continue locally" : "Try again";
    article.append(action);
  }
  return article;
}

function renderConversationRecord(record) {
  if (record.type === "user") return createUserTurn(record.text, record.meta, record.id, record.branch);
  if (record.type === "aika") return createAikaTurn(record);
  if (record.type === "attachment") return createAttachmentTurn(record);
  if (record.type === "divider") {
    const divider = document.createElement("div");
    divider.className = "conversation-day session-divider";
    divider.dataset.conversationEntry = "";
    divider.dataset.recordId = record.id;
    const label = document.createElement("span");
    const line = document.createElement("i");
    const time = document.createElement("time");
    label.textContent = record.label;
    time.textContent = record.time;
    divider.append(label, line, time);
    return divider;
  }
  return createConversationEvent(record);
}

function insertConversationNode(node) {
  node.dataset.sessionRecord = "";
  conversationJournal.insertBefore(node, workPresence);
  updateConversationDensity();
  return node;
}

function addConversationRecord(record, shouldStore = true) {
  if (!record.id) record.id = `turn-${Date.now()}-${messageSequence += 1}`;
  const node = insertConversationNode(renderConversationRecord(record));
  if (shouldStore) {
    conversationRecords.push(record);
    storeConversationRecords();
    syncEmptySessionState();
  }
  if (shouldStore && historyIsOpen()) renderSessionHistory();
  return node;
}

function resetConversationTools() {
  conversationSearchPanel.hidden = true;
  conversationSearchToggle.setAttribute("aria-expanded", "false");
  conversationSearchInput.value = "";
  conversationSearchStatus.textContent = "Type to search";
  conversationJournal.classList.remove("is-searching", "show-all-turns");
  conversationJournal.querySelectorAll(".is-search-hidden").forEach((entry) => entry.classList.remove("is-search-hidden"));
  conversationMoreMenu.hidden = true;
  conversationMoreToggle.setAttribute("aria-expanded", "false");
}

function updateEmptySessionPresence() {
  const hour = new Date().getHours();
  const moment = hour < 12 ? "Morning light" : hour < 18 ? "A quiet afternoon" : "A quiet evening";
  emptySessionKicker.textContent = `${moment} · here with you`;
  emptySessionCopy.textContent = sessionStore.sessions.length > 1
    ? "A half-formed thought is enough. I kept our earlier pages nearby."
    : "A half-formed thought is enough. We can discover where it wants to go.";
}

function syncEmptySessionState() {
  const sessionIsEmpty = conversationRecords.length === 0;
  const hasVisibleWork = !workPresence.hidden || !workResultTurn.hidden;
  const showOpening = sessionIsEmpty && !hasVisibleWork;

  conversationJournal.classList.toggle("is-empty-session", showOpening);
  emptySessionState.hidden = !showOpening;
  conversationSummarize.disabled = sessionIsEmpty;
  thoughtInput.placeholder = sessionIsEmpty
    ? "Bring me the unfinished version…"
    : "Tell me what’s on your mind…";

  if (showOpening) updateEmptySessionPresence();
}

function renderActiveSession() {
  const session = activeSession();
  conversationJournal.querySelectorAll("[data-session-record]").forEach((node) => node.remove());
  conversationRecords = session ? [...session.records] : [];
  conversationRecords.forEach((record) => addConversationRecord(record, false));
  conversationDayTime.textContent = session?.createdAt
    ? new Intl.DateTimeFormat([], { hour: "numeric", minute: "2-digit" }).format(new Date(session.createdAt))
    : "now";
  thoughtInput.value = session?.draft || "";
  resizeThoughtInput();
  workPresence.hidden = true;
  workResultTurn.hidden = true;
  syncEmptySessionState();
  updateConversationDensity();
}

function activateSession(id) {
  const current = activeSession();
  if (current) current.draft = thoughtInput.value;
  const next = sessionStore.sessions.find((session) => session.id === id);
  if (!next) return;
  if (activeStream) stopActiveStream();
  sessionStore.activeSessionId = next.id;
  saveSessionStore();
  resetConversationTools();
  renderActiveSession();
  closeSessionHistory();
  thoughtStatus.textContent = `Opened “${next.title}”.`;
  thoughtInput.focus();
  scrollConversationToEnd();
}

function createNewSession() {
  const current = activeSession();
  if (current) current.draft = thoughtInput.value;
  if (current && current.records.length === 0 && !current.draft.trim()) {
    current.draft = "";
    thoughtInput.value = "";
    resetConversationTools();
    closeSessionHistory();
    saveSessionStore();
    renderActiveSession();
    thoughtStatus.textContent = "This conversation is already blank.";
    thoughtInput.focus();
    return;
  }
  if (activeStream) stopActiveStream();
  const session = makeSession();
  sessionStore.sessions.push(session);
  sessionStore.activeSessionId = session.id;
  saveSessionStore();
  resetConversationTools();
  closeSessionHistory();
  renderActiveSession();
  thoughtStatus.textContent = "A fresh page is ready.";
  setExpression("calm");
  setCharacterMotion("idle", "sharing a quiet page");
  thoughtInput.focus();
  companionPulse.scrollTo({ top: 0, behavior: "smooth" });
}

function readSessionHistoryMeta() {
  try { return JSON.parse(localStorage.getItem("aika-session-history-meta-v1")) || {}; }
  catch { return {}; }
}

function getHistorySessions() {
  return [...sessionStore.sessions].map((session) => {
    const last = [...session.records].reverse().find((record) => record.text || record.title || record.body);
    return {
      ...session,
      preview: last?.text || last?.title || last?.body || "A quiet space ready for your next thought.",
      pinned: Boolean(session.pinned),
      archived: Boolean(session.archived),
      count: session.records.length,
      time: new Intl.DateTimeFormat([], { hour: "numeric", minute: "2-digit" }).format(new Date(session.updatedAt)),
    };
  }).sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
}

function saveHistoryMeta(sessionId, patch) {
  const session = sessionStore.sessions.find((item) => item.id === sessionId);
  if (!session) return;
  Object.assign(session, patch, { updatedAt: new Date().toISOString() });
  saveSessionStore();
  renderSessionHistory();
}

function sessionExport(session) {
  const payload = { title: session.title, exportedAt: new Date().toISOString(), messages: session.records };
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${session.title.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase() || "aika-session"}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function summarizeHistorySession(session) {
  const target = sessionStore.sessions.find((item) => item.id === session.id);
  if (!target) return;
  const topic = session.records.find((record) => record.type === "user")?.text || session.title;
  target.records.push({
    id: `turn-${Date.now()}-${messageSequence += 1}`,
    type: "event",
    kind: "summary",
    label: "Session summary",
    title: session.title,
    body: `${session.count} conversation ${session.count === 1 ? "turn" : "turns"}, centered on ${topic.toLowerCase()}.`,
  });
  target.updatedAt = new Date().toISOString();
  saveSessionStore();
  if (session.id === sessionStore.activeSessionId) renderActiveSession();
  renderSessionHistory();
  thoughtStatus.textContent = `A local summary was added to “${session.title}”.`;
}

function openHistorySession(session) {
  activateSession(session.id);
}

function beginHistoryRename(card, session) {
  const title = card.querySelector(".history-session-title");
  const input = document.createElement("input");
  input.className = "history-rename-input";
  input.value = session.title;
  input.setAttribute("aria-label", "Conversation name");
  title.replaceWith(input);
  input.focus();
  input.select();
  const finish = (save) => {
    const value = input.value.trim();
    if (save && value) saveHistoryMeta(session.id, { title: value });
    else renderSessionHistory();
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") finish(true);
    if (event.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => finish(true), { once: true });
}

function renderSessionHistory() {
  const query = sessionHistorySearch.value.trim().toLowerCase();
  const allSessions = getHistorySessions();
  const visibleSessions = allSessions.filter((session) => !session.archived);
  const pinnedSessions = visibleSessions.filter((session) => session.pinned);
  const archivedSessions = allSessions.filter((session) => session.archived);
  sessionHistoryCount.textContent = allSessions.length;
  sessionHistoryFilters.forEach((button) => {
    const count = button.dataset.historyFilter === "pinned"
      ? pinnedSessions.length
      : button.dataset.historyFilter === "archived" ? archivedSessions.length : visibleSessions.length;
    button.querySelector("span").textContent = count;
  });

  const sessions = allSessions.filter((session) => {
    const matchesFilter = (activeHistoryFilter === "all" && !session.archived)
      || (activeHistoryFilter === "pinned" && session.pinned && !session.archived)
      || (activeHistoryFilter === "archived" && session.archived);
    return matchesFilter && (!query || `${session.title} ${session.preview}`.toLowerCase().includes(query));
  });
  if (activeHistoryFilter === "all") {
    sessions.sort((a, b) => Number(b.pinned) - Number(a.pinned) || new Date(b.updatedAt) - new Date(a.updatedAt));
  }
  sessionHistoryList.replaceChildren();
  sessionHistoryEmpty.hidden = sessions.length > 0;
  if (!sessions.length) return;
  let previousGroup = "";
  sessions.forEach((session) => {
    const updated = new Date(session.updatedAt);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    const daysAgo = Math.floor((new Date(today.toDateString()) - new Date(updated.toDateString())) / 86400000);
    const groupName = activeHistoryFilter === "all" && session.pinned
      ? "Kept close"
      : updated.toDateString() === today.toDateString()
        ? "Today"
        : updated.toDateString() === yesterday.toDateString()
          ? "Yesterday"
          : daysAgo < 7
            ? "This week"
            : new Intl.DateTimeFormat([], { month: "long", year: "numeric" }).format(updated);
    if (groupName !== previousGroup) {
      const group = document.createElement("p");
      group.className = "history-date-group";
      group.textContent = groupName;
      sessionHistoryList.append(group);
      previousGroup = groupName;
    }
    const card = document.createElement("article");
    card.className = "history-session-card";
    if (session.id === sessionStore.activeSessionId) card.classList.add("is-active");
    if (session.archived) card.classList.add("is-archived");
    const main = document.createElement("button");
    main.type = "button";
    main.className = "history-session-main";
    const heading = document.createElement("span");
    heading.className = "history-session-heading";
    const title = document.createElement("strong");
    title.className = "history-session-title";
    title.textContent = session.title;
    heading.append(title);
    if (session.id === sessionStore.activeSessionId || session.pinned) {
      const state = document.createElement("small");
      state.className = "history-session-state";
      state.textContent = session.id === sessionStore.activeSessionId ? "Open" : "Kept";
      heading.append(state);
    }
    const preview = document.createElement("span");
    preview.className = "history-session-preview";
    preview.textContent = session.preview;
    const detail = document.createElement("small");
    detail.className = "history-session-detail";
    detail.textContent = `${session.count} ${session.count === 1 ? "turn" : "turns"} · ${session.time}`;
    main.append(heading, preview, detail);
    main.addEventListener("click", () => openHistorySession(session));
    const actions = document.createElement("details");
    actions.className = "history-session-actions";
    const actionsToggle = document.createElement("summary");
    actionsToggle.setAttribute("aria-label", `More options for ${session.title}`);
    actionsToggle.textContent = "•••";
    const actionsMenu = document.createElement("div");
    [
      [session.pinned ? "Let go" : "Keep close", () => saveHistoryMeta(session.id, { pinned: !session.pinned })],
      ["Rename", () => beginHistoryRename(card, session)],
      ["Summarize", () => summarizeHistorySession(session)],
      ["Export", () => sessionExport(session)],
      [session.archived ? "Restore" : "Archive", () => saveHistoryMeta(session.id, { archived: !session.archived })],
    ].forEach(([label, action]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", () => {
        actions.open = false;
        action();
      });
      actionsMenu.append(button);
    });
    actions.append(actionsToggle, actionsMenu);
    card.append(main, actions);
    sessionHistoryList.append(card);
  });
}

function closeSessionHistory() {
  sessionHistoryPanel.classList.remove("is-open");
  sessionHistoryPanel.setAttribute("aria-hidden", "true");
  conversationHistoryToggle.setAttribute("aria-expanded", "false");
}

function historyIsOpen() {
  return sessionHistoryPanel.classList.contains("is-open");
}

function updateConversationDensity() {
  const entries = [...conversationJournal.querySelectorAll("[data-conversation-entry]")];
  entries.forEach((entry) => entry.classList.remove("is-archived-turn"));
  const archivedCount = Math.max(0, entries.length - 7);
  entries.slice(0, archivedCount).forEach((entry) => entry.classList.add("is-archived-turn"));
  olderTurnsToggle.hidden = archivedCount === 0;
  olderTurnsToggle.textContent = conversationJournal.classList.contains("show-all-turns")
    ? "Hide earlier conversation"
    : `Show ${archivedCount} earlier ${archivedCount === 1 ? "turn" : "turns"}`;
}

function stopActiveStream() {
  if (!activeStream) return;
  clearInterval(activeStream.timer);
  clearTimeout(activeStream.phaseTimer);
  const { node, record, bodyCopy, words, index } = activeStream;
  const partial = words.slice(0, Math.max(index, 1)).join(" ");
  bodyCopy.textContent = `${partial}${index < words.length ? " …" : ""}`;
  node.classList.remove("is-streaming", "is-pending");
  node.classList.add("is-stopped");
  const status = node.querySelector(".stream-state");
  if (status) status.textContent = "Stopped by you";
  const stop = node.querySelector("[data-stop-stream]");
  if (stop) stop.remove();
  node.append(createContextTrace(["Current conversation", "Stopped response"]), createMessageActions("aika"));
  conversationRecords.push({ type: "aika", ...record, body: bodyCopy.textContent, context: ["Current conversation", "Stopped response"] });
  storeConversationRecords();
  activeStream = null;
  setExpression("calm");
  setCharacterMotion("idle", "ready when you are");
  thoughtStatus.textContent = "AIKA stopped generating. The partial response remains in the conversation.";
}

function finishActiveStream() {
  if (!activeStream) return;
  clearInterval(activeStream.timer);
  const { node, record } = activeStream;
  node.classList.remove("is-streaming", "is-pending");
  const status = node.querySelector(".stream-state");
  if (status) status.textContent = "Response complete";
  const stop = node.querySelector("[data-stop-stream]");
  if (stop) stop.remove();
  node.append(createContextTrace(record.context), createMessageActions("aika"));
  conversationRecords.push({ type: "aika", ...record });
  storeConversationRecords();
  activeStream = null;
  updateConversationDensity();
  playCharacterReaction(record.expression || "calm");
  thoughtStatus.textContent = "Prototype response complete. No external model or tool was called.";
  scrollConversationToEnd();
}

function appendAikaReply(reply, finalExpression = "calm") {
  stopActiveStream();
  const id = `turn-${Date.now()}-${messageSequence += 1}`;
  const record = {
    type: "aika",
    id,
    ...reply,
    expression: finalExpression,
    context: reply.context || ["Current conversation", "Companion preferences", "Prototype only"],
  };
  const pending = createAikaTurn({ id, lead: "A quiet moment…", title: "Thinking beside you…", body: "I’m finding the part that deserves attention first." }, true);
  const copy = pending.querySelector(".journal-aika-copy");
  const status = document.createElement("small");
  status.className = "stream-state";
  status.textContent = "Thinking";
  copy.prepend(status);
  const stop = document.createElement("button");
  stop.type = "button";
  stop.dataset.stopStream = "";
  stop.className = "stop-stream";
  stop.textContent = "Stop";
  pending.append(stop);
  insertConversationNode(pending);
  setExpression("calm");
  setCharacterMotion("thinking");
  scrollConversationToEnd();

  const phaseTimer = window.setTimeout(() => {
    status.textContent = "Forming response";
    setCharacterMotion("talking");
    const lead = pending.querySelector(".voice-lead");
    const title = pending.querySelector("h2");
    const bodyCopy = pending.querySelector(".journal-aika-copy > p:last-child");
    lead.textContent = record.lead;
    title.textContent = record.title;
    bodyCopy.textContent = "";
    pending.classList.add("is-streaming");
    const words = record.body.split(/\s+/);
    activeStream = { node: pending, record, bodyCopy, words, index: 0, timer: null, phaseTimer };
    activeStream.timer = window.setInterval(() => {
      if (!activeStream) return;
      activeStream.index = Math.min(activeStream.index + 3, words.length);
      bodyCopy.textContent = words.slice(0, activeStream.index).join(" ");
      if (activeStream.index >= words.length) finishActiveStream();
    }, 58);
  }, 520);
  activeStream = { node: pending, record, bodyCopy: copy.querySelector("p:last-child"), words: record.body.split(/\s+/), index: 0, timer: null, phaseTimer };
}

function scrollConversationToEnd() {
  const conversation = document.querySelector(".companion-pulse");
  window.requestAnimationFrame(() => conversation.scrollTo({ top: conversation.scrollHeight, behavior: "smooth" }));
}

function clearVoiceTimers() {
  clearInterval(voiceClock);
  clearInterval(voiceTranscriptClock);
  clearTimeout(voiceStageTimer);
}

function finishVoiceDemo(message = "Voice conversation closed. Your typed conversation is still available.") {
  clearVoiceTimers();
  if (speechRecognition && voiceSession.dataset.stage === "listening") {
    try { speechRecognition.abort(); } catch { /* Recognition may already be stopped. */ }
  }
  window.speechSynthesis?.cancel();
  voiceSession.hidden = true;
  thoughtForm.hidden = false;
  voiceSession.dataset.stage = "idle";
  setExpression("calm");
  setCharacterMotion("idle");
  thoughtStatus.textContent = message;
  thoughtInput.focus();
}

function setVoiceStage(stage) {
  voiceSession.dataset.stage = stage;

  if (stage === "listening") {
    voicePhase.textContent = "Listening";
    voicePrompt.textContent = "Talk naturally. I’ll keep the words visible.";
    voiceTranscript.textContent = "I’m listening…";
    voiceAdvance.textContent = "Done";
    voiceAdvance.disabled = false;
    voicePause.textContent = "Pause";
    voicePause.disabled = false;
    voiceTranscript.classList.remove("is-uncertain");
    setExpression("calm");
    setCharacterMotion("listening");
    return;
  }

  if (stage === "thinking") {
    voiceTranscript.dataset.userTranscript = voiceTranscript.textContent;
    voicePhase.textContent = "Understanding";
    voicePrompt.textContent = "I have your words. I’m finding the useful part.";
    voiceAdvance.textContent = "Just a moment";
    voiceAdvance.disabled = true;
    voicePause.disabled = true;
    setExpression("calm");
    setCharacterMotion("thinking");
    voiceStageTimer = window.setTimeout(() => setVoiceStage("speaking"), 850);
    return;
  }

  voicePhase.textContent = "AIKA is speaking";
  voicePrompt.textContent = "You can interrupt me whenever you need to.";
  voiceTranscript.textContent = "I understand. I’d keep the conversation visible, respond in place, and let you interrupt without losing our context.";
  voiceAdvance.textContent = "Stop";
  voiceAdvance.disabled = false;
  voicePause.textContent = "Pause audio";
  voicePause.disabled = !voiceSettings.autoSpeak || !("speechSynthesis" in window);
  setExpression("calm");
  setCharacterMotion("talking");
  if (voiceSettings.autoSpeak && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(voiceTranscript.textContent);
    utterance.rate = Number(voiceSettings.rate);
    utterance.pitch = 1.04;
    const selectedVoice = window.speechSynthesis.getVoices().find((voice) => voice.name === voiceSettings.voiceName);
    if (selectedVoice) utterance.voice = selectedVoice;
    window.speechSynthesis.speak(utterance);
  }
}

function startVoiceDemo() {
  clearVoiceTimers();
  switchSpace("together");
  thoughtForm.hidden = true;
  voiceSession.hidden = false;
  voiceElapsed = 0;
  liveVoiceTranscript = "";
  voiceOutputPaused = false;
  voiceTimer.textContent = "00:00";
  setExpression("calm");
  setVoiceStage("listening");

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  speechIsLive = Boolean(Recognition);
  const honesty = voiceSession.querySelector("footer span");
  if (Recognition) {
    speechRecognition = new Recognition();
    speechRecognition.continuous = voiceSettings.inputMode === "continuous";
    speechRecognition.interimResults = true;
    speechRecognition.lang = document.documentElement.lang || "en-US";
    speechRecognition.onresult = (event) => {
      let transcript = "";
      let uncertain = false;
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
        uncertain ||= !event.results[index].isFinal || event.results[index][0].confidence < 0.65;
      }
      if (transcript.trim()) {
        liveVoiceTranscript = transcript.trim();
        voiceTranscript.textContent = liveVoiceTranscript;
        voiceTranscript.classList.toggle("is-uncertain", uncertain);
      }
    };
    speechRecognition.onerror = (event) => {
      const denied = event.error === "not-allowed" || event.error === "service-not-allowed";
      finishVoiceDemo(denied ? "Microphone permission was not granted. Typed conversation is still available." : "Speech recognition paused. You can continue by typing.");
      addConversationRecord({
        type: "event",
        kind: "failure",
        label: "Voice unavailable",
        title: denied ? "Microphone access was not granted" : "Speech recognition stopped",
        body: "Nothing was lost. Continue by typing, or try the microphone again when it is available.",
      });
    };
    speechRecognition.onend = () => {
      if (voiceSession.dataset.stage === "listening") setVoiceStage("thinking");
    };
    honesty.textContent = "Browser speech recognition · permission requested only after your click";
    try {
      speechRecognition.start();
    } catch {
      speechIsLive = false;
    }
  }

  if (!speechIsLive) {
    const transcriptMoments = [
      "When I’m speaking with you…",
      "When I’m speaking with you, I want the conversation…",
      "When I’m speaking with you, I want the conversation to stay natural and visible.",
    ];
    let transcriptIndex = 0;
    voiceTranscriptClock = window.setInterval(() => {
      voiceTranscript.textContent = transcriptMoments[Math.min(transcriptIndex, transcriptMoments.length - 1)];
      liveVoiceTranscript = voiceTranscript.textContent;
      transcriptIndex += 1;
    }, 800);
    honesty.textContent = "Speech API unavailable · showing the interface simulation";
  }
  voiceClock = window.setInterval(() => {
    voiceElapsed += 1;
    voiceTimer.textContent = formatElapsed(voiceElapsed);
  }, 1000);
  thoughtStatus.textContent = speechIsLive ? "Listening through the browser speech API." : "Voice interface simulation open.";
}

function advanceVoiceDemo() {
  const stage = voiceSession.dataset.stage;
  if (stage === "listening") {
    clearInterval(voiceTranscriptClock);
    if (speechIsLive && speechRecognition) {
      try { speechRecognition.stop(); } catch { /* Recognition may already be stopped. */ }
    }
    setVoiceStage("thinking");
  } else if (stage === "speaking") {
    const transcript = voiceTranscript.dataset.userTranscript || "When I’m speaking with you, I want the conversation to stay natural and visible.";
    addConversationRecord({ type: "user", text: transcript, meta: `Voice transcript · ${formatElapsed(voiceElapsed)}` });
    addConversationRecord({
      type: "aika",
      lead: "I heard you clearly.",
      title: "We can keep voice inside the same conversation.",
      body: "Your transcript becomes a normal turn, my spoken response stays readable, and you can interrupt without losing the thread.",
      context: ["Voice transcript", "Current conversation", "Speech preferences"],
    });
    finishVoiceDemo("Voice exchange complete. The transcript would remain in the conversation.");
    scrollConversationToEnd();
  }
}

function toggleVoicePause() {
  const stage = voiceSession.dataset.stage;
  if (stage === "listening") {
    voiceSession.dataset.stage = "paused";
    clearInterval(voiceTranscriptClock);
    if (speechIsLive && speechRecognition) {
      try { speechRecognition.stop(); } catch { /* Recognition may already be paused. */ }
    }
    voicePhase.textContent = "Paused";
    voicePrompt.textContent = "Take your time. Your transcript is still here.";
    voicePause.textContent = "Resume";
    characterState.textContent = "waiting with you";
    return;
  }

  if (stage === "paused") {
    voiceSession.dataset.stage = "listening";
    voicePhase.textContent = "Listening";
    voicePrompt.textContent = "Continue whenever you’re ready.";
    voicePause.textContent = "Pause";
    characterState.textContent = "listening closely";
    if (speechIsLive && speechRecognition) {
      try { speechRecognition.start(); } catch { /* Browser may require a fresh voice session. */ }
    } else {
      voiceTranscriptClock = window.setInterval(() => {
        liveVoiceTranscript = "When I’m speaking with you, I want the conversation to stay natural and visible.";
        voiceTranscript.textContent = liveVoiceTranscript;
      }, 900);
    }
    return;
  }

  if (stage === "speaking" && "speechSynthesis" in window) {
    if (voiceOutputPaused) {
      window.speechSynthesis.resume();
      voicePause.textContent = "Pause audio";
    } else {
      window.speechSynthesis.pause();
      voicePause.textContent = "Resume audio";
    }
    voiceOutputPaused = !voiceOutputPaused;
  }
}

const workSentences = [
  "I’m understanding what should change before touching the interface.",
  "I’ve chosen a focused approach and kept the rest of the design untouched.",
  "I’m building the interaction and keeping each change visible.",
  "I’m checking the result and making sure the conversation still has room.",
];

function clearWorkTimers() {
  clearInterval(workClock);
  clearInterval(workStageClock);
}

function saveWorkState(status) {
  try {
    localStorage.setItem("aika-prototype-work-v1", JSON.stringify({ status, stage: workStage, elapsed: workElapsed }));
  } catch {
    // The active card still works for the current session.
  }
}

function readWorkState() {
  try {
    return JSON.parse(localStorage.getItem("aika-prototype-work-v1") || "null");
  } catch {
    return null;
  }
}

function setWorkStage(stage) {
  const steps = [...document.querySelectorAll("[data-work-step]")];
  workStage = stage;
  steps.forEach((step, index) => {
    step.classList.toggle("is-complete", index < stage || stage >= steps.length);
    step.classList.toggle("is-current", index === stage && stage < steps.length);
  });

  if (stage < steps.length) {
    workSentence.textContent = workSentences[stage];
    globalWorkText.textContent = stage < 2 ? "Planning" : stage === 2 ? "Building" : "Checking";
    saveWorkState("running");
    return;
  }

  clearWorkTimers();
  workPresence.classList.add("is-finished");
  workTitle.textContent = "Finished — the interaction is ready";
  workSentence.textContent = "The result is ready to review, and the work details remain available when you want them.";
  workHonesty.textContent = "3 prototype files represented · checks complete";
  workStop.textContent = "Close";
  workResultTurn.hidden = false;
  syncEmptySessionState();
  globalWorkText.textContent = "Result ready";
  globalWorkIndicator.classList.add("is-ready");
  workResume.hidden = true;
  saveWorkState("finished");
  playCharacterReaction("happy");
  thoughtStatus.textContent = "Working-state demonstration complete. No files or tools were actually changed by this demo.";
  scrollConversationToEnd();
}

function startWorkDemo() {
  clearWorkTimers();
  switchSpace("together");
  conversationJournal.append(workPresence, workResultTurn);
  workPresence.hidden = false;
  workResultTurn.hidden = true;
  syncEmptySessionState();
  workPresence.classList.remove("is-finished", "is-stopped");
  workTitle.textContent = "Shaping your companion prototype";
  workHonesty.textContent = "Working locally · simulated prototype";
  workStop.textContent = "Stop";
  workResume.hidden = true;
  globalWorkIndicator.hidden = false;
  globalWorkIndicator.classList.remove("is-ready", "is-paused");
  globalWorkText.textContent = "Planning";
  workElapsed = 0;
  workTimer.textContent = "00:00";
  setWorkStage(0);
  setExpression("calm");
  setCharacterMotion("working");
  workPresence.scrollIntoView({ behavior: "smooth", block: "center" });

  workClock = window.setInterval(() => {
    workElapsed += 1;
    workTimer.textContent = formatElapsed(workElapsed);
    saveWorkState("running");
  }, 1000);
  workStageClock = window.setInterval(() => setWorkStage(workStage + 1), 1150);
  thoughtStatus.textContent = "Working-state preview started. This is a visual simulation only.";
}

function stopWorkDemo() {
  if (workPresence.classList.contains("is-finished") || workPresence.classList.contains("is-stopped")) {
    workPresence.hidden = true;
    syncEmptySessionState();
    setExpression("calm");
    setCharacterMotion("idle");
    return;
  }

  clearWorkTimers();
  workResultTurn.hidden = true;
  workPresence.classList.add("is-stopped");
  workTitle.textContent = "Work paused safely";
  workSentence.textContent = "I stopped where you asked. A real task could preserve its place and continue later.";
  workHonesty.textContent = "Stopped by you · progress preserved in the interface";
  workStop.textContent = "Close";
  workResume.hidden = false;
  globalWorkText.textContent = "Work paused";
  globalWorkIndicator.classList.add("is-paused");
  saveWorkState("paused");
  setExpression("calm");
  setCharacterMotion("idle", "work paused safely");
  syncEmptySessionState();
}

function resumeWorkDemo() {
  clearWorkTimers();
  workPresence.hidden = false;
  syncEmptySessionState();
  workPresence.classList.remove("is-stopped", "is-finished");
  workResume.hidden = true;
  workStop.textContent = "Stop";
  globalWorkIndicator.hidden = false;
  globalWorkIndicator.classList.remove("is-paused", "is-ready");
  setWorkStage(Math.max(0, workStage));
  setExpression("calm");
  setCharacterMotion("working", "continuing the work");
  workClock = window.setInterval(() => {
    workElapsed += 1;
    workTimer.textContent = formatElapsed(workElapsed);
    saveWorkState("running");
  }, 1000);
  workStageClock = window.setInterval(() => setWorkStage(workStage + 1), 1150);
}

function restoreWorkState() {
  const saved = readWorkState();
  if (!saved) return;
  workStage = Number.isInteger(saved.stage) ? saved.stage : 0;
  workElapsed = Number.isFinite(saved.elapsed) ? saved.elapsed : 0;
  workTimer.textContent = formatElapsed(workElapsed);
  conversationJournal.append(workPresence, workResultTurn);
  globalWorkIndicator.hidden = false;
  if (saved.status === "finished") {
    workPresence.hidden = true;
    workResultTurn.hidden = false;
    syncEmptySessionState();
    globalWorkText.textContent = "Result ready";
    globalWorkIndicator.classList.add("is-ready");
    playCharacterReaction("happy");
    return;
  }
  workPresence.hidden = false;
  workResultTurn.hidden = true;
  syncEmptySessionState();
  workPresence.classList.add("is-stopped");
  workTitle.textContent = saved.status === "running" ? "Paused during restart" : "Work paused safely";
  workSentence.textContent = "Completed progress is preserved. Continue when you’re ready.";
  workHonesty.textContent = `${formatElapsed(workElapsed)} elapsed · progress preserved locally`;
  workResume.hidden = false;
  workStop.textContent = "Close";
  globalWorkText.textContent = "Work paused";
  globalWorkIndicator.classList.add("is-paused");
  setCharacterMotion("idle", "work paused safely");
  saveWorkState("paused");
  const steps = [...document.querySelectorAll("[data-work-step]")];
  steps.forEach((step, index) => {
    step.classList.toggle("is-complete", index < workStage);
    step.classList.toggle("is-current", index === workStage);
  });
}

function switchSpace(space) {
  if (!spaces[space]) return;

  currentSpace = space;
  document.querySelectorAll("[data-space-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.spacePanel === space);
  });
  document.querySelectorAll("[data-space]").forEach((button) => {
    const active = button.dataset.space === space;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
    if (active) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  });

  activeSpaceName.textContent = spaces[space].label;
  activeSpaceIcon.textContent = spaces[space].icon;
  moreToggle.setAttribute("aria-label", `Current space: ${spaces[space].label}. Choose another space.`);
  setMoreMenu(false);

  spaceKicker.textContent = spaces[space].kicker;
  document.querySelector(".character-aside").textContent = spaces[space].aside;
  document.querySelector(".companion-pulse").scrollTo({ top: 0, behavior: "smooth" });
  thoughtStatus.textContent = `${spaces[space].kicker} open · sample content`;
}

function chooseReply(thought) {
  const normalized = thought.toLowerCase();
  return companionReplies.find((reply) => reply.terms.some((term) => normalized.includes(term))) || {
    title: "I’m with you",
    body: `I’ve placed “${thought}” at the center of our desk. In the real system, I’d use the relevant memories, tools, and permissions before responding.`,
    lead: "For this prototype, I’m showing the intended companion rhythm without pretending a live model is connected.",
  };
}

function shareThought() {
  const thought = thoughtInput.value.trim();
  if (!thought) {
    thoughtStatus.textContent = "Write a thought first—I’m listening.";
    thoughtInput.focus();
    return;
  }

  switchSpace("together");
  clearTimeout(responseTimer);
  addConversationRecord({ type: "user", text: thought, meta: "Typed just now" });
  const protectedIntent = ["delete", "remove file", "write file", "edit file", "run command", "shell"].some((term) => thought.toLowerCase().includes(term));
  if (protectedIntent) {
    addConversationRecord({
      type: "event",
      kind: "approval",
      label: "Your approval is needed",
      title: "This request may change your files",
      body: "AIKA would show the exact targets and proposed changes before anything protected is allowed to continue.",
    });
    thoughtStatus.textContent = "Protected request paused until you review it.";
    thoughtInput.value = "";
    resizeThoughtInput();
    scrollConversationToEnd();
    return;
  }
  thoughtStatus.textContent = "AIKA is composing a prototype response locally.";
  appendAikaReply(chooseReply(thought), expressionForThought(thought));

  thoughtInput.value = "";
  resizeThoughtInput();
}

themeSwitch.addEventListener("click", () => {
  setTheme(root.dataset.theme === "daylight" ? "twilight" : "daylight");
});

railToggle.addEventListener("click", () => setRail(!body.classList.contains("rail-collapsed")));
railClose.addEventListener("click", () => setRail(true));
moreToggle.addEventListener("click", () => setMoreMenu(moreMenu.hidden));
voiceToggle.addEventListener("click", startVoiceDemo);
voiceCancel.addEventListener("click", () => finishVoiceDemo());
voicePause.addEventListener("click", toggleVoicePause);
voiceAdvance.addEventListener("click", advanceVoiceDemo);
workDemo.addEventListener("click", () => {
  conversationMoreMenu.hidden = true;
  conversationMoreToggle.setAttribute("aria-expanded", "false");
  startWorkDemo();
});
workStop.addEventListener("click", stopWorkDemo);
workResume.addEventListener("click", resumeWorkDemo);
globalWorkIndicator.addEventListener("click", () => {
  switchSpace("together");
  workPresence.scrollIntoView({ behavior: "smooth", block: "center" });
});
composerAdd.addEventListener("click", () => {
  const open = composerTray.hidden;
  composerTray.hidden = !open;
  composerAdd.setAttribute("aria-expanded", String(open));
  composerAdd.classList.toggle("is-open", open);
});
attachFileAction.addEventListener("click", () => {
  attachmentReplaceTargetId = "";
  attachmentInput.multiple = true;
  attachmentInput.click();
});
async function buildAttachmentRecord(file) {
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  const languages = { js: "JavaScript", ts: "TypeScript", py: "Python", html: "HTML", css: "CSS", json: "JSON", md: "Markdown", txt: "Text" };
  const record = {
    type: "attachment",
    name: file.name,
    kind: file.type || "File",
    size: file.size < 1024 * 1024 ? `${Math.max(1, Math.round(file.size / 1024))} KB` : `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
    language: languages[extension] || (file.type.startsWith("image/") ? "Image" : extension.toUpperCase() || "Local file"),
  };
  if (file.type.startsWith("image/")) {
    record.previewUrl = URL.createObjectURL(file);
    record.detail = "Image preview";
  } else if ((file.type.startsWith("text/") || languages[extension]) && file.size <= 2 * 1024 * 1024) {
    try {
      const text = await file.text();
      record.detail = `${text.split(/\r?\n/).length} lines`;
    } catch {
      record.detail = "Text preview unavailable";
    }
  } else if (extension === "pdf") {
    record.detail = "PDF document";
  } else {
    record.detail = "Metadata preview";
  }
  return record;
}

attachmentInput.addEventListener("change", async () => {
  const selectedFiles = [...attachmentInput.files];
  if (attachmentReplaceTargetId) {
    conversationJournal.querySelector(`[data-record-id="${attachmentReplaceTargetId}"]`)?.remove();
    conversationRecords = conversationRecords.filter((record) => record.id !== attachmentReplaceTargetId);
    attachmentReplaceTargetId = "";
  }
  const records = await Promise.all(selectedFiles.map(buildAttachmentRecord));
  records.forEach((record) => {
    addConversationRecord(record);
  });
  if (selectedFiles.length) {
    addConversationRecord({
      type: "aika",
      lead: "I have the attachment beside us.",
      title: "I’ll wait for your direction before using it.",
      body: "A live version could read, analyze, or edit it only within the permissions you choose.",
      context: ["Attached file metadata", "Current conversation", "Permission policy"],
    });
    scrollConversationToEnd();
  }
  attachmentInput.value = "";
  composerTray.hidden = true;
  composerAdd.setAttribute("aria-expanded", "false");
});
document.querySelectorAll("[data-demo-event]").forEach((button) => {
  button.addEventListener("click", () => {
    const kind = button.dataset.demoEvent;
    const records = {
      approval: { type: "event", kind, label: "Your approval is needed", title: "Update three prototype files?", body: "AIKA would show the exact changes and keep everything outside the prototype untouched." },
      offline: { type: "event", kind, label: "Connection changed", title: "AIKA is continuing locally", body: "Online features are waiting, but your conversation and local work remain available." },
      failure: { type: "event", kind, label: "Something interrupted the task", title: "The last step did not finish", body: "Completed work is preserved. You can retry the failed step without starting over." },
    };
    addConversationRecord(records[kind]);
    composerTray.hidden = true;
    composerAdd.setAttribute("aria-expanded", "false");
    switchSpace("together");
    scrollConversationToEnd();
  });
});
comfortTextToggle.addEventListener("click", () => {
  const enabled = body.classList.toggle("comfort-text");
  savePreference("aika-comfort-text", String(enabled));
  comfortTextToggle.classList.toggle("is-active", enabled);
  comfortTextToggle.querySelector("small").textContent = enabled ? "Readability increased" : "Increase readability";
});
olderTurnsToggle.addEventListener("click", () => {
  conversationJournal.classList.toggle("show-all-turns");
  updateConversationDensity();
});
conversationSearchToggle.addEventListener("click", () => {
  const open = conversationSearchPanel.hidden;
  conversationSearchPanel.hidden = !open;
  conversationSearchToggle.setAttribute("aria-expanded", String(open));
  if (open) {
    closeSessionHistory();
    conversationSearchInput.focus();
  }
});
conversationMoreToggle.addEventListener("click", () => {
  const open = conversationMoreMenu.hidden;
  conversationMoreMenu.hidden = !open;
  conversationMoreToggle.setAttribute("aria-expanded", String(open));
});
conversationSearchClose.addEventListener("click", () => {
  conversationSearchPanel.hidden = true;
  conversationSearchToggle.setAttribute("aria-expanded", "false");
  conversationSearchInput.value = "";
  conversationJournal.classList.remove("is-searching");
  conversationJournal.querySelectorAll(".is-search-hidden").forEach((entry) => entry.classList.remove("is-search-hidden"));
});
conversationSearchInput.addEventListener("input", () => {
  const query = conversationSearchInput.value.trim().toLowerCase();
  conversationJournal.classList.toggle("is-searching", Boolean(query));
  const entries = [...conversationJournal.querySelectorAll("[data-conversation-entry]")];
  let matches = 0;
  entries.forEach((entry) => {
    const match = !query || entry.textContent.toLowerCase().includes(query);
    entry.classList.toggle("is-search-hidden", !match);
    if (query && match) matches += 1;
  });
  conversationSearchStatus.textContent = query ? `${matches} ${matches === 1 ? "match" : "matches"}` : "Type to search";
});
conversationHistoryToggle.addEventListener("click", () => {
  const willOpen = !historyIsOpen();
  sessionHistoryPanel.classList.toggle("is-open", willOpen);
  sessionHistoryPanel.setAttribute("aria-hidden", String(!willOpen));
  conversationHistoryToggle.setAttribute("aria-expanded", String(willOpen));
  if (willOpen) {
    conversationSearchPanel.hidden = true;
    conversationSearchToggle.setAttribute("aria-expanded", "false");
    renderSessionHistory();
    sessionHistorySearch.focus();
  }
});
sessionHistoryClose.addEventListener("click", closeSessionHistory);
sessionHistoryNew.addEventListener("click", createNewSession);
sessionHistorySearch.addEventListener("input", renderSessionHistory);
sessionHistoryFilters.forEach((button) => button.addEventListener("click", () => {
  activeHistoryFilter = button.dataset.historyFilter;
  sessionHistoryFilters.forEach((filter) => filter.classList.toggle("is-active", filter === button));
  renderSessionHistory();
}));
conversationSummarize.addEventListener("click", () => {
  const entries = [...conversationJournal.querySelectorAll("[data-conversation-entry]")].filter((entry) => !entry.classList.contains("conversation-event"));
  const recent = entries.slice(-6);
  const userTopics = recent.filter((entry) => entry.classList.contains("user-turn")).map((entry) => entry.querySelector("p")?.textContent).filter(Boolean);
  const topic = userTopics.at(-1) || "the current AIKA companion design";
  addConversationRecord({
    type: "event",
    kind: "summary",
    label: "Session summary",
    title: "Where we are now",
    body: `The conversation is focused on ${topic.toLowerCase()}. The interface keeps voice, work, approvals, and results inside one calm journal.`,
  });
  thoughtStatus.textContent = "A local prototype summary was added to the conversation.";
  conversationMoreMenu.hidden = true;
  conversationMoreToggle.setAttribute("aria-expanded", "false");
  scrollConversationToEnd();
});
conversationNewSession.addEventListener("click", () => {
  createNewSession();
});
jumpLatest.addEventListener("click", scrollConversationToEnd);
companionPulse.addEventListener("scroll", () => {
  const distance = companionPulse.scrollHeight - companionPulse.scrollTop - companionPulse.clientHeight;
  jumpLatest.hidden = currentSpace !== "together" || distance < 180;
});
expressionCycle.addEventListener("click", () => {
  const nextIndex = (expressionIndex + 1) % expressionOrder.length;
  const nextExpression = expressionOrder[nextIndex];
  if (nextExpression === "talking") {
    setExpression("calm");
    expressionIndex = nextIndex;
    expressionName.textContent = expressions.talking.label;
    setCharacterMotion("talking", "previewing speech");
    motionReturnTimer = window.setTimeout(() => setCharacterMotion("idle"), 1800);
  } else {
    playCharacterReaction(nextExpression);
  }
});

thoughtInput.addEventListener("input", () => {
  resizeThoughtInput();
  const session = activeSession();
  if (session) {
    session.draft = thoughtInput.value;
    saveSessionStore();
  }
});
thoughtInput.addEventListener("focus", () => {
  if (voiceSession.hidden && !activeStream && workPresence.hidden) setCharacterMotion("listening", "ready for your thought");
});
thoughtInput.addEventListener("blur", () => {
  if (currentCharacterMotion === "listening" && voiceSession.hidden) setCharacterMotion("idle");
});
thoughtInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    shareThought();
  }
});
thoughtForm.addEventListener("submit", (event) => {
  event.preventDefault();
  shareThought();
});

document.querySelectorAll("[data-space]").forEach((button) => {
  button.addEventListener("click", () => switchSpace(button.dataset.space));
});

document.querySelectorAll("[data-suggest]").forEach((button) => {
  button.addEventListener("click", () => {
    thoughtInput.value = button.dataset.suggest;
    resizeThoughtInput();
    thoughtInput.focus();
    thoughtStatus.textContent = "I placed the idea in the thought field. Edit it or press Enter when it feels right.";
  });
});

document.querySelectorAll("[data-dismiss-update]").forEach((button) => {
  button.addEventListener("click", () => {
    button.closest(".primary-update").classList.add("is-dismissed");
    thoughtStatus.textContent = "Update tucked away. The underlying reminder remains available in Dayline.";
  });
});

document.querySelectorAll("[data-memory-detail]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-memory-detail]").forEach((item) => item.classList.remove("is-selected"));
    button.classList.add("is-selected");
    document.getElementById("memoryExplanation").textContent = button.dataset.memoryDetail;
  });
});

document.querySelectorAll("[data-invite-agent]").forEach((button) => {
  button.addEventListener("click", () => {
    const invited = button.classList.toggle("is-invited");
    const agent = button.dataset.inviteAgent;
    button.closest(".crew-member").classList.toggle("is-invited", invited);
    button.textContent = invited ? "Invited" : "Invite";
    thoughtStatus.textContent = `${agent} is ${invited ? "joining" : "leaving"} this prototype workspace.`;
  });
});

document.getElementById("researchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const query = document.getElementById("researchInput").value.trim();
  if (!query) return;
  document.getElementById("researchFindingTitle").textContent = `Trail prepared for “${query}”`;
  document.getElementById("researchFindingBody").textContent = "A live version would search, compare sources, note disagreements, and keep every citation attached to the claim it supports.";
  thoughtStatus.textContent = "Sample research trail prepared locally. No web search was performed.";
});

document.querySelectorAll(".tool-shelves button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tool-shelves button").forEach((tool) => tool.classList.remove("is-selected"));
    button.classList.add("is-selected");
    thoughtStatus.textContent = `${button.textContent.trim()} selected. AIKA would still apply its permission and safety policy before acting.`;
  });
});

document.querySelectorAll(".setting-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const enabled = button.getAttribute("aria-checked") === "true";
    button.setAttribute("aria-checked", String(!enabled));
    button.classList.toggle("is-on", !enabled);
    const setting = button.querySelector("strong").textContent;
    thoughtStatus.textContent = `${setting} ${enabled ? "disabled" : "enabled"} for this visual prototype.`;
  });
});

voicePreference.addEventListener("change", () => {
  voiceSettings.voiceName = voicePreference.value;
  saveVoiceSettings();
});
voiceRate.addEventListener("input", () => {
  voiceSettings.rate = Number(voiceRate.value);
  voiceRateValue.textContent = `${voiceSettings.rate.toFixed(2)}×`;
  saveVoiceSettings();
});
voiceInputMode.addEventListener("change", () => {
  voiceSettings.inputMode = voiceInputMode.value;
  saveVoiceSettings();
});
interruptSensitivity.addEventListener("input", () => {
  voiceSettings.sensitivity = Number(interruptSensitivity.value);
  interruptValue.textContent = ["Gentle", "Balanced", "Immediate"][voiceSettings.sensitivity - 1];
  saveVoiceSettings();
});
autoSpeakToggle.addEventListener("click", () => {
  voiceSettings.autoSpeak = autoSpeakToggle.getAttribute("aria-checked") === "true";
  saveVoiceSettings();
});
captionsToggle.addEventListener("click", () => {
  voiceSettings.captions = captionsToggle.getAttribute("aria-checked") === "true";
  body.classList.toggle("captions-hidden", !voiceSettings.captions);
  saveVoiceSettings();
});

function enhanceExistingMessages() {
  conversationJournal.querySelectorAll(".user-turn").forEach((turn) => {
    if (!turn.querySelector(".message-actions")) turn.append(createMessageActions("user"));
  });
  conversationJournal.querySelectorAll(".aika-turn").forEach((turn) => {
    if (!turn.classList.contains("work-result-turn") && !turn.querySelector(".message-actions")) turn.append(createMessageActions("aika"));
  });
}

function nearestUserText(turn) {
  let candidate = turn.previousElementSibling;
  while (candidate) {
    if (candidate.classList?.contains("user-turn")) return candidate.querySelector("p")?.textContent || "Continue our conversation";
    candidate = candidate.previousElementSibling;
  }
  return "Continue our conversation";
}

function beginMessageEdit(turn) {
  if (turn.querySelector(".message-editor")) return;
  const message = turn.querySelector("p");
  if (!message) return;
  message.hidden = true;
  const form = document.createElement("form");
  form.className = "message-editor";
  const input = document.createElement("textarea");
  input.value = message.textContent;
  input.rows = 3;
  const actions = document.createElement("div");
  actions.innerHTML = '<button type="button" data-edit-cancel>Cancel</button><button type="submit">Create branch</button>';
  form.append(input, actions);
  message.after(form);
  input.focus();
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const edited = input.value.trim();
    if (!edited) return;
    if (!turn.querySelector(".branch-label")) {
      const originalBranch = document.createElement("span");
      originalBranch.className = "branch-label";
      originalBranch.textContent = "Version 1 of 2";
      turn.append(originalBranch);
      const originalRecord = conversationRecords.find((record) => record.id === turn.dataset.recordId);
      if (originalRecord) {
        originalRecord.branch = "Version 1 of 2";
        storeConversationRecords();
      }
    }
    addConversationRecord({ type: "user", text: edited, meta: "Edited branch · just now", branch: "Version 2 of 2" });
    appendAikaReply(chooseReply(edited), expressionForThought(edited));
    form.remove();
    message.hidden = false;
    scrollConversationToEnd();
  });
  form.querySelector("[data-edit-cancel]").addEventListener("click", () => {
    form.remove();
    message.hidden = false;
  });
}

conversationJournal.addEventListener("click", (event) => {
  const attachmentAction = event.target.closest("[data-attachment-action]");
  if (attachmentAction) {
    const turn = attachmentAction.closest(".attachment-turn");
    const id = turn.dataset.recordId;
    if (attachmentAction.dataset.attachmentAction === "remove") {
      conversationRecords = conversationRecords.filter((record) => record.id !== id);
      storeConversationRecords();
      turn.remove();
      updateConversationDensity();
      thoughtStatus.textContent = "Attachment removed from this prototype conversation.";
    } else {
      attachmentReplaceTargetId = id;
      attachmentInput.multiple = false;
      attachmentInput.click();
      window.setTimeout(() => { attachmentInput.multiple = true; }, 0);
    }
    return;
  }

  const stopStream = event.target.closest("[data-stop-stream]");
  if (stopStream) {
    stopActiveStream();
    return;
  }

  const messageAction = event.target.closest("[data-message-action]");
  if (messageAction) {
    const turn = messageAction.closest(".conversation-turn");
    const action = messageAction.dataset.messageAction;
    const copy = turn.querySelector(".journal-aika-copy, .update-copy, p")?.textContent?.trim() || "";
    if (action === "copy") {
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(copy).then(
          () => { thoughtStatus.textContent = "Message copied."; },
          () => { thoughtStatus.textContent = "Copy was unavailable in this browser."; },
        );
      } else {
        thoughtStatus.textContent = "Copy was unavailable in this browser.";
      }
    } else if (action === "edit") {
      beginMessageEdit(turn);
    } else if (action === "continue") {
      thoughtInput.value = `Continue from: ${copy}`;
      resizeThoughtInput();
      thoughtInput.focus();
    } else if (action === "retry") {
      const source = nearestUserText(turn);
      const retry = chooseReply(source);
      retry.lead = "Here’s another way I can approach it.";
      retry.title = `${retry.title} — another version`;
      appendAikaReply(retry, expressionForThought(source));
    } else if (action === "memory") {
      let saved = [];
      try {
        const parsed = JSON.parse(readPreference("aika-saved-message-memory") || "[]");
        if (Array.isArray(parsed)) saved = parsed;
      } catch {
        saved = [];
      }
      saved.push({ text: copy, savedAt: new Date().toISOString() });
      savePreference("aika-saved-message-memory", JSON.stringify(saved.slice(-20)));
      messageAction.textContent = "Saved";
      messageAction.disabled = true;
      thoughtStatus.textContent = "This response was saved to the prototype’s local Memory Garden.";
    }
    return;
  }

  const resultAction = event.target.closest("[data-result-action]");
  if (resultAction) {
    if (resultAction.dataset.resultAction === "review") {
      workPresence.hidden = false;
      workPresence.querySelector(".work-details").open = true;
      workPresence.scrollIntoView({ behavior: "smooth", block: "center" });
      thoughtStatus.textContent = "The prototype work details are open for review.";
    } else {
      thoughtStatus.textContent = "Result preview selected. A live AIKA task would open the created artifact here.";
    }
    return;
  }

  const approval = event.target.closest("[data-approval]");
  if (approval) {
    const card = approval.closest(".conversation-event");
    if (approval.dataset.approval === "review") {
      card.classList.add("is-reviewed");
      card.querySelector("p").textContent = "Proposed scope: index.html, styles.css, and script.js inside the local prototype folder only.";
      thoughtStatus.textContent = "The proposed scope is now visible. Nothing has been approved yet.";
    } else if (approval.dataset.approval === "allow") {
      card.classList.add("is-resolved");
      card.querySelector("small").textContent = "Approved by you";
      card.querySelector("h3").textContent = "Protected work may continue";
      card.querySelector("p").textContent = "The approval applies only to the scope shown in this conversation event.";
      card.querySelector("footer").remove();
      startWorkDemo();
    } else {
      card.classList.add("is-resolved");
      card.querySelector("small").textContent = "Not approved";
      card.querySelector("h3").textContent = "The protected action is waiting";
      card.querySelector("p").textContent = "No protected change was made. You can return to this request later.";
      card.querySelector("footer").remove();
    }
    return;
  }

  const recovery = event.target.closest("[data-event-recovery]");
  if (recovery) {
    const card = recovery.closest(".conversation-event");
    card.classList.add("is-resolved");
    card.querySelector("small").textContent = "Recovered";
    card.querySelector("h3").textContent = recovery.dataset.eventRecovery === "offline" ? "Continuing with local abilities" : "The failed step is ready to retry";
    card.querySelector("p").textContent = "The conversation stayed intact and completed progress was preserved.";
    recovery.remove();
    playCharacterReaction("happy");
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== thoughtInput) {
    event.preventDefault();
    thoughtInput.focus();
  }
  if (event.key === "Escape") {
    if (historyIsOpen()) {
      closeSessionHistory();
      conversationHistoryToggle.focus();
    } else if (!voiceSession.hidden) {
      finishVoiceDemo();
    } else if (!composerTray.hidden) {
      composerTray.hidden = true;
      composerAdd.setAttribute("aria-expanded", "false");
    } else if (!moreMenu.hidden) {
      setMoreMenu(false);
    } else if (!body.classList.contains("rail-collapsed")) {
      setRail(true);
    }
  }
});

document.addEventListener("click", (event) => {
  if (!moreMenu.hidden && !moreMenu.contains(event.target) && !moreToggle.contains(event.target)) {
    setMoreMenu(false);
  }
  if (!composerTray.hidden && !composerTray.contains(event.target) && !composerAdd.contains(event.target)) {
    composerTray.hidden = true;
    composerAdd.setAttribute("aria-expanded", "false");
  }
  if (!conversationMoreMenu.hidden && !conversationMoreMenu.contains(event.target) && !conversationMoreToggle.contains(event.target)) {
    conversationMoreMenu.hidden = true;
    conversationMoreToggle.setAttribute("aria-expanded", "false");
  }
});

setTheme(readPreference("aika-living-desk-theme") || "twilight");
const savedRailState = readPreference("aika-awareness-collapsed-v2");
setRail(savedRailState === null ? true : savedRailState === "true");
updateAmbientTime();
resizeThoughtInput();
characterPortrait.dataset.expression = "calm";
setExpression("calm");
setCharacterMotion("idle");
switchSpace(currentSpace);
sessionStore = readSessionStore();
renderActiveSession();
body.classList.toggle("comfort-text", readPreference("aika-comfort-text") === "true");
comfortTextToggle.classList.toggle("is-active", body.classList.contains("comfort-text"));
if (body.classList.contains("comfort-text")) comfortTextToggle.querySelector("small").textContent = "Readability increased";
loadVoiceSettings();
populateVoiceOptions();
if ("speechSynthesis" in window) window.speechSynthesis.onvoiceschanged = populateVoiceOptions;
restoreWorkState();
updateConversationDensity();
thoughtStatus.textContent = "";
