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
};

// ------------------------------------------------------------------------------
// Initialization
// ------------------------------------------------------------------------------
async function init() {
  setupEventListeners();
  await checkHealth();
  await loadProfiles();
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
    const res = await fetch("/api/profiles");
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
      fetch(`/api/profiles/${profileId}`),
      fetch(`/api/servers/${profileId}/status`),
      fetch(`/api/servers/${profileId}/config`)
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
  const portsText = status.ports ? status.ports.map(p => `${p.port}/${p.protocol}`).join(", ") : "-";
  el.metricPorts.textContent = portsText;
}

function startStatusPolling(profileId) {
  stopStatusPolling();
  state.statusPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/servers/${profileId}/status`);
      if (res.ok) {
        const s = await res.json();
        updateStatusUI(s);
      }
    } catch {
      // Ignorar falhas pontuais de polling
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
// Dynamic Config Form Generation
// ------------------------------------------------------------------------------
function renderFormFields(fields, configData) {
  el.formFieldsContainer.innerHTML = "";
  const values = configData.values || configData.defaults || {};

  fields.forEach(f => {
    const group = document.createElement("div");
    group.className = "form-group";
    group.id = `group-${f.key}`;

    const currentVal = values[f.key] !== undefined ? values[f.key] : f.default;

    if (f.type === "boolean") {
      group.className = "form-group switch-wrapper";
      group.innerHTML = `
        <div>
          <label class="form-label" for="field-${f.key}">${f.label}</label>
          <div class="form-desc">${f.description || ""}</div>
        </div>
        <label class="switch">
          <input type="checkbox" id="field-${f.key}" name="${f.key}" ${currentVal ? "checked" : ""}>
          <span class="slider"></span>
        </label>
      `;
    } else if (f.type === "select") {
      const optionsHtml = (f.options || [])
        .map(opt => `<option value="${opt.value}" ${String(opt.value) === String(currentVal) ? "selected" : ""}>${opt.label}</option>`)
        .join("");

      group.innerHTML = `
        <label class="form-label" for="field-${f.key}">
          <span>${f.label}</span>
          ${f.required ? '<span style="color: var(--danger)">*</span>' : ''}
        </label>
        <select class="form-select" id="field-${f.key}" name="${f.key}">
          ${optionsHtml}
        </select>
        <div class="form-desc">${f.description || ""}</div>
      `;
    } else {
      const inputType = f.type === "password" ? "password" : (f.type === "integer" ? "number" : "text");
      const minAttr = f.min !== null && f.min !== undefined ? `min="${f.min}"` : "";
      const maxAttr = f.max !== null && f.max !== undefined ? `max="${f.max}"` : "";

      group.innerHTML = `
        <label class="form-label" for="field-${f.key}">
          <span>${f.label}</span>
          ${f.required ? '<span style="color: var(--danger)">*</span>' : ''}
        </label>
        <input 
          class="form-input" 
          type="${inputType}" 
          id="field-${f.key}" 
          name="${f.key}" 
          value="${currentVal !== null && currentVal !== undefined ? currentVal : ""}"
          ${minAttr} ${maxAttr}
        >
        <div class="form-desc">${f.description || ""}</div>
      `;
    }

    el.formFieldsContainer.appendChild(group);
  });
}

function collectFormData() {
  const data = {};
  if (!state.currentProfile) return data;

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
    const res = await fetch("/api/jobs/install", {
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
    const res = await fetch(`/api/servers/${state.currentProfile.id}/start`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao iniciar servidor");

    appendTerminalLog(`[SUCESSO] ${data.message} (PID: ${data.pid})`, "log-success");
    const statusRes = await fetch(`/api/servers/${state.currentProfile.id}/status`);
    updateStatusUI(await statusRes.json());
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

async function handleStopServer() {
  if (!state.currentProfile) return;
  appendTerminalLog(`[AÇÃO] Parando servidor de ${state.currentProfile.name}...`, "log-warn");

  try {
    const res = await fetch(`/api/servers/${state.currentProfile.id}/stop`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao parar servidor");

    appendTerminalLog(`[OK] ${data.message}`, "log-warn");
    const statusRes = await fetch(`/api/servers/${state.currentProfile.id}/status`);
    updateStatusUI(await statusRes.json());
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

async function handleRestartServer() {
  if (!state.currentProfile) return;
  appendTerminalLog(`[AÇÃO] Reiniciando servidor de ${state.currentProfile.name}...`, "log-info");

  try {
    const res = await fetch(`/api/servers/${state.currentProfile.id}/restart`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao reiniciar servidor");

    appendTerminalLog(`[OK] ${data.message}`, "log-success");
    const statusRes = await fetch(`/api/servers/${state.currentProfile.id}/status`);
    updateStatusUI(await statusRes.json());
  } catch (err) {
    appendTerminalLog(`[ERRO] ${err.message}`, "log-error");
  }
}

async function handleSaveConfig() {
  if (!state.currentProfile) return;
  const values = collectFormData();

  try {
    const res = await fetch(`/api/servers/${state.currentProfile.id}/config`, {
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

  const es = new EventSource(`/api/jobs/${jobId}/stream`);
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
      fetch(`/api/servers/${state.currentProfile.id}/status`)
        .then(r => r.json())
        .then(s => updateStatusUI(s));
    }
  });

  es.onerror = () => {
    // Conexão encerrada pelo servidor após término
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

function appendTerminalLog(text, customClass = "") {
  if (!text) return;

  const line = document.createElement("div");
  line.className = `log-line ${customClass}`;

  // Destaque visual automático baseado no conteúdo
  if (!customClass) {
    if (text.includes("[OK]") || text.includes("OK") || text.includes("Success")) {
      line.classList.add("log-success");
    } else if (text.includes("[ERRO]") || text.includes("ERROR") || text.includes("Falha")) {
      line.classList.add("log-error");
    } else if (text.includes("==>") || text.includes("[INFO]")) {
      line.classList.add("log-info");
    } else if (text.includes("[AVISO]") || text.includes("warn")) {
      line.classList.add("log-warn");
    }
  }

  const timeStr = new Date().toLocaleTimeString();
  line.textContent = `[${timeStr}] ${text}`;

  el.terminalBody.appendChild(line);

  if (state.autoScroll) {
    el.terminalBody.scrollTop = el.terminalBody.scrollHeight;
  }
}

// Iniciar a aplicação
document.addEventListener("DOMContentLoaded", init);
