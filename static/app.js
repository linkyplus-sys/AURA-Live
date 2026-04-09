const STORAGE_KEYS = {
  backgroundUrl: "aura-live.background-url",
  petOffset: "aura-live.pet-offset",
};

const BACKGROUND_PRESETS = [
  {
    label: "林间雾光",
    url: "https://images.unsplash.com/photo-1518531933037-91b2f5f229cc?q=80&w=2000",
  },
  {
    label: "夜色海岸",
    url: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?q=80&w=2000",
  },
  {
    label: "静谧房间",
    url: "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=2000",
  },
];

const state = {
  history: [],
  soulName: "AURA",
  runtime: {
    healthy: false,
    error: "",
    models: [],
    current_model: "",
    memory_count: 0,
    memory_error: "",
    base_url: "",
  },
  sending: false,
  streaming: null,
  stickToBottom: true,
  backgroundUrl: BACKGROUND_PRESETS[0].url,
  petOffset: { x: 0, y: 0 },
  petDrag: null,
};

const elements = {
  dynamicBg: document.getElementById("dynamicBg"),
  settingsFab: document.getElementById("settingsFab"),
  quickSettings: document.getElementById("quickSettings"),
  closeQuickSettingsBtn: document.getElementById("closeQuickSettingsBtn"),
  backgroundInput: document.getElementById("backgroundInput"),
  backgroundPresets: document.getElementById("backgroundPresets"),
  applyBackgroundBtn: document.getElementById("applyBackgroundBtn"),
  chatLayout: document.getElementById("chatLayout"),
  heroTitle: document.getElementById("heroTitle"),
  heroStatus: document.getElementById("heroStatus"),
  petFloatImage: document.getElementById("petFloatImage"),
  petFloatFallback: document.getElementById("petFloatFallback"),
  petFloatName: document.getElementById("petFloatName"),
  petCard: document.getElementById("petCard"),
  petHandle: document.getElementById("petHandle"),
  healthBadge: document.getElementById("healthBadge"),
  memoryBadge: document.getElementById("memoryBadge"),
  runtimeModel: document.getElementById("runtimeModel"),
  notice: document.getElementById("notice"),
  messageList: document.getElementById("messageList"),
  messageTemplate: document.getElementById("messageTemplate"),
  chatForm: document.getElementById("chatForm"),
  chatInput: document.getElementById("chatInput"),
  sendButton: document.getElementById("sendButton"),
};

function readStorage(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : raw;
  } catch (error) {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    // Ignore storage failures in constrained environments.
  }
}

function showNotice(message, type = "success") {
  if (!message) {
    hideNotice();
    return;
  }

  elements.notice.textContent = message;
  elements.notice.hidden = false;
  elements.notice.className = `notice notice-${type}`;
}

