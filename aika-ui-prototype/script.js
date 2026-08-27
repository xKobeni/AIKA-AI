const body = document.body;
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const contextPanel = document.getElementById("contextPanel");
const toggleContext = document.getElementById("toggleContext");
const form = document.getElementById("composerForm");
const input = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const messageThread = document.getElementById("messageThread");
const welcomePanel = document.getElementById("welcomePanel");
const conversationScroll = document.getElementById("conversationScroll");
const messageCount = document.getElementById("messageCount");
const viewTitle = document.getElementById("viewTitle");
const root = document.documentElement;

let visibleMessageCount = 0;
let responseTimer;

const viewLabels = {
  chat: "Conversation",
  memory: "Memory",
  tasks: "Tasks",
  agents: "Agents",
  research: "Research",
  library: "Library",
  system: "System",
  settings: "Settings",
};

function getSavedTheme() {
  try {
    return localStorage.getItem("aika-prototype-theme");
  } catch {
    return null;
  }
}

function setTheme(theme) {
  const nextTheme = theme === "light" ? "light" : "dark";
  root.dataset.theme = nextTheme;

  try {
    localStorage.setItem("aika-prototype-theme", nextTheme);
  } catch {
    // The visual toggle still works if browser storage is unavailable.
  }

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    const lightActive = nextTheme === "light";
    button.setAttribute("aria-label", lightActive ? "Switch to dark mode" : "Switch to light mode");
    button.title = lightActive ? "Switch to dark mode" : "Switch to light mode";
    button.querySelector(".theme-toggle__icon").textContent = lightActive ? "☾" : "☼";
  });

  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    const selected = button.dataset.themeChoice === nextTheme;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function toggleTheme() {
  setTheme(root.dataset.theme === "light" ? "dark" : "light");
}

const sampleReplies = [
  {
    match: ["plan", "next step", "priority"],
    text: "That could work. I’d keep the next step small: first decide which part of the AIKA experience you want to validate—conversation, memory, or task handling. For this prototype, conversation is the strongest place to begin because it defines how everything else should feel.",
    signal: "Planning · no tools used",
  },
  {
    match: ["remember", "memory", "project"],
    text: "The useful thread I’m holding onto is that you want AIKA to feel personal, capable, and honest—not like a generic chatbot. You also prefer incremental changes with clear verification before moving into the next phase.",
    signal: "1 relevant memory · prototype response",
  },
  {
    match: ["research", "source", "web"],
    text: "I can help research that and keep the sources visible beside the answer. In the finished interface, I’d show search activity quietly, then attach a compact source drawer so the response stays readable.",
    signal: "Research preview · no live search performed",
  },
];

function setGreeting() {
  const hour = new Date().getHours();
  const label = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  document.getElementById("timeGreeting").textContent = label;
}

function resizeComposer() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
  sendButton.disabled = input.value.trim().length === 0;
}

function scrollToLatest() {
  requestAnimationFrame(() => {
    conversationScroll.scrollTo({ top: conversationScroll.scrollHeight, behavior: "smooth" });
  });
}

function timeNow() {
  return new Intl.DateTimeFormat([], { hour: "numeric", minute: "2-digit" }).format(new Date());
}

