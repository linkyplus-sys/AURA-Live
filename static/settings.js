const state = {
  runtime: {
    healthy: false,
    error: "",
    models: [],
    current_model: "",
    memory_count: 0,
  },
  history: [],
  worldbookEntries: [],
};

const elements = {
  notice: document.getElementById("notice"),
  petImage: document.getElementById("petImage"),
  petFallback: document.getElementById("petFallback"),
  petName: document.getElementById("petName"),
  soulForm: document.getElementById("soulForm"),
  soulName: document.getElementById("soulName"),
  soulPersonality: document.getElementById("soulPersonality"),
  soulStyle: document.getElementById("soulStyle"),
  soulScene: document.getElementById("soulScene"),
  soulImage: document.getElementById("soulImage"),
  worldbookForm: document.getElementById("worldbookForm"),
  worldbookEntries: document.getElementById("worldbookEntries"),
  worldbookEntryTemplate: document.getElementById("worldbookEntryTemplate"),
  addWorldbookEntryBtn: document.getElementById("addWorldbookEntryBtn"),
  runtimeBaseUrlInput: document.getElementById("runtimeBaseUrlInput"),
  saveBaseUrlBtn: document.getElementById("saveBaseUrlBtn"),
  modelSelect: document.getElementById("modelSelect"),
  saveModelBtn: document.getElementById("saveModelBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  clearMemoryBtn: document.getElementById("clearMemoryBtn"),
  healthBadge: document.getElementById("healthBadge"),
  memoryBadge: document.getElementById("memoryBadge"),
  runtimeModel: document.getElementById("runtimeModel"),
  runtimeModelsCount: document.getElementById("runtimeModelsCount"),
  runtimeHistoryCount: document.getElementById("runtimeHistoryCount"),
  runtimeBaseUrl: document.getElementById("runtimeBaseUrl"),
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

function updatePetPreview(imageName, fallbackText) {
  elements.petFallback.textContent = (fallbackText || "A").slice(0, 1).toUpperCase();
  if (!imageName) {
    elements.petImage.hidden = true;
    elements.petFallback.hidden = false;
    return;
  }

  elements.petImage.src = `/avatars/${encodeURIComponent(imageName)}`;
  elements.petImage.hidden = false;
  elements.petImage.onerror = () => {
    elements.petImage.hidden = true;
    elements.petFallback.hidden = false;
  };
  elements.petImage.onload = () => {
    elements.petImage.hidden = false;
    elements.petFallback.hidden = true;
  };
}

function fillSoulForm(soul) {
  elements.petName.textContent = soul.name || "AURA";
  elements.soulName.value = soul.name || "";
  elements.soulPersonality.value = soul.personality || "";
  elements.soulStyle.value = soul.style || "";
  elements.soulScene.value = soul.scene || "";
  elements.soulImage.value = soul.pet_image || "";
  updatePetPreview(soul.pet_image || "", soul.name || "A");
}

function normalizeKeywordList(rawKeywords, fallbackTitle = "") {
  if (Array.isArray(rawKeywords)) {
    return rawKeywords.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof rawKeywords === "string") {
    return rawKeywords
      .split(/[,\n，]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return fallbackTitle ? [fallbackTitle] : [];
}

function normalizeWorldbookEntry(entry, fallbackTitle = "") {
  if (!entry || typeof entry !== "object") {
    return null;
  }

  const title = String(entry.title || fallbackTitle || "").trim();
  const content = String(entry.content || "").trim();
  const keywords = normalizeKeywordList(entry.keywords, title || fallbackTitle);
  const always = Boolean(entry.always);

  if (!title && !content && !keywords.length) {
    return null;
  }

  return {
    title,
    keywords,
    content,
    always,
  };
}

function normalizeWorldbook(worldbook) {
  if (!worldbook || typeof worldbook !== "object") {
    return [];
  }

  if (Array.isArray(worldbook.entries)) {
    return worldbook.entries
      .map((entry) => normalizeWorldbookEntry(entry))
      .filter(Boolean);
  }

  return Object.entries(worldbook)
    .map(([key, value]) => {
      if (typeof value === "string") {
        return {
          title: key,
          keywords: [key],
          content: value,
          always: false,
        };
      }
      return normalizeWorldbookEntry(value, key);
    })
    .filter(Boolean);
}

function renderWorldbookEntries() {
  elements.worldbookEntries.innerHTML = "";

  if (!state.worldbookEntries.length) {
    const empty = document.createElement("div");
    empty.className = "worldbook-empty";
    empty.textContent = "暂无条目";
    elements.worldbookEntries.appendChild(empty);
    return;
  }

  state.worldbookEntries.forEach((entry, index) => {
    const fragment = elements.worldbookEntryTemplate.content.cloneNode(true);
    const article = fragment.querySelector(".worldbook-entry");
    const title = fragment.querySelector(".worldbook-title");
    const keywords = fragment.querySelector(".worldbook-keywords");
    const content = fragment.querySelector(".worldbook-content");
    const always = fragment.querySelector(".worldbook-always-input");
    const entryTitle = fragment.querySelector(".worldbook-entry-title");

    article.dataset.index = String(index);
    title.value = entry.title || "";
    keywords.value = (entry.keywords || []).join(", ");
    content.value = entry.content || "";
    always.checked = Boolean(entry.always);
    entryTitle.textContent = entry.title || `条目 ${index + 1}`;

    elements.worldbookEntries.appendChild(fragment);
  });
}

function fillWorldbook(worldbook) {
  state.worldbookEntries = normalizeWorldbook(worldbook);
  if (!state.worldbookEntries.length) {
    state.worldbookEntries = [
      {
        title: "",
        keywords: [],
        content: "",
        always: false,
      },
    ];
  }
  renderWorldbookEntries();
}

function buildWorldbookPayload() {
  const items = [...elements.worldbookEntries.querySelectorAll(".worldbook-entry")]
    .map((entry, index) => {
      const title = entry.querySelector(".worldbook-title")?.value.trim() || "";
      const content = entry.querySelector(".worldbook-content")?.value.trim() || "";
      const always = Boolean(entry.querySelector(".worldbook-always-input")?.checked);
      const keywords = normalizeKeywordList(
        entry.querySelector(".worldbook-keywords")?.value || "",
        title,
      );

      if (!title && !content && !keywords.length) {
        return null;
      }

      return {
        title: title || keywords[0] || `entry-${index + 1}`,
        keywords,
        content,
        always,
      };
    })
    .filter((item) => item && item.content);

  return { entries: items };
}

function addWorldbookEntry() {
  state.worldbookEntries.push({
    title: "",
    keywords: [],
    content: "",
    always: false,
  });
  renderWorldbookEntries();
}

function fillModels() {
  elements.modelSelect.innerHTML = "";
  const models = state.runtime.models || [];

  if (!models.length) {
    const option = document.createElement("option");
    option.value = state.runtime.current_model || "";
    option.textContent = state.runtime.current_model || "未获取到模型";
    elements.modelSelect.appendChild(option);
    return;
  }

  models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    elements.modelSelect.appendChild(option);
  });

  elements.modelSelect.value = models.includes(state.runtime.current_model)
    ? state.runtime.current_model
    : models[0];
}

function refreshRuntimeUI() {
  elements.healthBadge.textContent = state.runtime.healthy ? "Ollama 已连接" : "Ollama 未连接";
  elements.healthBadge.className = `status-pill ${state.runtime.healthy ? "status-online" : "status-offline"}`;
  elements.memoryBadge.textContent = `记忆 ${state.runtime.memory_count ?? 0}`;
  elements.runtimeModel.textContent = state.runtime.current_model || "未选择";
  elements.runtimeModelsCount.textContent = String(state.runtime.models?.length ?? 0);
  elements.runtimeHistoryCount.textContent = String(state.history.length);
  if (elements.runtimeBaseUrlInput) {
    elements.runtimeBaseUrlInput.value = state.runtime.base_url || "";
  }
  elements.runtimeBaseUrl.textContent = state.runtime.base_url || "未配置";
  elements.runtimeBaseUrl.title = state.runtime.base_url || "";
}

function applyBootstrap(payload) {
  document.title = `${payload.app_title || "AURA Live"} Settings`;
  state.runtime = payload.runtime || state.runtime;
  state.history = payload.history || [];
  fillSoulForm(payload.soul || {});
  fillWorldbook(payload.worldbook || {});
  fillModels();
  refreshRuntimeUI();

  if (state.runtime.error) {
    showNotice(state.runtime.error, "error");
    return;
  }
  if (state.runtime.memory_error) {
    showNotice(`记忆写入失败：${state.runtime.memory_error}`, "error");
  }
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

async function saveSoul(event) {
  event.preventDefault();
  hideNotice();

  const payload = {
    name: elements.soulName.value.trim(),
    personality: elements.soulPersonality.value.trim(),
    style: elements.soulStyle.value.trim(),
    scene: elements.soulScene.value.trim(),
    pet_image: elements.soulImage.value.trim(),
  };

  try {
    const data = await apiFetch("/api/config/soul", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    fillSoulForm(data.soul);
    showNotice("灵魂配置已保存。");
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function saveWorldbook(event) {
  event.preventDefault();
  hideNotice();

  const payload = buildWorldbookPayload();

  try {
    const data = await apiFetch("/api/config/worldbook", {
      method: "PUT",
      body: JSON.stringify({ entries: payload }),
    });
    fillWorldbook(data.worldbook);
    showNotice("世界书已保存。");
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function saveModel() {
  hideNotice();
  try {
    const data = await apiFetch("/api/runtime/model", {
      method: "PUT",
      body: JSON.stringify({ model: elements.modelSelect.value }),
    });
    state.runtime = data;
    fillModels();
    refreshRuntimeUI();
    showNotice("当前模型已保存。");
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function saveBaseUrl() {
  hideNotice();
  try {
    const data = await apiFetch("/api/runtime/base-url", {
      method: "PUT",
      body: JSON.stringify({ base_url: elements.runtimeBaseUrlInput.value.trim() }),
    });
    state.runtime = data;
    fillModels();
    refreshRuntimeUI();
    showNotice("服务地址已保存。");
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function clearHistory() {
  hideNotice();
  try {
    const data = await apiFetch("/api/history", { method: "DELETE" });
    state.history = data.history || [];
    refreshRuntimeUI();
    showNotice("对话历史已清空。");
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function clearMemory() {
  hideNotice();
  try {
    const data = await apiFetch("/api/memory", { method: "DELETE" });
    state.runtime.memory_count = data.memory_count ?? 0;
    refreshRuntimeUI();
    showNotice("记忆库已清空。");
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function handleWorldbookListClick(event) {
  const removeButton = event.target.closest(".worldbook-remove-btn");
  if (!removeButton) {
    return;
  }

  const entry = removeButton.closest(".worldbook-entry");
  if (!entry) {
    return;
  }

  const index = Number(entry.dataset.index || "-1");
  if (index < 0) {
    return;
  }

  state.worldbookEntries.splice(index, 1);
  if (!state.worldbookEntries.length) {
    addWorldbookEntry();
    return;
  }
  renderWorldbookEntries();
}

function handleWorldbookInput(event) {
  const entry = event.target.closest(".worldbook-entry");
  if (!entry) {
    return;
  }

  const title = entry.querySelector(".worldbook-title")?.value.trim();
  const heading = entry.querySelector(".worldbook-entry-title");
  if (heading) {
    heading.textContent = title || `条目 ${Number(entry.dataset.index || "0") + 1}`;
  }
}

function bindEvents() {
  elements.soulForm.addEventListener("submit", saveSoul);
  elements.worldbookForm.addEventListener("submit", saveWorldbook);
  elements.addWorldbookEntryBtn.addEventListener("click", addWorldbookEntry);
  elements.worldbookEntries.addEventListener("click", handleWorldbookListClick);
  elements.worldbookEntries.addEventListener("input", handleWorldbookInput);
  elements.saveBaseUrlBtn.addEventListener("click", saveBaseUrl);
  elements.saveModelBtn.addEventListener("click", saveModel);
  elements.clearHistoryBtn.addEventListener("click", clearHistory);
  elements.clearMemoryBtn.addEventListener("click", clearMemory);
}

bindEvents();
loadBootstrap();