function hideNotice() {
  elements.notice.hidden = true;
  elements.notice.textContent = "";
  elements.notice.className = "notice";
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function isActionSegment(segment) {
  return /^[（(][^（）()]+[）)]$/.test(segment.trim());
}

function rewriteFirstPersonAction(innerText) {
  const subject = (state.soulName || "AURA").trim() || "AURA";
  return innerText
    .replace(/我自己/g, `${subject}自己`)
    .replace(/我的/g, `${subject}的`)
    .replace(/我会/g, `${subject}会`)
    .replace(/我在/g, `${subject}在`)
    .replace(/我正/g, `${subject}正`)
    .replace(/我向/g, `${subject}向`)
    .replace(/我把/g, `${subject}把`)
    .replace(/我轻/g, `${subject}轻`)
    .replace(/我慢/g, `${subject}慢`)
    .replace(/我抬/g, `${subject}抬`)
    .replace(/我伸/g, `${subject}伸`)
    .replace(/我低/g, `${subject}低`)
    .replace(/我看/g, `${subject}看`)
    .replace(/我听/g, `${subject}听`)
    .replace(/(^|[，。；、\s])我(?=[，。；、\s]|$)/g, `$1${subject}`);
}

function normalizeActionSegment(segment) {
  const trimmed = segment.trim();
  if (!isActionSegment(trimmed)) {
    return trimmed;
  }

  const open = trimmed[0];
  const close = trimmed[trimmed.length - 1];
  const inner = rewriteFirstPersonAction(trimmed.slice(1, -1).trim()).replace(/\s+/g, " ").trim();
  return `${open}${inner}${close}`;
}

function renderInlineMarkdown(rawText) {
  let html = escapeHtml(rawText).replace(/```/g, "");
  const codeTokens = [];

  html = html.replace(/`([^`]+)`/g, (_, code) => {
    const token = `@@CODE_${codeTokens.length}@@`;
    codeTokens.push(`<code>${code}</code>`);
    return token;
  });

  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__([^_\n]+)__/g, "<strong>$1</strong>");
  html = html.replace(/~~([^~\n]+)~~/g, "<del>$1</del>");
  html = html.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  html = html.replace(/_([^_\n]+)_/g, "<em>$1</em>");

  codeTokens.forEach((token, index) => {
    html = html.replaceAll(`@@CODE_${index}@@`, token);
  });

  return html;
}

function renderRichParagraph(paragraph) {
  const trimmed = paragraph.trim();
  if (!trimmed) {
    return '<div class="message-paragraph"><br></div>';
  }
  if (/^###\s+/.test(trimmed)) {
    return `<div class="message-paragraph"><span class="md-heading md-heading-3">${renderInlineMarkdown(trimmed.replace(/^###\s+/, ""))}</span></div>`;
  }
  if (/^##\s+/.test(trimmed)) {
    return `<div class="message-paragraph"><span class="md-heading md-heading-2">${renderInlineMarkdown(trimmed.replace(/^##\s+/, ""))}</span></div>`;
  }
  if (/^#\s+/.test(trimmed)) {
    return `<div class="message-paragraph"><span class="md-heading md-heading-1">${renderInlineMarkdown(trimmed.replace(/^#\s+/, ""))}</span></div>`;
  }
  if (/^>\s+/.test(trimmed)) {
    return `<div class="message-paragraph"><span class="md-quote">${renderInlineMarkdown(trimmed.replace(/^>\s+/, ""))}</span></div>`;
  }
  if (/^[-*]\s+/.test(trimmed)) {
    return `<div class="message-paragraph"><span class="md-bullet">• ${renderInlineMarkdown(trimmed.replace(/^[-*]\s+/, ""))}</span></div>`;
  }

  const parts = paragraph.split(/([（(][^（）()]+[）)])/g).filter(Boolean);
  const html = parts
    .map((part) => {
      if (isActionSegment(part)) {
        return `<span class="message-action-inline">${escapeHtml(normalizeActionSegment(part))}</span>`;
      }
      return renderInlineMarkdown(part);
    })
    .join("");

  return `<div class="message-paragraph">${html}</div>`;
}

function renderAssistantBody(text) {
  return String(text)
    .split(/\n/)
    .map((paragraph) => renderRichParagraph(paragraph))
    .join("");
}

function renderUserBody(text) {
  return escapeHtml(text).replaceAll("\n", "<br>");
}

function isNearBottom() {
  const list = elements.messageList;
  return list.scrollHeight - list.scrollTop - list.clientHeight < 120;
}

function scrollToBottom(force = false) {
  if (!force && !state.stickToBottom) {
    return;
  }
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function buildMessageElement(message, { streaming = false } = {}) {
  const fragment = elements.messageTemplate.content.cloneNode(true);
  const article = fragment.querySelector(".message-bubble");
  const body = fragment.querySelector(".message-body");
  const actions = fragment.querySelector(".message-actions");
  const regenerateButton = fragment.querySelector(".message-regenerate");
  const isUser = message.role === "user";

  article.classList.add(isUser ? "message-user" : "message-assistant");
  article.dataset.role = message.role;
  if (streaming) {
    article.classList.add("message-streaming");
  }
  if (isUser && actions) {
    actions.remove();
  } else if (regenerateButton) {
    regenerateButton.disabled = state.sending;
  }

  body.innerHTML = isUser ? renderUserBody(message.content) : renderAssistantBody(message.content);
  return { fragment, article, body };
}

function createEmptyState() {
  const empty = document.createElement("div");
  empty.className = "message-empty";
  empty.setAttribute("aria-hidden", "true");
  return empty;
}

function syncLatestAssistantActions() {
  const assistantMessages = [
    ...elements.messageList.querySelectorAll(".message-bubble.message-assistant"),
  ];
  assistantMessages.forEach((article) => {
    article.classList.remove("message-latest-assistant");
    const button = article.querySelector(".message-regenerate");
    if (button) {
      button.disabled = state.sending;
    }
  });

  for (let index = assistantMessages.length - 1; index >= 0; index -= 1) {
    const article = assistantMessages[index];
    if (article.classList.contains("message-streaming")) {
      continue;
    }
    article.classList.add("message-latest-assistant");
    break;
  }
}

function renderMessages() {
  elements.messageList.innerHTML = "";

  if (!state.history.length) {
    elements.messageList.appendChild(createEmptyState());
    syncLatestAssistantActions();
    return;
  }

  state.history.forEach((message) => {
    const { fragment } = buildMessageElement(message);
    elements.messageList.appendChild(fragment);
  });

  syncLatestAssistantActions();
  scrollToBottom(true);
}

function appendMessage(message, options = {}) {
  const { fragment, article, body } = buildMessageElement(message, options);
  const empty = elements.messageList.querySelector(".message-empty");
  if (empty) {
    empty.remove();
  }

  elements.messageList.appendChild(fragment);
  syncLatestAssistantActions();
  scrollToBottom(options.forceScroll ?? true);
  return { article, body };
}

function setBusy(isBusy) {
  state.sending = isBusy;
  elements.sendButton.disabled = isBusy;
  elements.chatInput.disabled = isBusy;
  syncLatestAssistantActions();
}

function refreshRuntimeUI() {
  elements.healthBadge.textContent = state.runtime.healthy ? "Ollama 在线" : "Ollama 未连接";
  elements.healthBadge.className = `glass-pill status-pill ${state.runtime.healthy ? "status-online" : "status-offline"}`;
  elements.memoryBadge.textContent = `记忆 ${state.runtime.memory_count ?? 0}`;
  elements.runtimeModel.textContent = state.runtime.current_model || "未选择模型";
  elements.heroStatus.textContent = state.runtime.healthy ? "在线陪伴" : "等待连接";
}

function syncPetPreview(imageName, fallbackText) {
  elements.petFloatFallback.textContent = (fallbackText || "A").slice(0, 1).toUpperCase();
  if (!imageName) {
    elements.petFloatImage.hidden = true;
    elements.petFloatFallback.hidden = false;
    return;
  }

  elements.petFloatImage.src = `/avatars/${encodeURIComponent(imageName)}`;
  elements.petFloatImage.hidden = false;
  elements.petFloatImage.onerror = () => {
    elements.petFloatImage.hidden = true;
    elements.petFloatFallback.hidden = false;
  };
  elements.petFloatImage.onload = () => {
    elements.petFloatImage.hidden = false;
    elements.petFloatFallback.hidden = true;
  };
}

function updatePresence(soul) {
  state.soulName = soul.name || "AURA";
  elements.heroTitle.textContent = state.soulName;
  elements.petFloatName.textContent = state.soulName;
  syncPetPreview(soul.pet_image || "", state.soulName);
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = "请求失败";
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (error) {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

function applyBootstrap(payload) {
  document.title = payload.app_title || "AURA Live";
  state.history = payload.history || [];
  state.runtime = payload.runtime || state.runtime;
  updatePresence(payload.soul || {});
  refreshRuntimeUI();
  renderMessages();

  if (state.runtime.error) {
    showNotice(state.runtime.error, "error");
    return;
  }
  if (state.runtime.memory_error) {
    showNotice(`记忆写入失败：${state.runtime.memory_error}`, "error");
    return;
  }
  hideNotice();
}

async function loadBootstrap() {
  hideNotice();
  try {
    const payload = await apiFetch("/api/bootstrap", { method: "GET" });
    applyBootstrap(payload);
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function autoResizeInput() {
  elements.chatInput.style.height = "0px";
  elements.chatInput.style.height = `${Math.min(elements.chatInput.scrollHeight, 160)}px`;
}

function createAssistantPlaceholder() {
  const placeholder = { role: "assistant", content: "" };
  state.history.push(placeholder);
  const refs = appendMessage(placeholder, { streaming: true, forceScroll: true });
  state.streaming = {
    message: placeholder,
    article: refs.article,
    body: refs.body,
    rafId: null,
    pendingContent: "",
  };
}

function flushStreamingContent() {
  if (!state.streaming) {
    return;
  }

  state.streaming.rafId = null;
  state.streaming.message.content = state.streaming.pendingContent;
  state.streaming.body.innerHTML = renderAssistantBody(state.streaming.pendingContent);
  scrollToBottom();
}

function appendStreamingChunk(chunk) {
  if (!state.streaming) {
    return;
  }

  state.streaming.pendingContent += chunk;
  if (state.streaming.rafId !== null) {
    return;
  }
  state.streaming.rafId = window.requestAnimationFrame(flushStreamingContent);
}

function finalizeStreaming(history, runtime) {
  if (!state.streaming) {
    state.history = history || state.history;
    state.runtime = runtime || state.runtime;
    refreshRuntimeUI();
    syncLatestAssistantActions();
    return;
  }

  if (state.streaming.rafId !== null) {
    window.cancelAnimationFrame(state.streaming.rafId);
    flushStreamingContent();
  }

  state.streaming.article.classList.remove("message-streaming");
  state.history = history || state.history;
  state.runtime = runtime || state.runtime;
  state.streaming = null;
  refreshRuntimeUI();
  syncLatestAssistantActions();
}

function removeStreamingPlaceholder() {
  if (!state.streaming) {
    return;
  }

  state.streaming.article.remove();
  state.history = state.history.filter((item) => item !== state.streaming.message);
  state.streaming = null;
  if (!state.history.length) {
    elements.messageList.appendChild(createEmptyState());
  }
  syncLatestAssistantActions();
}

function parseSseBlock(block) {
  const lines = block.split("\n");
  let event = "message";
  const dataLines = [];

  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  });

  if (!dataLines.length) {
    return null;
  }

  return {
    event,
    data: JSON.parse(dataLines.join("\n")),
  };
}

async function streamConversation(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    let detail = "聊天请求失败";
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (error) {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  createAssistantPlaceholder();

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      if (!block.trim()) {
        continue;
      }

      const packet = parseSseBlock(block);
      if (!packet) {
        continue;
      }

      if (packet.event === "status") {
        state.runtime = packet.data.runtime || state.runtime;
        refreshRuntimeUI();
        continue;
      }

      if (packet.event === "chunk") {
        appendStreamingChunk(packet.data.content || "");
        continue;
      }

      if (packet.event === "done") {
        finalizeStreaming(packet.data.history, packet.data.runtime);
        if (state.runtime.memory_error) {
          showNotice(`记忆写入失败：${state.runtime.memory_error}`, "error");
        } else {
          hideNotice();
        }
        continue;
      }

      if (packet.event === "error") {
        removeStreamingPlaceholder();
        throw new Error(packet.data.message || "对话失败");
      }
    }
  }
}

function findLatestAssistantTurn() {
  for (let index = state.history.length - 1; index > 0; index -= 1) {
    const current = state.history[index];
    const previous = state.history[index - 1];
    if (current?.role === "assistant" && previous?.role === "user") {
      return {
        assistantIndex: index,
        userIndex: index - 1,
        userMessage: previous.content || "",
      };
    }
  }
  return null;
}

async function submitChat(event) {
  event.preventDefault();
  if (state.sending) {
    return;
  }

  const message = elements.chatInput.value.trim();
  if (!message) {
    return;
  }

  hideNotice();
  state.stickToBottom = true;

  const userMessage = { role: "user", content: message };
  state.history.push(userMessage);
  appendMessage(userMessage, { forceScroll: true });

  elements.chatInput.value = "";
  autoResizeInput();
  setBusy(true);

  try {
    await streamConversation("/api/chat/stream", { message });
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    setBusy(false);
    elements.chatInput.focus();
  }
}

async function regenerateLatestReply() {
  if (state.sending) {
    return;
  }

  const latestTurn = findLatestAssistantTurn();
  if (!latestTurn) {
    showNotice("当前没有可重新生成的回复。", "error");
    return;
  }

  const snapshot = state.history.slice();
  hideNotice();
  state.stickToBottom = true;
  state.history.splice(latestTurn.assistantIndex, 1);
  renderMessages();
  setBusy(true);

  try {
    await streamConversation("/api/chat/regenerate", {});
  } catch (error) {
    state.history = snapshot;
    renderMessages();
    showNotice(error.message, "error");
  } finally {
    setBusy(false);
    elements.chatInput.focus();
  }
}

function handleInputKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    elements.chatForm.requestSubmit();
  }
}

function handleMessageListClick(event) {
  const regenerateButton = event.target.closest(".message-regenerate");
  if (!regenerateButton) {
    return;
  }
  event.preventDefault();
  regenerateLatestReply();
}

function applyBackground(url) {
  const nextUrl = (url || BACKGROUND_PRESETS[0].url).trim();
  state.backgroundUrl = nextUrl;
  elements.dynamicBg.style.backgroundImage = `url("${nextUrl.replaceAll('"', '\\"')}")`;
  elements.backgroundInput.value = nextUrl;
  writeStorage(STORAGE_KEYS.backgroundUrl, nextUrl);
  refreshBackgroundPresets();
}

function refreshBackgroundPresets() {
  const buttons = elements.backgroundPresets.querySelectorAll(".bg-preset");
  buttons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.bg === state.backgroundUrl);
  });
}