function createMessage(role, text, signal = "") {
  const article = document.createElement("article");
  article.className = `message message--${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message__avatar";
  avatar.textContent = role === "assistant" ? "AI" : "A";

  const content = document.createElement("div");
  const meta = document.createElement("div");
  meta.className = "message__meta";

  const author = document.createElement("strong");
  author.textContent = role === "assistant" ? "AIKA" : "You";
  const time = document.createElement("time");
  time.textContent = timeNow();
  meta.append(author, time);

  const bodyCopy = document.createElement("div");
  bodyCopy.className = "message__body";
  bodyCopy.textContent = text;
  content.append(meta, bodyCopy);

  if (signal) {
    const status = document.createElement("div");
    status.className = "message__signal";
    status.textContent = signal;
    content.append(status);
  }

  article.append(avatar, content);
  return article;
}

function createTypingMessage() {
  const article = createMessage("assistant", "");
  article.id = "typingMessage";
  const bodyCopy = article.querySelector(".message__body");
  bodyCopy.innerHTML = '<span class="typing-dots" aria-label="AIKA is responding"><i></i><i></i><i></i></span>';
  return article;
}

function chooseReply(message) {
  const normalized = message.toLowerCase();
  return (
    sampleReplies.find((reply) => reply.match.some((term) => normalized.includes(term))) || {
      text: "I see what you’re trying to do. For this prototype I’m keeping the response simple, but the interaction is designed to support real streaming replies, tool activity, memory context, and approvals when it connects to the AIKA service.",
      signal: "Conversation · prototype response",
    }
  );
}

function sendMessage(message) {
  const cleanMessage = message.trim();
  if (!cleanMessage) return;

  clearTimeout(responseTimer);
  document.getElementById("typingMessage")?.remove();
  welcomePanel.hidden = true;
  messageThread.append(createMessage("user", cleanMessage));
  visibleMessageCount += 1;
  messageCount.textContent = visibleMessageCount;

  input.value = "";
  resizeComposer();
  messageThread.append(createTypingMessage());
  scrollToLatest();

  const reply = chooseReply(cleanMessage);
  responseTimer = window.setTimeout(() => {
    document.getElementById("typingMessage")?.remove();
    messageThread.append(createMessage("assistant", reply.text, reply.signal));
    visibleMessageCount += 1;
    messageCount.textContent = visibleMessageCount;
    scrollToLatest();
  }, 850);
}

function switchView(view) {
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("is-visible", panel.dataset.viewPanel === view);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    const active = item.dataset.view === view;
    item.classList.toggle("is-active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  viewTitle.textContent = viewLabels[view];
  closeSidebar();
}

function openSidebar() {
  sidebar.classList.add("is-open");
  sidebarBackdrop.classList.add("is-visible");
}

function closeSidebar() {
  sidebar.classList.remove("is-open");
  sidebarBackdrop.classList.remove("is-visible");
}

function setContextVisibility(visible) {
  contextPanel.classList.toggle("is-hidden", !visible);
  body.classList.toggle("context-hidden", !visible);
  toggleContext.setAttribute("aria-expanded", String(visible));
}

function resetConversation() {
  clearTimeout(responseTimer);
  messageThread.replaceChildren();
  welcomePanel.hidden = false;
  visibleMessageCount = 0;
  messageCount.textContent = "0";
  switchView("chat");
  input.value = "";
  resizeComposer();
  input.focus();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("input", resizeComposer);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== input) {
    event.preventDefault();
    switchView("chat");
    input.focus();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n") {
    event.preventDefault();
    resetConversation();
  }
  if (event.key === "Escape") closeSidebar();
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.prompt));
});

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.querySelectorAll(".task-check").forEach((button) => {
  button.addEventListener("click", () => {
    const row = button.closest(".task-row");
    const checked = button.getAttribute("aria-pressed") === "true";
    button.setAttribute("aria-pressed", String(!checked));
    button.textContent = checked ? "" : "✓";
    row.style.opacity = checked ? "1" : "0.52";
  });
});

document.querySelectorAll(".switch").forEach((button) => {
  button.addEventListener("click", () => {
    const nextState = button.getAttribute("aria-checked") !== "true";
    button.setAttribute("aria-checked", String(nextState));
    button.classList.toggle("is-on", nextState);
  });
});

document.querySelectorAll(".view-tab").forEach((button) => {
  button.addEventListener("click", () => {
    button.parentElement.querySelectorAll(".view-tab").forEach((tab) => tab.classList.remove("is-active"));
    button.classList.add("is-active");
  });
});

document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
  button.addEventListener("click", toggleTheme);
});

document.querySelectorAll("[data-theme-choice]").forEach((button) => {
  button.addEventListener("click", () => setTheme(button.dataset.themeChoice));
});

document.getElementById("researchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const researchInput = document.getElementById("researchInput");
  const topic = researchInput.value.trim();
  if (!topic) {
    researchInput.focus();
    return;
  }

  const title = document.getElementById("researchTitle");
  const summary = document.getElementById("researchSummary");
  const status = document.getElementById("researchStatus");
  title.textContent = topic;
  summary.textContent = "AIKA is mapping the topic, selecting search queries, and preparing a source-ranked report. This prototype simulates that workflow without making a live web request.";
  status.textContent = "Researching";
  status.classList.add("tag--active");

  window.setTimeout(() => {
    status.textContent = "Preview ready";
    summary.textContent = "The research workspace would combine web search, page crawling, relevance ranking, and a structured synthesis here. Every factual section can remain linked to its supporting sources.";
  }, 1100);
});

document.getElementById("newChatButton").addEventListener("click", resetConversation);
document.getElementById("openSidebar").addEventListener("click", openSidebar);
document.getElementById("closeSidebar").addEventListener("click", closeSidebar);
sidebarBackdrop.addEventListener("click", closeSidebar);
toggleContext.addEventListener("click", () => setContextVisibility(contextPanel.classList.contains("is-hidden")));
document.getElementById("closeContext").addEventListener("click", () => setContextVisibility(false));

setGreeting();
setTheme(getSavedTheme() || "dark");
resizeComposer();
