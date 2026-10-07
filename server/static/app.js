// ==============================================================================
// Game Server Installer - Frontend Application Logic (ESModules)
// ==============================================================================

const state = {
  profiles: [],
  currentProfile: null,
  serverStatus: null,
  activeJobId: null,
  eventSource: null,
  autoScroll: true,
  statusPollInterval: null,
  authToken: sessionStorage.getItem("gsi_token") || null,
  currentUser: sessionStorage.getItem("gsi_user") || null,
  authEnabled: true,
};

// DOM Elements
const el = {
  catalogSection: document.getElementById("catalog-section"),
  catalogGrid: document.getElementById("catalog-grid"),
  dashboardSection: document.getElementById("dashboard-section"),
  btnBackToCatalog: document.getElementById("btn-back-to-catalog"),
  
  selectedGameTitle: document.getElementById("selected-game-title"),
  selectedGameDesc: document.getElementById("selected-game-desc"),
  serverStatusTag: document.getElementById("server-status-tag"),
  
  metricStatus: document.getElementById("metric-status"),
  metricPid: document.getElementById("metric-pid"),
  metricPorts: document.getElementById("metric-ports"),
  
  btnInstall: document.getElementById("btn-install-server"),
  btnStart: document.getElementById("btn-start-server"),
  btnStop: document.getElementById("btn-stop-server"),
  btnRestart: document.getElementById("btn-restart-server"),
  btnSaveConfig: document.getElementById("btn-save-config"),
  
  configForm: document.getElementById("config-form"),
  formFieldsContainer: document.getElementById("form-fields-container"),
  
  terminalBody: document.getElementById("terminal-body"),
  btnToggleAutoscroll: document.getElementById("btn-toggle-autoscroll"),
  btnCopyLogs: document.getElementById("btn-copy-logs"),
  btnClearLogs: document.getElementById("btn-clear-logs"),
  apiStatusBadge: document.getElementById("api-status-badge"),

  // Auth Elements
  loginModal: document.getElementById("login-modal"),
  loginForm: document.getElementById("login-form"),
  loginUsername: document.getElementById("login-username"),
  loginPassword: document.getElementById("login-password"),
  loginErrorMsg: document.getElementById("login-error-msg"),
  userInfoArea: document.getElementById("user-info-area"),
  userBadge: document.getElementById("user-badge"),
  btnLogout: document.getElementById("btn-logout"),
};

// ------------------------------------------------------------------------------
// API Fetch Wrapper (com Injeção de Token e Interceptação 401)
// ------------------------------------------------------------------------------
async function apiFetch(url, options = {}) {
  options.headers = options.headers || {};
  if (state.authToken) {
    options.headers["Authorization"] = `Bearer ${state.authToken}`;
  }

  const res = await fetch(url, options);
  if (res.status === 401 && state.authEnabled) {
    clearAuth();
    showLoginModal("Sessão expirada ou credenciais inválidas. Por favor faça login.");
    throw new Error("Não autenticado");
  }
  return res;
}

function showLoginModal(errorMsg = "") {
  if (el.loginErrorMsg) {
    if (errorMsg) {
      el.loginErrorMsg.textContent = errorMsg;
      el.loginErrorMsg.style.display = "block";
    } else {
      el.loginErrorMsg.style.display = "none";
    }
  }
  if (el.loginModal) {
    el.loginModal.classList.add("active");
  }
}

function hideLoginModal() {
  if (el.loginModal) {
    el.loginModal.classList.remove("active");
  }
  if (el.loginErrorMsg) {
    el.loginErrorMsg.style.display = "none";
  }
}

function setAuth(token, username) {
  state.authToken = token;
  state.currentUser = username;
  sessionStorage.setItem("gsi_token", token);
  sessionStorage.setItem("gsi_user", username);

  if (el.userInfoArea && el.userBadge) {
    el.userBadge.textContent = `👤 ${username}`;
    el.userInfoArea.style.display = "flex";
  }
  hideLoginModal();
}

function clearAuth() {
  state.authToken = null;
  state.currentUser = null;
  sessionStorage.removeItem("gsi_token");
  sessionStorage.removeItem("gsi_user");

  if (el.userInfoArea) {
    el.userInfoArea.style.display = "none";
  }
}