function renderBackgroundPresets() {
  elements.backgroundPresets.innerHTML = "";
  BACKGROUND_PRESETS.forEach((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "bg-preset";
    button.dataset.bg = preset.url;
    button.style.backgroundImage = `url("${preset.url.replaceAll('"', '\\"')}")`;

    const label = document.createElement("span");
    label.textContent = preset.label;
    button.appendChild(label);

    elements.backgroundPresets.appendChild(button);
  });
  refreshBackgroundPresets();
}

function openQuickSettings() {
  elements.quickSettings.classList.remove("hidden");
  elements.quickSettings.setAttribute("aria-hidden", "false");
  elements.backgroundInput.value = state.backgroundUrl;
}

function closeQuickSettings() {
  elements.quickSettings.classList.add("hidden");
  elements.quickSettings.setAttribute("aria-hidden", "true");
}

function toggleQuickSettings() {
  if (elements.quickSettings.classList.contains("hidden")) {
    openQuickSettings();
    return;
  }
  closeQuickSettings();
}

function clampPetOffset(x, y) {
  const card = elements.petCard;
  const layout = elements.chatLayout;
  const computed = window.getComputedStyle(card);
  const baseLeft = Number.parseFloat(computed.left) || 0;
  const baseTop = Number.parseFloat(computed.top) || 0;
  const availableX = Math.max(0, layout.clientWidth - baseLeft - card.offsetWidth - 12);
  const availableY = Math.max(0, layout.clientHeight - baseTop - card.offsetHeight - 12);

  return {
    x: Math.min(Math.max(0, x), availableX),
    y: Math.min(Math.max(0, y), availableY),
  };
}

