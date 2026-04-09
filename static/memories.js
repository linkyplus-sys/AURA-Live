const state = {
  memories: [],
  memoryCount: 0,
};

const elements = {
  notice: document.getElementById("notice"),
  memoryCountText: document.getElementById("memoryCountText"),
  memoryUpdatedText: document.getElementById("memoryUpdatedText"),
  refreshMemoriesBtn: document.getElementById("refreshMemoriesBtn"),
  memoriesList: document.getElementById("memoriesList"),
  memoryItemTemplate: document.getElementById("memoryItemTemplate"),
};

function showNotice(message, type = "success") {
  elements.notice.textContent = message;
  elements.notice.hidden = false;
  elements.notice.className = `notice notice-${type}`;
}

function hideNotice() {
  elements.notice.hidden = true;
  elements.notice.textContent = "";
  elements.notice.className = "notice";
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

  return response.json();
}

function formatDate(value) {
  if (!value) {
    return "未记录时间";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function fillDetailSection(article, field, value) {
  const section = article.querySelector(`[data-field="${field}"]`);
  if (!section) {
    return;
  }

  const text = String(value || "").trim();
  if (!text) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  section.querySelector("p").textContent = text;
}

function renderMemories() {
  elements.memoriesList.innerHTML = "";
  elements.memoryCountText.textContent = `记忆 ${state.memoryCount}`;
  elements.memoryUpdatedText.textContent = `最后刷新 ${formatDate(new Date().toISOString())}`;

  if (!state.memories.length) {
    const empty = document.createElement("div");
    empty.className = "memory-empty";
    empty.textContent = "当前还没有可展示的长期记忆。";
    elements.memoriesList.appendChild(empty);
    return;
  }

  state.memories.forEach((memory) => {
    const fragment = elements.memoryItemTemplate.content.cloneNode(true);
    const article = fragment.querySelector(".memory-item");
    const category = fragment.querySelector(".memory-category");
    const score = fragment.querySelector(".memory-score");
    const time = fragment.querySelector(".memory-time");
    const summary = fragment.querySelector(".memory-summary");
    const key = fragment.querySelector(".memory-key");

    category.textContent = memory.category || "general";
    score.textContent = `score ${memory.score ?? 0}`;
    time.textContent = formatDate(memory.updated_at || memory.created_at);
    summary.textContent = memory.summary || "未生成摘要";
    key.textContent = memory.key ? `key: ${memory.key}` : "";
    key.hidden = !memory.key;

    fillDetailSection(article, "user_memory", memory.user_memory);
    fillDetailSection(article, "bot_memory", memory.bot_memory);
    fillDetailSection(article, "user_text", memory.user_text);
    fillDetailSection(article, "bot_text", memory.bot_text);

    elements.memoriesList.appendChild(fragment);
  });
}

async function loadMemories() {
  hideNotice();
  elements.refreshMemoriesBtn.disabled = true;

  try {
    const payload = await apiFetch("/api/memories", { method: "GET" });
    state.memories = Array.isArray(payload.memories) ? payload.memories : [];
    state.memoryCount = Number(payload.memory_count ?? state.memories.length) || 0;
    renderMemories();
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    elements.refreshMemoriesBtn.disabled = false;
  }
}

elements.refreshMemoriesBtn.addEventListener("click", loadMemories);

loadMemories();