// ------------------------------------------------------------------------------
// Initialization
// ------------------------------------------------------------------------------
async function init() {
  setupEventListeners();
  await checkHealth();
  await checkAuthAndLoad();
}

function setupEventListeners() {
  el.btnBackToCatalog.addEventListener("click", () => {
    stopStatusPolling();
    closeEventSource();
    el.dashboardSection.style.display = "none";
    el.catalogSection.style.display = "block";
    loadProfiles();
  });

  el.btnInstall.addEventListener("click", handleInstallServer);
  el.btnStart.addEventListener("click", handleStartServer);
  el.btnStop.addEventListener("click", handleStopServer);
  el.btnRestart.addEventListener("click", handleRestartServer);
  el.btnSaveConfig.addEventListener("click", handleSaveConfig);

  el.btnToggleAutoscroll.addEventListener("click", () => {
    state.autoScroll = !state.autoScroll;
    el.btnToggleAutoscroll.textContent = `Auto-scroll: ${state.autoScroll ? "ON" : "OFF"}`;
    el.btnToggleAutoscroll.classList.toggle("btn-primary", state.autoScroll);
  });

  el.btnClearLogs.addEventListener("click", () => {
    el.terminalBody.innerHTML = '<div class="log-line log-info">[SISTEMA] Console limpo.</div>';
  });

  el.btnCopyLogs.addEventListener("click", () => {
    const text = Array.from(el.terminalBody.querySelectorAll(".log-line"))
      .map(line => line.textContent)
      .join("\n");
    navigator.clipboard.writeText(text).then(() => {
      appendTerminalLog("[SISTEMA] Logs copiados para a área de transferência!", "log-success");
    });
  });

  // Auth Listeners
  if (el.loginForm) {
    el.loginForm.addEventListener("submit", handleLoginSubmit);
  }

  if (el.btnLogout) {
    el.btnLogout.addEventListener("click", () => {
      clearAuth();
      showLoginModal("Sessão encerrada.");
    });
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const username = el.loginUsername.value.trim();
  const password = el.loginPassword.value;

  if (!username || !password) return;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (!res.ok) {
      showLoginModal(data.detail || "Usuário ou senha incorretos");
      return;
    }

    setAuth(data.token, data.username);
    appendTerminalLog(`[AUTH] Conectado com sucesso como '${data.username}'.`, "log-success");
    await loadProfiles();
  } catch (err) {
    showLoginModal(`Erro de conexão: ${err.message}`);
  }
}

async function checkAuthAndLoad() {
  try {
    const res = await fetch("/api/auth/status");
    if (res.ok) {
      const data = await res.json();
      state.authEnabled = data.auth_enabled;
    }
  } catch {
    state.authEnabled = true;
  }

  if (!state.authEnabled) {
    if (el.userInfoArea) el.userInfoArea.style.display = "none";
    hideLoginModal();
    await loadProfiles();
    return;
  }

  if (state.authToken) {
    try {
      const res = await apiFetch("/api/auth/me");
      if (res.ok) {
        const user = await res.json();
        setAuth(state.authToken, user.username);
        await loadProfiles();
        return;
      }
    } catch {
      // Token inválido
    }
  }

  // Se não autenticado, abre modal
  showLoginModal();
}

// ------------------------------------------------------------------------------
// API & Data Fetching
// ------------------------------------------------------------------------------
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error();
    el.apiStatusBadge.className = "status-badge";
    el.apiStatusBadge.querySelector("span:last-child").textContent = "API Online";
  } catch {
    el.apiStatusBadge.className = "status-badge";
    el.apiStatusBadge.style.color = "var(--danger)";
    el.apiStatusBadge.querySelector("span:last-child").textContent = "API Offline";
  }
}

async function loadProfiles() {
  try {
    const res = await apiFetch("/api/profiles");
    if (!res.ok) throw new Error("Falha ao buscar perfis");
    state.profiles = await res.json();
    renderCatalog();
  } catch (err) {
    appendTerminalLog(`[ERRO] Não foi possível carregar catálogo: ${err.message}`, "log-error");
  }
}