function applyPetOffset(x, y, persist = true) {
  const next = clampPetOffset(x, y);
  state.petOffset = next;
  elements.petCard.style.transform = `translate3d(${next.x}px, ${next.y}px, 0)`;
  if (persist) {
    writeStorage(STORAGE_KEYS.petOffset, JSON.stringify(next));
  }
}

function restorePetOffset() {
  try {
    const raw = readStorage(STORAGE_KEYS.petOffset, "");
    if (!raw) {
      applyPetOffset(0, 0, false);
      return;
    }
    const parsed = JSON.parse(raw);
    applyPetOffset(Number(parsed.x) || 0, Number(parsed.y) || 0, false);
  } catch (error) {
    applyPetOffset(0, 0, false);
  }
}

function beginPetDrag(event) {
  if (event.button !== undefined && event.button !== 0) {
    return;
  }
  event.preventDefault();
  elements.petCard.classList.add("is-dragging");
  state.petDrag = {
    startX: event.clientX,
    startY: event.clientY,
    originX: state.petOffset.x,
    originY: state.petOffset.y,
  };
}

function onPetDrag(event) {
  if (!state.petDrag) {
    return;
  }

  const nextX = state.petDrag.originX + (event.clientX - state.petDrag.startX);
  const nextY = state.petDrag.originY + (event.clientY - state.petDrag.startY);
  applyPetOffset(nextX, nextY, false);
}

function endPetDrag() {
  if (!state.petDrag) {
    return;
  }

  elements.petCard.classList.remove("is-dragging");
  state.petDrag = null;
  writeStorage(STORAGE_KEYS.petOffset, JSON.stringify(state.petOffset));
}

function bindEvents() {
  elements.chatForm.addEventListener("submit", submitChat);
  elements.chatInput.addEventListener("input", autoResizeInput);
  elements.chatInput.addEventListener("keydown", handleInputKeydown);
  elements.messageList.addEventListener("click", handleMessageListClick);
  elements.messageList.addEventListener("scroll", () => {
    state.stickToBottom = isNearBottom();
  });

  elements.settingsFab.addEventListener("click", toggleQuickSettings);
  elements.closeQuickSettingsBtn.addEventListener("click", closeQuickSettings);
  elements.applyBackgroundBtn.addEventListener("click", () => {
    applyBackground(elements.backgroundInput.value.trim() || BACKGROUND_PRESETS[0].url);
    closeQuickSettings();
  });
  elements.backgroundInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyBackground(elements.backgroundInput.value.trim() || BACKGROUND_PRESETS[0].url);
      closeQuickSettings();
    }
  });
  elements.backgroundPresets.addEventListener("click", (event) => {
    const button = event.target.closest(".bg-preset");
    if (!button) {
      return;
    }
    applyBackground(button.dataset.bg || BACKGROUND_PRESETS[0].url);
  });

  document.addEventListener("click", (event) => {
    if (elements.quickSettings.classList.contains("hidden")) {
      return;
    }
    if (
      elements.quickSettings.contains(event.target) ||
      elements.settingsFab.contains(event.target)
    ) {
      return;
    }
    closeQuickSettings();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeQuickSettings();
    }
  });

  elements.petHandle.addEventListener("pointerdown", beginPetDrag);
  window.addEventListener("pointermove", onPetDrag);
  window.addEventListener("pointerup", endPetDrag);
  window.addEventListener("pointercancel", endPetDrag);
  window.addEventListener("resize", () => {
    applyPetOffset(state.petOffset.x, state.petOffset.y, false);
  });
}

function initUiState() {
  renderBackgroundPresets();
  applyBackground(readStorage(STORAGE_KEYS.backgroundUrl, BACKGROUND_PRESETS[0].url));
  restorePetOffset();
  autoResizeInput();
}

bindEvents();
initUiState();
loadBootstrap();