function renderCatalog() {
  el.catalogGrid.innerHTML = "";
  state.profiles.forEach(p => {
    const card = document.createElement("div");
    card.className = "game-card";
    card.id = `card-game-${p.id}`;

    const isInstalledTag = p.is_installed 
      ? '<span class="tag installed">● Instalado</span>'
      : '<span class="tag not-installed">○ Não Instalado</span>';

    card.innerHTML = `
      <div class="game-card-header">
        <h3 class="game-card-title">${p.name}</h3>
        <span class="game-card-appid">App ID: ${p.steam_app_id}</span>
      </div>
      <div class="game-card-tags">
        ${isInstalledTag}
        <span class="tag">${p.ports_count} portas de rede</span>
        <span class="tag">${p.fields_count} configurações</span>
      </div>
      <button class="btn btn-primary btn-sm" style="width: 100%;">Gerenciar Servidor →</button>
    `;

    card.addEventListener("click", () => openDashboard(p.id));
    el.catalogGrid.appendChild(card);
  });
}

// ------------------------------------------------------------------------------
// Dashboard & Server Details
// ------------------------------------------------------------------------------
async function openDashboard(profileId) {
  el.catalogSection.style.display = "none";
  el.dashboardSection.style.display = "block";

  try {
    const [profileRes, statusRes, configRes] = await Promise.all([
      apiFetch(`/api/profiles/${profileId}`),
      apiFetch(`/api/servers/${profileId}/status`),
      apiFetch(`/api/servers/${profileId}/config`)
    ]);

    if (!profileRes.ok) throw new Error("Erro ao carregar detalhes do perfil");
    state.currentProfile = await profileRes.json();
    state.serverStatus = await statusRes.json();
    const configData = await configRes.json();

    el.selectedGameTitle.textContent = state.currentProfile.name;
    el.selectedGameDesc.textContent = `Steam App ID: ${state.currentProfile.steam_app_id} • Executável: ${state.currentProfile.executable}`;

    updateStatusUI(state.serverStatus);
    renderFormFields(state.currentProfile.fields, configData);
    startStatusPolling(profileId);

  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

function updateStatusUI(status) {
  state.serverStatus = status;

  if (status.running) {
    el.serverStatusTag.textContent = "● Em Execução";
    el.serverStatusTag.className = "tag installed";
    el.metricStatus.textContent = "Online";
    el.metricStatus.style.color = "var(--success)";
    el.metricPid.textContent = status.pid || "-";
    
    el.btnStart.disabled = true;
    el.btnStop.disabled = false;
    el.btnRestart.disabled = false;
  } else {
    el.serverStatusTag.textContent = status.is_installed ? "○ Parado" : "○ Não Instalado";
    el.serverStatusTag.className = status.is_installed ? "tag not-installed" : "tag";
    el.metricStatus.textContent = status.is_installed ? "Parado" : "Não Instalado";
    el.metricStatus.style.color = status.is_installed ? "var(--warning)" : "var(--text-dim)";
    el.metricPid.textContent = "-";

    el.btnStart.disabled = !status.is_installed;
    el.btnStop.disabled = true;
    el.btnRestart.disabled = true;
  }

  // Portas
  if (status.ports && status.ports.length > 0) {
    const mainPorts = status.ports
      .filter(p => !p.optional)
      .map(p => `${p.port}/${p.protocol}`)
      .join(", ");
    el.metricPorts.textContent = mainPorts || "-";
    el.metricPorts.title = status.ports.map(p => `${p.port}/${p.protocol} (${p.description})`).join("\n");
  } else {
    el.metricPorts.textContent = "-";
  }
}

function startStatusPolling(profileId) {
  stopStatusPolling();
  state.statusPollInterval = setInterval(async () => {
    try {
      const res = await apiFetch(`/api/servers/${profileId}/status`);
      if (res.ok) {
        const s = await res.json();
        updateStatusUI(s);
      }
    } catch {
      // Ignora falhas temporárias de polling
    }
  }, 4000);
}

function stopStatusPolling() {
  if (state.statusPollInterval) {
    clearInterval(state.statusPollInterval);
    state.statusPollInterval = null;
  }
}

// ------------------------------------------------------------------------------
// Dynamic Form Generation
// ------------------------------------------------------------------------------
function renderFormFields(fields, configData) {
  el.formFieldsContainer.innerHTML = "";

  const values = configData.defaults || {};

  fields.forEach(field => {
    const val = (values[field.key] !== undefined) ? values[field.key] : field.default;
    const group = document.createElement("div");
    group.className = "form-group";

    const label = document.createElement("label");
    label.className = "form-label";
    label.htmlFor = `field-${field.key}`;
    label.textContent = field.label;
    if (field.required) {
      label.innerHTML += ' <span style="color: var(--danger)">*</span>';
    }

    let inputEl;

    if (field.type === "boolean") {
      group.className = "form-group form-check";
      inputEl = document.createElement("input");
      inputEl.type = "checkbox";
      inputEl.className = "form-checkbox";
      inputEl.id = `field-${field.key}`;
      inputEl.name = field.key;
      inputEl.checked = Boolean(val);

      const checkLabel = document.createElement("label");
      checkLabel.htmlFor = `field-${field.key}`;
      checkLabel.textContent = field.label;
      checkLabel.style.fontSize = "0.9rem";
      checkLabel.style.cursor = "pointer";

      group.appendChild(inputEl);
      group.appendChild(checkLabel);

    } else if (field.type === "select" && field.options) {
      inputEl = document.createElement("select");
      inputEl.className = "form-control";
      inputEl.id = `field-${field.key}`;
      inputEl.name = field.key;

      field.options.forEach(opt => {
        const option = document.createElement("option");
        option.value = opt;
        option.textContent = opt;
        if (opt === String(val)) option.selected = true;
        inputEl.appendChild(option);
      });

      group.appendChild(label);
      group.appendChild(inputEl);

    } else {
      inputEl = document.createElement("input");
      inputEl.type = field.type === "integer" ? "number" : (field.type === "password" ? "password" : "text");
      inputEl.className = "form-control";
      inputEl.id = `field-${field.key}`;
      inputEl.name = field.key;
      inputEl.value = (val !== null && val !== undefined) ? val : "";

      if (field.validation) {
        if (field.validation.min !== undefined) inputEl.min = field.validation.min;
        if (field.validation.max !== undefined) inputEl.max = field.validation.max;
      }

      group.appendChild(label);
      group.appendChild(inputEl);
    }

    if (field.description) {
      const hint = document.createElement("span");
      hint.className = "form-hint";
      hint.textContent = field.description;
      group.appendChild(hint);
    }

    el.formFieldsContainer.appendChild(group);
  });
}

function collectFormData() {
  if (!state.currentProfile) return {};
  const data = {};
  state.currentProfile.fields.forEach(f => {
    const input = document.getElementById(`field-${f.key}`);
    if (!input) return;

    if (f.type === "boolean") {
      data[f.key] = input.checked;
    } else if (f.type === "integer") {
      const parsed = parseInt(input.value, 10);
      data[f.key] = isNaN(parsed) ? f.default : parsed;
    } else {
      data[f.key] = input.value;
    }
  });
  return data;
}

// ------------------------------------------------------------------------------
// Server Lifecycle Actions
// ------------------------------------------------------------------------------
async function handleInstallServer() {
  if (!state.currentProfile) return;
  const customValues = collectFormData();

  appendTerminalLog(`[INÍCIO] Disparando download/atualização do servidor de ${state.currentProfile.name}...`, "log-info");
  el.btnInstall.disabled = true;

  try {
    const res = await apiFetch("/api/jobs/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: state.currentProfile.id,
        custom_values: customValues
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Erro ao criar job de instalação");
    }

    const job = await res.json();
    state.activeJobId = job.id;
    appendTerminalLog(`[JOB #${job.id}] Fila iniciada. Conectando streaming de logs...`, "log-info");

    connectLogStream(job.id);
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
    el.btnInstall.disabled = false;
  }
}

async function handleStartServer() {
  if (!state.currentProfile) return;
  appendTerminalLog(`[AÇÃO] Iniciando servidor de ${state.currentProfile.name}...`, "log-info");

  try {
    const res = await apiFetch(`/api/servers/${state.currentProfile.id}/start`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao iniciar servidor");

    appendTerminalLog(`[SUCESSO] ${data.message} (PID: ${data.pid})`, "log-success");
    const statusRes = await apiFetch(`/api/servers/${state.currentProfile.id}/status`);
    updateStatusUI(await statusRes.json());
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

async function handleStopServer() {
  if (!state.currentProfile) return;
  appendTerminalLog(`[AÇÃO] Parando servidor de ${state.currentProfile.name}...`, "log-warn");

  try {
    const res = await apiFetch(`/api/servers/${state.currentProfile.id}/stop`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao parar servidor");

    appendTerminalLog(`[OK] ${data.message}`, "log-warn");
    const statusRes = await apiFetch(`/api/servers/${state.currentProfile.id}/status`);
    updateStatusUI(await statusRes.json());
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

async function handleRestartServer() {
  if (!state.currentProfile) return;
  appendTerminalLog(`[AÇÃO] Reiniciando servidor de ${state.currentProfile.name}...`, "log-info");

  try {
    const res = await apiFetch(`/api/servers/${state.currentProfile.id}/restart`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao reiniciar servidor");

    appendTerminalLog(`[OK] ${data.message}`, "log-success");
    const statusRes = await apiFetch(`/api/servers/${state.currentProfile.id}/status`);
    updateStatusUI(await statusRes.json());
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

async function handleSaveConfig() {
  if (!state.currentProfile) return;
  const values = collectFormData();

  try {
    const res = await apiFetch(`/api/servers/${state.currentProfile.id}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao salvar configurações");

    appendTerminalLog(`[OK] ${data.message}`, "log-success");
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

// ------------------------------------------------------------------------------
// Live Streaming SSE Console
// ------------------------------------------------------------------------------
function connectLogStream(jobId) {
  closeEventSource();

  const streamUrl = state.authToken 
    ? `/api/jobs/${jobId}/stream?token=${encodeURIComponent(state.authToken)}`
    : `/api/jobs/${jobId}/stream`;

  const es = new EventSource(streamUrl);
  state.eventSource = es;

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      appendTerminalLog(data.text);
    } catch {
      appendTerminalLog(event.data);
    }
  };

  es.addEventListener("done", (event) => {
    appendTerminalLog("[CONCLUÍDO] Processo finalizado com sucesso!", "log-success");
    closeEventSource();
    el.btnInstall.disabled = false;
    if (state.currentProfile) {
      apiFetch(`/api/servers/${state.currentProfile.id}/status`)
        .then(r => r.json())
        .then(s => updateStatusUI(s));
    }
  });

  es.onerror = () => {
    appendTerminalLog("[STREAM] Conexão com o console encerrada.", "log-dim");
    closeEventSource();
    el.btnInstall.disabled = false;
  };
}

function closeEventSource() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
}

// ------------------------------------------------------------------------------
// Terminal Log Utilities
// ------------------------------------------------------------------------------
function appendTerminalLog(text, customClass = "") {
  if (!text) return;

  const line = document.createElement("div");
  line.className = "log-line";

  // Detecção de cores automática se não especificado
  if (customClass) {
    line.classList.add(customClass);
  } else if (text.includes("Success") || text.includes("OK") || text.includes("Fully Installed")) {
    line.classList.add("log-success");
  } else if (text.includes("Error") || text.includes("Failed") || text.includes("FAILED")) {
    line.classList.add("log-error");
  } else if (text.includes("Update state") || text.includes("downloading")) {
    line.classList.add("log-info");
  }

  line.textContent = text;
  el.terminalBody.appendChild(line);

  // Limite de buffer a 1000 linhas
  while (el.terminalBody.childNodes.length > 1000) {
    el.terminalBody.removeChild(el.terminalBody.firstChild);
  }

  if (state.autoScroll) {
    el.terminalBody.scrollTop = el.terminalBody.scrollHeight;
  }
}

// Start
document.addEventListener("DOMContentLoaded", init);
