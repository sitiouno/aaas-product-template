import { initAuth, onAuthChange, getActiveToken, logout, openAuthModal } from "./js/auth.js";
import { setupFetch, fetchJson, el, els, t, escapeHtml, showToast, dismissToast } from "./js/utils.js";
import { subscribeRunEvents, startNewRun, fetchHistory, fetchAccount, resumeRun } from "./js/runner.js";
import { styleLabel } from "./js/utils.js";

let currentScreen = "workspace-dashboard";
let _selectedStyle = "deploy_product";
let _capabilities = null;

/* ── Active tasks queue (tracks all running/queued reports) ────────── */
const _activeTasks = new Map(); // jobId → { style, prompt, status, progress, toast, eventSource }

function _getCapLabel(styleKey) {
  const cap = _capabilities?.find((s) => s.key === styleKey);
  return cap?.name || styleLabel(styleKey);
}

function _renderTaskQueue() {
  const panel = el("#active-tasks-panel");
  if (!panel) return;
  if (_activeTasks.size === 0) {
    panel.innerHTML = "";
    return;
  }
  panel.innerHTML = Array.from(_activeTasks.entries())
    .map(([jobId, task]) => {
      const isRunning = task.status === "running" || task.status === "queued";
      const isCompleted = task.status === "completed";
      const isFailed = task.status === "failed";
      const statusClass = isRunning ? "is-running" : isCompleted ? "is-completed" : isFailed ? "is-failed" : "";
      const icon = isRunning
        ? `<span class="tq-spinner"></span>`
        : isCompleted
          ? `<span class="tq-icon" style="color:var(--accent-green);">&#10003;</span>`
          : `<span class="tq-icon" style="color:var(--accent-red);">&#10007;</span>`;
      const progress = isRunning
        ? `<span class="tq-progress"><span class="tq-progress-bar" style="width:${task.progress || 0}%"></span></span>`
        : "";
      const link = isCompleted
        ? `<a class="tq-link" href="javascript:void(0)" onclick="window.viewRun('${jobId}')">${t("View Deployment", "Ver Despliegue")}</a>`
        : "";
      const prompt = escapeHtml((task.prompt || "").substring(0, 45));
      return `<div class="task-queue-item ${statusClass}">
        ${icon}
        <span class="tq-label"><strong>${escapeHtml(_getCapLabel(task.style))}</strong> &mdash; ${prompt}</span>
        ${progress}${link}
      </div>`;
    })
    .join("");
}

function _monitorTask(jobId, task) {
  const es = new EventSource(`/api/v1/runs/${encodeURIComponent(jobId)}/stream`);
  task.eventSource = es;
  es.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      const snapshot = payload?.snapshot || payload;
      task.status = snapshot.status || task.status;
      task.progress = snapshot.progress_percent || 0;
      _renderTaskQueue();
      if (["completed", "failed"].includes(snapshot.status)) {
        es.close();
        task.eventSource = null;
        if (snapshot.status === "completed") {
          if (task.toast) dismissToast(task.toast);
          showToast(
            `<span style="color:var(--accent-green)">&#10003;</span> <strong>${escapeHtml(_getCapLabel(task.style))}</strong> ${t("deployed!", "desplegado!")} <a href="javascript:void(0)" onclick="window.viewRun('${jobId}')">${t("View Deployment", "Ver Despliegue")}</a>`,
            { tone: "success", duration: 10000, html: true }
          );
          // Refresh dashboard/account to show updated credits
          _refreshAccountIfVisible();
        } else {
          if (task.toast) dismissToast(task.toast);
          showToast(
            `<span style="color:var(--accent-red)">&#10007;</span> <strong>${escapeHtml(_getCapLabel(task.style))}</strong> ${t("failed.", "fallo.")}`,
            { tone: "error", duration: 8000, html: true }
          );
        }
        // Auto-remove completed/failed tasks after a delay
        setTimeout(() => {
          _activeTasks.delete(jobId);
          _renderTaskQueue();
        }, 30000);
      }
    } catch (e) {
      console.error("Task monitor SSE parse error:", e);
    }
  };
  es.onerror = () => {
    es.close();
    task.eventSource = null;
    // SSE died — poll the run status, retry if still running
    setTimeout(async () => {
      try {
        const res = await setupFetch(`/api/v1/runs/${encodeURIComponent(jobId)}`);
        if (res.ok) {
          const snapshot = await res.json();
          task.status = snapshot.status || task.status;
          task.progress = snapshot.progress_percent || 0;
          _renderTaskQueue();
          if (["completed", "failed"].includes(snapshot.status)) {
            if (task.toast) dismissToast(task.toast);
            if (snapshot.status === "completed") {
              showToast(
                `<span style="color:var(--accent-green)">&#10003;</span> <strong>${escapeHtml(_getCapLabel(task.style))}</strong> ${t("deployed!", "desplegado!")} <a href="javascript:void(0)" onclick="window.viewRun('${jobId}')">${t("View Deployment", "Ver Despliegue")}</a>`,
                { tone: "success", duration: 10000, html: true }
              );
            } else {
              showToast(
                `<span style="color:var(--accent-red)">&#10007;</span> <strong>${escapeHtml(_getCapLabel(task.style))}</strong> ${t("failed.", "fallo.")}`,
                { tone: "error", duration: 8000, html: true }
              );
            }
            _refreshAccountIfVisible();
            setTimeout(() => { _activeTasks.delete(jobId); _renderTaskQueue(); }, 15000);
          } else {
            // Still running — reconnect SSE
            _monitorTask(jobId, task);
          }
        } else {
          // Run not found — dismiss toast
          if (task.toast) dismissToast(task.toast);
          _activeTasks.delete(jobId);
          _renderTaskQueue();
        }
      } catch {
        // Network error — try reconnecting after longer delay
        setTimeout(() => _monitorTask(jobId, task), 5000);
      }
    }, 2000);
  };
}

function _refreshAccountIfVisible() {
  // Dispatch a custom event that the boot function listens to for refreshing
  window.dispatchEvent(new CustomEvent("refresh-account"));
}

/* ── Custom Modal (replaces alert/confirm/prompt) ─────────────────── */
function showModal(message, type = "alert", defaultValue = "") {
  return new Promise((resolve) => {
    const existing = document.getElementById("app-modal-overlay");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "app-modal-overlay";
    overlay.className = "modal-overlay";

    const isPrompt = type === "prompt";
    const isConfirm = type === "confirm";

    overlay.innerHTML = `
      <div class="modal-card">
        <p class="modal-message">${escapeHtml(message)}</p>
        ${isPrompt ? `<input type="text" class="modal-input" value="${escapeHtml(defaultValue)}" />` : ""}
        <div class="modal-actions">
          ${isConfirm || isPrompt ? `<button class="modal-btn modal-btn-cancel">${t("Cancel", "Cancelar")}</button>` : ""}
          <button class="modal-btn modal-btn-ok">${t("OK", "Aceptar")}</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add("is-active"));

    const input = overlay.querySelector(".modal-input");
    const btnOk = overlay.querySelector(".modal-btn-ok");
    const btnCancel = overlay.querySelector(".modal-btn-cancel");

    function close(value) {
      overlay.classList.remove("is-active");
      setTimeout(() => overlay.remove(), 200);
      resolve(value);
    }

    btnOk.addEventListener("click", () => {
      if (isPrompt) close(input?.value || "");
      else if (isConfirm) close(true);
      else close(undefined);
    });

    if (btnCancel) btnCancel.addEventListener("click", () => close(isPrompt ? null : false));

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close(isPrompt ? null : isConfirm ? false : undefined);
    });

    if (input) {
      input.focus();
      input.select();
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") btnOk.click(); });
    } else {
      btnOk.focus();
    }
  });
}

/* ── Pipeline definitions for How It Works ───────────────────────── */
const PIPELINE_INFO = {
  deploy_product: {
    agents: [
      { name: "Product Planner", model: "pro", icon: "doc" },
      { name: "Infrastructure Provisioner", model: "flash", icon: "search" },
      { name: "Code Generator", model: "pro", icon: "chart" },
      { name: "Billing Configurator", model: "flash", icon: "chart" },
      { name: "Landing Page Builder", model: "pro", icon: "format" },
      { name: "Deployment Manager", model: "flash", icon: "search" },
      { name: "MCP Server Setup", model: "flash", icon: "format" },
    ],
    pattern: "Sequential",
  },
  market_intelligence: {
    agents: [
      { name: "Market Trends", model: "flash", icon: "search", parallel: true },
      { name: "Competitor Scanner", model: "flash", icon: "search", parallel: true },
      { name: "Industry Analyst", model: "flash", icon: "search", parallel: true },
      { name: "Market Synthesizer", model: "pro", icon: "brain" },
      { name: "Report Formatter", model: "flash", icon: "format" },
      { name: "Chart Generator", model: "flash", icon: "chart" },
    ],
    pattern: "Parallel → Sequential",
  },
  world_news_briefing: {
    agents: [
      { name: "Global News Scanner", model: "flash", icon: "search", parallel: true },
      { name: "Market Movers", model: "flash", icon: "chart", parallel: true },
      { name: "Geopolitical Monitor", model: "flash", icon: "search", parallel: true },
      { name: "Earnings Tracker", model: "flash", icon: "chart", parallel: true },
      { name: "Briefing Synthesizer", model: "flash", icon: "brain" },
      { name: "Report Formatter", model: "flash", icon: "format" },
    ],
    pattern: "Parallel → Sequential",
  },
  company_deep_dive: {
    agents: [
      { name: "Company Profiler", model: "flash", icon: "search", parallel: true },
      { name: "Financial Analyst", model: "flash", icon: "chart", parallel: true },
      { name: "News Aggregator", model: "flash", icon: "search", parallel: true },
      { name: "Competitor Mapper", model: "flash", icon: "search", parallel: true },
      { name: "Company Analyst", model: "pro", icon: "brain" },
      { name: "Report Formatter", model: "flash", icon: "format" },
      { name: "Chart Generator", model: "flash", icon: "chart" },
    ],
    pattern: "Parallel → Sequential",
  },
  industry_analysis: {
    agents: [
      { name: "Sector Overview", model: "flash", icon: "search", parallel: true },
      { name: "Key Players Scanner", model: "flash", icon: "search", parallel: true },
      { name: "Regulatory Tracker", model: "flash", icon: "search", parallel: true },
      { name: "Trend Forecaster", model: "flash", icon: "chart", parallel: true },
      { name: "Industry Synthesizer", model: "pro", icon: "brain" },
      { name: "Report Formatter", model: "flash", icon: "format" },
      { name: "Chart Generator", model: "flash", icon: "chart" },
    ],
    pattern: "Parallel → Sequential",
  },
  osint_360: {
    agents: [
      { name: "Identity Resolver", model: "flash", icon: "search", parallel: true },
      { name: "Social Media Hunter", model: "flash", icon: "search", parallel: true },
      { name: "Corporate Registry", model: "flash", icon: "search", parallel: true },
      { name: "Public Records", model: "flash", icon: "search", parallel: true },
      { name: "News Media Scanner", model: "flash", icon: "search", parallel: true },
      { name: "Image Intel", model: "flash", icon: "search", parallel: true },
      { name: "Lead Investigator", model: "pro", icon: "brain", loop: true },
      { name: "Red Flag Hunter", model: "pro", icon: "alert", loop: true },
      { name: "Connection Mapper", model: "pro", icon: "brain" },
      { name: "Risk Profiler", model: "pro", icon: "alert" },
      { name: "Graph Visualizer", model: "pro", icon: "chart" },
      { name: "Report Formatter", model: "flash", icon: "format" },
      { name: "Chart Generator", model: "flash", icon: "chart" },
    ],
    pattern: "Parallel → Loop → Sequential",
  },
};

function boot() {
  initAuth();

  const DOM = {
    workspaceShell: el(".workspace-shell"),
    navLinks: els(".workspace-nav a[data-view]"),
    sections: els(".workspace-section"),
    targetUrlInput: el("#app-prompt-input"),
    statusPill: el("#app-status-pill"),
    progressFill: el("#app-progress-fill"),
    stageTitle: el("#app-current-stage-title"),
    stageDescription: el("#app-current-stage-description"),
    stageList: el("#app-stage-list"),
    summaryCard: el("#app-summary-card"),
    resultsStack: el("#app-results-stack"),
    artifactGrid: el("#app-artifact-grid"),
    logFeed: el("#app-log-feed"),
    disableButtons: els("button[type='submit']"),
  };

  if (!DOM.workspaceShell) {
    bootLanding();
    return;
  }

  onAuthChange(async (user) => {
    if (user) {
      const account = await fetchAccount();
      if (account && account.is_admin) {
        const navAdmin = document.getElementById("nav-admin");
        if (navAdmin) navAdmin.style.display = "flex";
      }
      // Onboarding modal for new users
      if (account && account.onboarding_completed === false) {
        const modal = document.getElementById("onboarding-modal");
        if (modal) {
          modal.classList.add("is-active");
          const lang = document.documentElement.lang || "en";
          const msg = lang === "es"
            ? "Tienes " + (account.credits || 0) + " creditos gratis para explorar."
            : "You have " + (account.credits || 0) + " free credits to explore.";
          const creditsMsg = document.getElementById("onboarding-credits-msg");
          if (creditsMsg) creditsMsg.textContent = msg;
          const dismissBtn = document.getElementById("btn-dismiss-onboarding");
          if (dismissBtn) {
            dismissBtn.onclick = async () => {
              await setupFetch("/api/v1/account", { method: "PATCH", body: JSON.stringify({ onboarding_completed: true }) });
              modal.classList.remove("is-active");
            };
          }
        }
      }
    }
  });

  subscribeRunEvents(DOM);

  const logoutBtn = document.getElementById("workspace-logout-button");
  if (logoutBtn) logoutBtn.addEventListener("click", () => logout());

  loadCapabilities();

  /* ── Tab switching ─────────────────────────────────────────────── */
  function switchTab(hashNav) {
    if (!hashNav) hashNav = "dashboard";
    const targetSectionId = "workspace-" + hashNav;

    DOM.navLinks.forEach((link) => {
      link.classList.toggle("is-active", link.getAttribute("href") === "#" + hashNav);
    });
    DOM.sections.forEach((section) => {
      section.classList.toggle("is-active", section.id === targetSectionId);
    });

    currentScreen = targetSectionId;
    window.location.hash = hashNav;

    const loaders = {
      dashboard: loadDashboard,
      history: loadHistory,
      api: loadApiArea,
      account: loadAccountArea,
      billing: loadBillingArea,
      admin: loadAdminArea,
      "how-it-works": loadHowItWorks,
    };
    if (loaders[hashNav]) loaders[hashNav]();
  }

  DOM.navLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      switchTab(link.getAttribute("href").replace("#", ""));
    });
  });

  const initialHash = window.location.hash.replace("#", "") || "dashboard";
  switchTab(initialHash);

  // Listen for hash changes (e.g. "View all reports" link)
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "");
    if (hash && hash !== currentScreen.replace("workspace-", "")) {
      switchTab(hash);
    }
  });

  document.addEventListener("click", (e) => {
    const navBtn = e.target.closest("[data-navigate]");
    if (navBtn) {
      e.preventDefault();
      switchTab(navBtn.getAttribute("data-navigate").replace("workspace-", ""));
    }
  });

  // Listen for account refresh requests from the task queue
  window.addEventListener("refresh-account", () => {
    if (currentScreen === "workspace-dashboard") loadDashboard();
    if (currentScreen === "workspace-account") loadAccountArea();
  });

  /* ── Mobile hamburger menu ─────────────────────────────────────── */
  const hamburgerBtn = el("#hamburger-toggle");
  const sidebar = el(".workspace-sidebar");
  if (hamburgerBtn && sidebar) {
    hamburgerBtn.addEventListener("click", () => {
      sidebar.classList.toggle("is-open");
      hamburgerBtn.classList.toggle("is-active");
    });
    // Close sidebar when a nav link is clicked (mobile)
    sidebar.querySelectorAll("a[data-view]").forEach((link) => {
      link.addEventListener("click", () => {
        sidebar.classList.remove("is-open");
        hamburgerBtn.classList.remove("is-active");
      });
    });
  }

  /* ── Style card selection ──────────────────────────────────────── */
  document.addEventListener("click", (e) => {
    const card = e.target.closest(".style-card[data-style]");
    if (!card) return;
    selectStyle(card.getAttribute("data-style"));
  });

  /* ── Run submission ────────────────────────────────────────────── */
  const submitBtn = el("#app-run-submit");
  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      if (!_selectedStyle) {
        _selectedStyle = "deploy_product";
      }
      const prompt = DOM.targetUrlInput?.value || "";
      if (!prompt) {
        showModal(t("Describe the product you want to deploy.", "Describe el producto que quieres desplegar."), "alert");
        return;
      }
      const lang = el("#app-language-select")?.value || "en";
      const styleName = _getCapLabel(_selectedStyle);
      submitBtn.disabled = true;
      try {
        const newRun = await startNewRun({ prompt, research_style: _selectedStyle, language: lang });
        if (newRun) {
          DOM.targetUrlInput.value = "";
          // Show the status area
          const statusArea = el("#app-run-status-area");
          if (statusArea) statusArea.style.display = "block";
          // Toast: report generation started
          const inProgressToast = showToast(
            `<span class="toast-spinner"></span> <strong>${escapeHtml(styleName)}</strong> &mdash; ${t("Deploying product...", "Desplegando producto...")}`,
            { tone: "info", persist: true, html: true }
          );
          // Track in active tasks queue
          const task = { style: _selectedStyle, prompt, status: "queued", progress: 0, toast: inProgressToast };
          _activeTasks.set(newRun.job_id, task);
          _renderTaskQueue();
          _monitorTask(newRun.job_id, task);
        }
      } catch (err) {
        const fb = el("#app-run-feedback");
        if (fb) {
          fb.hidden = false;
          fb.textContent = err.message;
          fb.setAttribute("data-tone", "error");
        }
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  /* ── Load capabilities ─────────────────────────────────────────── */
  async function loadCapabilities() {
    const grid = el("#research-style-grid");
    if (!grid) return;
    try {
      const res = await setupFetch("/api/v1/research/capabilities");
      if (!res.ok) return;
      const data = await res.json();
      _capabilities = data.styles || [];
      grid.innerHTML = _capabilities
        .map(
          (s) => `
        <div class="style-card" data-style="${s.key}">
          <div class="style-name">${s.name}</div>
          <div class="style-desc">${s.description || ""}</div>
          <div class="style-meta">
            <span>${s.agent_count || "?"} agents</span>
            <span>${s.credit_cost || "?"} credits</span>
            <span>${s.estimated_duration_minutes ? s.estimated_duration_minutes[0] + "-" + s.estimated_duration_minutes[1] + " min" : ""}</span>
          </div>
        </div>`
        )
        .join("");
    } catch (e) {
      /* empty */
    }
  }

  function selectStyle(styleKey) {
    _selectedStyle = styleKey;
    els(".style-card[data-style]").forEach((c) =>
      c.classList.toggle("is-selected", c.getAttribute("data-style") === styleKey)
    );
    const formArea = el("#research-form-area");
    const label = el("#selected-style-label");
    const costNote = el("#credit-cost-note");
    if (formArea) formArea.style.display = "block";
    const cap = _capabilities?.find((s) => s.key === styleKey);
    if (label) label.textContent = cap?.name || styleLabel(styleKey);
    if (costNote && cap) {
      costNote.textContent = t(
        `This will consume ${cap.credit_cost} credit(s). Estimated: ${cap.estimated_duration_minutes[0]}-${cap.estimated_duration_minutes[1]} min.`,
        `Esto consumira ${cap.credit_cost} credito(s). Estimado: ${cap.estimated_duration_minutes[0]}-${cap.estimated_duration_minutes[1]} min.`
      );
    }
  }

  /* ── Products Dashboard ──────────────────────────────────────────── */
  async function loadProducts() {
    try {
      const resp = await setupFetch('/api/v1/products');
      if (!resp.ok) return;
      const products = await resp.json();
      renderProductsDashboard(products);
    } catch (e) {
      console.warn('Failed to load products:', e);
    }
  }

  function renderProductsDashboard(products) {
    const container = el('#products-dashboard');
    if (!container) return;

    if (!products.length) {
      container.innerHTML = `<p class="muted-copy">${t("No products deployed yet. Deploy your first MVP above!", "Sin productos desplegados. Despliega tu primer MVP arriba!")}</p>`;
      return;
    }

    container.innerHTML = products.map(p => {
      const statusColors = {created: '#94A3B8', provisioning: '#EAB308', running: '#10B981', error: '#EF4444', completed: '#10B981'};
      const statusColor = statusColors[p.status] || '#94A3B8';
      return `
        <div class="product-card">
          <div class="product-header">
            <h3>${escapeHtml(p.product_name)}</h3>
            <span class="status-badge" style="background:${statusColor}">${p.status}</span>
          </div>
          <p class="product-domain">${escapeHtml(p.custom_domain || p.product_slug)}</p>
          <div class="product-actions">
            ${p.repo_url ? `<a href="${escapeHtml(p.repo_url)}" target="_blank" class="btn-small">${t("Repo", "Repo")}</a>` : ''}
            ${p.cloud_run_url ? `<a href="${escapeHtml(p.cloud_run_url)}" target="_blank" class="btn-small">${t("View Site", "Ver Sitio")}</a>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  /* ── Dashboard ─────────────────────────────────────────────────── */
  async function loadDashboard() {
    const wsStats = el("#workspace-stats");
    const dashRecent = el("#dashboard-recent");
    const dashLaunch = el("#dashboard-quick-launch");
    if (!wsStats) return;

    const account = await fetchAccount();
    if (account) {
      const emailName = account.email ? account.email.split("@")[0] : "User";
      const dashWelcome = el("#dashboard-welcome");
      if (dashWelcome)
        dashWelcome.textContent = `${t("Welcome back", "Bienvenido")}, ${emailName}`;

      const failedHtml = account.failed_runs
        ? `<div class="stat-card stat-red"><span class="stat-value">${account.failed_runs}</span><p class="stat-label">${t("Failed", "Fallidos")}</p></div>`
        : "";
      wsStats.innerHTML = `
        <div class="stat-card stat-cyan">
          <span class="stat-value">${account.credits || 0}</span>
          <p class="stat-label">${t("Credits Balance", "Saldo de Creditos")}</p>
        </div>
        <div class="stat-card stat-purple">
          <span class="stat-value">${account.total_runs || 0}</span>
          <p class="stat-label">${t("Deployments", "Despliegues")}</p>
        </div>
        <div class="stat-card stat-green">
          <span class="stat-value">${account.daily_runs || 0}</span>
          <p class="stat-label">${t("Today (24h)", "Hoy (24h)")}</p>
        </div>
        ${failedHtml}
        <div class="stat-card stat-amber">
          <span class="stat-value">${account.api_keys?.length || 0}</span>
          <p class="stat-label">${t("API Keys", "API Keys")}</p>
        </div>
      `;
    }

    const hist = await fetchHistory();
    if (hist?.runs?.length > 0 && dashRecent) {
      dashRecent.innerHTML = hist.runs
        .slice(0, 5)
        .map(
          (r) => `
        <div class="recent-item" onclick="window.viewRun('${r.job_id}')">
          <div class="recent-item-left">
            <span class="pill pill-sm ${r.status === "completed" ? "pill-green" : r.status === "failed" ? "pill-red" : "pill-blue"}">${r.status}</span>
            <span class="recent-item-style">${styleLabel(r.research_style || "deploy_product")}</span>
          </div>
          <span class="recent-item-prompt">${escapeHtml((r.prompt || "").substring(0, 60))}</span>
        </div>`
        )
        .join("");
    } else if (dashRecent) {
      dashRecent.innerHTML = `<p class="muted-copy">${t("No deployments yet. Deploy your first product!", "Sin despliegues. Despliega tu primer producto!")}</p>`;
    }

    if (dashLaunch) {
      const styles = _capabilities || [];
      if (styles.length === 0) {
        // Fallback if capabilities not loaded yet
        try {
          const res = await setupFetch("/api/v1/research/capabilities");
          if (res.ok) {
            const data = await res.json();
            _capabilities = data.styles || [];
          }
        } catch (e) {
          /* empty */
        }
      }
      const items = (_capabilities || []).map(
        (s) => `
        <button class="quick-launch-card" data-style-key="${s.key}">
          <strong>${s.name}</strong>
          <span class="ql-meta">${s.agent_count} agents &middot; ${s.credit_cost} cr &middot; ${s.estimated_duration_minutes[0]}-${s.estimated_duration_minutes[1]}m</span>
        </button>`
      );
      dashLaunch.innerHTML = items.join("");
      dashLaunch.querySelectorAll(".quick-launch-card").forEach((card) => {
        card.addEventListener("click", () => {
          const styleKey = card.getAttribute("data-style-key");
          _selectedStyle = styleKey;
          switchTab("research");
          // Pre-select the style card after view renders
          setTimeout(() => {
            const styleCards = document.querySelectorAll(".style-card");
            styleCards.forEach((sc) => {
              if (sc.getAttribute("data-style") === styleKey) {
                sc.click();
              }
            });
          }, 100);
        });
      });
    }

    // Load deployed products
    loadProducts();
  }

  /* ── How It Works ──────────────────────────────────────────────── */
  function loadHowItWorks() {
    const container = el("#pipeline-cards");
    if (!container) return;

    const cards = Object.entries(PIPELINE_INFO).map(([key, info]) => {
      const agentList = info.agents
        .map((a) => {
          const badges = [];
          if (a.parallel) badges.push('<span class="agent-badge parallel">parallel</span>');
          if (a.loop) badges.push('<span class="agent-badge loop">loop</span>');
          badges.push(`<span class="agent-badge model-${a.model}">${a.model}</span>`);
          return `<div class="agent-row"><span class="agent-name">${a.name}</span><span class="agent-badges">${badges.join("")}</span></div>`;
        })
        .join("");

      return `
        <div class="pipeline-card">
          <div class="pipeline-header">
            <h3>${styleLabel(key)}</h3>
            <span class="pipeline-pattern">${info.pattern}</span>
          </div>
          <div class="pipeline-meta">${info.agents.length} agents</div>
          <div class="agent-list">${agentList}</div>
        </div>`;
    });

    container.innerHTML = cards.join("");
  }

  /* ── Admin Panel ───────────────────────────────────────────────── */
  async function loadAdminArea() {
    // Set up sub-tab switching
    const tabs = document.querySelectorAll(".admin-tab");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("is-active"));
        tab.classList.add("is-active");
        const target = tab.getAttribute("data-admin-tab");
        document.querySelectorAll(".admin-tab-content").forEach((c) => {
          c.style.display = "none";
          c.classList.remove("is-active");
        });
        const targetEl = document.getElementById("admin-tab-" + target);
        if (targetEl) {
          targetEl.style.display = "block";
          targetEl.classList.add("is-active");
        }
      });
    });

    loadAdminRequests();
    loadAdminUsers();
    loadAdminUsage();
    loadAdminRevenue();
  }

  async function loadAdminRequests() {
    const area = el("#admin-tab-requests");
    if (!area) return;
    area.innerHTML = `<p class="muted-copy">${t("Loading access requests...", "Cargando solicitudes...")}</p>`;

    try {
      const res = await setupFetch("/api/v1/admin/access-requests?status=pending");
      if (!res.ok) {
        area.innerHTML = `<p style="color:var(--accent-red);">${t("Access denied.", "Acceso denegado.")}</p>`;
        return;
      }
      const data = await res.json();
      const requests = data.requests || [];

      if (requests.length === 0) {
        area.innerHTML = `<div class="empty-state"><p>${t("No pending access requests.", "Sin solicitudes pendientes.")}</p></div>`;
        return;
      }

      area.innerHTML = `
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead><tr>
              <th>${t("Email", "Email")}</th>
              <th>${t("Name", "Nombre")}</th>
              <th>${t("Company", "Empresa")}</th>
              <th>${t("Message", "Mensaje")}</th>
              <th>${t("Date", "Fecha")}</th>
              <th>${t("Actions", "Acciones")}</th>
            </tr></thead>
            <tbody>
              ${requests
                .map(
                  (r) => `
                <tr>
                  <td class="mono-cell">${escapeHtml(r.email)}</td>
                  <td>${escapeHtml(r.full_name || "-")}</td>
                  <td>${escapeHtml(r.company || "-")}</td>
                  <td class="msg-cell" title="${escapeHtml(r.message || "")}">${escapeHtml((r.message || "").substring(0, 50))}</td>
                  <td>${r.created_at ? new Date(r.created_at).toLocaleDateString() : "-"}</td>
                  <td class="action-cell">
                    <button class="btn-approve" data-id="${r.id}">${t("Approve", "Aprobar")}</button>
                    <button class="btn-reject" data-id="${r.id}">${t("Reject", "Rechazar")}</button>
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`;

      area.querySelectorAll(".btn-approve").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.getAttribute("data-id");
          const credits = await showModal(t("Initial credits to grant:", "Creditos iniciales a otorgar:"), "prompt", "10");
          if (!credits) return;
          btn.disabled = true;
          try {
            const r = await setupFetch(`/api/v1/admin/access-requests/${id}/approve`, {
              method: "POST",
              body: JSON.stringify({ initial_credits: parseInt(credits, 10) }),
            });
            if (r.ok) {
              loadAdminRequests();
              loadAdminUsers();
            } else {
              const e = await r.json().catch(() => ({}));
              showModal(e.detail || "Error", "alert");
            }
          } catch (e) {
            showModal("Error: " + e.message, "alert");
          }
        });
      });

      area.querySelectorAll(".btn-reject").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.getAttribute("data-id");
          if (!await showModal(t("Reject this request?", "Rechazar esta solicitud?"), "confirm")) return;
          btn.disabled = true;
          try {
            await setupFetch(`/api/v1/admin/access-requests/${id}/reject`, { method: "POST" });
            loadAdminRequests();
          } catch (e) {
            showModal("Error", "alert");
          }
        });
      });
    } catch (e) {
      area.innerHTML = `<p style="color:var(--accent-red);">Error loading requests.</p>`;
    }
  }

  async function loadAdminUsers() {
    const area = el("#admin-tab-users");
    if (!area) return;
    area.innerHTML = `<p class="muted-copy">${t("Loading users...", "Cargando usuarios...")}</p>`;

    try {
      const res = await setupFetch("/api/v1/admin/users");
      if (!res.ok) return;
      const data = await res.json();
      const users = data.users || [];

      area.innerHTML = `
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead><tr>
              <th>${t("User", "Usuario")}</th>
              <th>${t("Status", "Estado")}</th>
              <th>${t("Credits", "Creditos")}</th>
              <th>${t("Runs", "Runs")}</th>
              <th>${t("Actions", "Acciones")}</th>
            </tr></thead>
            <tbody>
              ${users
                .map(
                  (u) => `
                <tr>
                  <td>
                    <span style="font-weight:600;">${escapeHtml(u.email)}</span>
                    ${u.is_owner ? '<span class="owner-badge" title="Owner">owner</span>' : u.is_admin ? '<span class="admin-badge" title="Admin">admin</span>' : ""}
                  </td>
                  <td><span class="pill pill-sm ${u.status === "approved" ? "pill-green" : u.status === "suspended" ? "pill-red" : "pill-amber"}">${u.status || "pending"}</span></td>
                  <td style="font-weight:600;color:var(--accent-cyan);">${u.credits ?? 0}</td>
                  <td>${u.total_runs ?? 0}</td>
                  <td class="action-cell">
                    <button class="btn-sm btn-grant" data-user-id="${u.id}" data-email="${escapeHtml(u.email)}">+ ${t("Credits", "Creditos")}</button>
                    ${u.is_owner ? "" : u.status === "suspended"
                      ? `<button class="btn-sm btn-reactivate" data-user-id="${u.id}">${t("Reactivate", "Reactivar")}</button>`
                      : `<button class="btn-sm btn-suspend" data-user-id="${u.id}">${t("Suspend", "Suspender")}</button>`}
                    ${u.is_owner ? "" : `<button class="btn-sm btn-delete-user" data-user-id="${u.id}" data-email="${escapeHtml(u.email)}">${t("Delete", "Eliminar")}</button>`}
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`;

      // Grant credits
      area.querySelectorAll(".btn-grant").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const userId = btn.getAttribute("data-user-id");
          const email = btn.getAttribute("data-email");
          const amountStr = await showModal(t(`Credits to grant to ${email}:`, `Creditos a otorgar a ${email}:`), "prompt");
          if (!amountStr) return;
          const amount = parseInt(amountStr, 10);
          if (isNaN(amount) || amount <= 0) return showModal(t("Invalid amount.", "Monto invalido."), "alert");
          btn.disabled = true;
          try {
            const r = await setupFetch("/api/v1/admin/grant-credits", {
              method: "POST",
              body: JSON.stringify({ user_id: userId, amount }),
            });
            if (r.ok) loadAdminUsers();
            else {
              const e = await r.json().catch(() => ({}));
              showModal(e.detail || "Error", "alert");
            }
          } catch (e) {
            showModal("Error: " + e.message, "alert");
          } finally {
            btn.disabled = false;
          }
        });
      });

      // Suspend user
      area.querySelectorAll(".btn-suspend").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const userId = btn.getAttribute("data-user-id");
          const ok = await showModal(t("Suspend this user? They won't be able to log in.", "Suspender este usuario? No podra iniciar sesion."), "confirm");
          if (!ok) return;
          btn.disabled = true;
          try {
            const r = await setupFetch(`/api/v1/admin/users/${userId}/suspend`, { method: "POST" });
            if (r.ok) loadAdminUsers();
            else { const e = await r.json().catch(() => ({})); showModal(e.detail || "Error", "alert"); }
          } catch (e) { showModal("Error", "alert"); }
          finally { btn.disabled = false; }
        });
      });

      // Reactivate user
      area.querySelectorAll(".btn-reactivate").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const userId = btn.getAttribute("data-user-id");
          btn.disabled = true;
          try {
            const r = await setupFetch(`/api/v1/admin/users/${userId}/reactivate`, { method: "POST" });
            if (r.ok) loadAdminUsers();
            else { const e = await r.json().catch(() => ({})); showModal(e.detail || "Error", "alert"); }
          } catch (e) { showModal("Error", "alert"); }
          finally { btn.disabled = false; }
        });
      });

      // Delete user
      area.querySelectorAll(".btn-delete-user").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const userId = btn.getAttribute("data-user-id");
          const email = btn.getAttribute("data-email");
          const ok = await showModal(t(`Permanently delete ${email}? This cannot be undone.`, `Eliminar permanentemente a ${email}? Esta accion no se puede deshacer.`), "confirm");
          if (!ok) return;
          btn.disabled = true;
          try {
            const r = await setupFetch(`/api/v1/admin/users/${userId}`, { method: "DELETE" });
            if (r.ok) loadAdminUsers();
            else { const e = await r.json().catch(() => ({})); showModal(e.detail || "Error", "alert"); }
          } catch (e) { showModal("Error", "alert"); }
          finally { btn.disabled = false; }
        });
      });
    } catch (e) {
      area.innerHTML = `<p>Error loading users.</p>`;
    }
  }

  async function loadAdminUsage() {
    const area = el("#admin-tab-usage");
    if (!area) return;
    area.innerHTML = `<p class="muted-copy">${t("Loading platform usage...", "Cargando uso de plataforma...")}</p>`;

    try {
      const res = await setupFetch("/api/v1/admin/users");
      if (!res.ok) return;
      const data = await res.json();
      const users = data.users || [];

      const totalCredits = users.reduce((sum, u) => sum + (u.credits || 0), 0);
      const totalRuns = users.reduce((sum, u) => sum + (u.total_runs || 0), 0);

      area.innerHTML = `
        <div class="dashboard-stats" style="margin-bottom:2rem;">
          <div class="stat-card stat-cyan">
            <span class="stat-value">${users.length}</span>
            <p class="stat-label">${t("Total Users", "Total Usuarios")}</p>
          </div>
          <div class="stat-card stat-purple">
            <span class="stat-value">${totalRuns}</span>
            <p class="stat-label">${t("Total Runs", "Total Runs")}</p>
          </div>
          <div class="stat-card stat-green">
            <span class="stat-value">${totalCredits}</span>
            <p class="stat-label">${t("Credits Outstanding", "Creditos Vigentes")}</p>
          </div>
        </div>
        <h4>${t("Per-User Breakdown", "Desglose por Usuario")}</h4>
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead><tr>
              <th>${t("User", "Usuario")}</th>
              <th>${t("Credits", "Creditos")}</th>
              <th>${t("Runs", "Runs")}</th>
              <th>${t("Daily", "Diarios")}</th>
            </tr></thead>
            <tbody>
              ${users
                .map(
                  (u) => `
                <tr>
                  <td>${escapeHtml(u.email)}</td>
                  <td style="font-weight:600;color:var(--accent-cyan);">${u.credits ?? 0}</td>
                  <td>${u.total_runs ?? 0}</td>
                  <td>${u.daily_runs ?? 0}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`;
    } catch (e) {
      area.innerHTML = `<p>Error.</p>`;
    }
  }

  /* ── Admin Revenue ─────────────────────────────────────────────── */
  async function loadAdminRevenue() {
    const area = el("#admin-tab-revenue");
    if (!area) return;
    area.innerHTML = `<p class="muted-copy">${t("Loading revenue data...", "Cargando datos de ingresos...")}</p>`;

    try {
      const [res, settingsRes] = await Promise.all([
        setupFetch("/api/v1/admin/billing/summary"),
        setupFetch("/api/v1/admin/settings"),
      ]);
      if (!res.ok) {
        area.innerHTML = `<p style="color:var(--accent-red);">${t("Could not load revenue data.", "No se pudieron cargar los datos de ingresos.")}</p>`;
        return;
      }
      const data = await res.json();
      if (settingsRes.ok) {
        const settings = await settingsRes.json();
        data.stripe_mode = settings.stripe_mode || "test";
        data.initial_credits = settings.default_initial_credits || "0";
      }

      area.innerHTML = `
        <div class="dashboard-stats" style="margin-bottom:2rem;">
          <div class="stat-card stat-cyan">
            <span class="stat-value">$${(data.total_revenue || 0).toLocaleString()}</span>
            <p class="stat-label">${t("Total Revenue", "Ingresos Totales")}</p>
          </div>
          <div class="stat-card stat-green">
            <span class="stat-value">$${(data.month_revenue || 0).toLocaleString()}</span>
            <p class="stat-label">${t("This Month", "Este Mes")}</p>
          </div>
          <div class="stat-card stat-purple">
            <span class="stat-value">${data.paying_users || 0}</span>
            <p class="stat-label">${t("Paying Users", "Usuarios de Pago")}</p>
          </div>
        </div>

        ${data.revenue_by_user?.length ? `
        <h4>${t("Revenue by User", "Ingresos por Usuario")}</h4>
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead><tr>
              <th>${t("User", "Usuario")}</th>
              <th>${t("Total Paid", "Total Pagado")}</th>
              <th>${t("Credits Purchased", "Creditos Comprados")}</th>
              <th>${t("Last Purchase", "Ultima Compra")}</th>
            </tr></thead>
            <tbody>
              ${data.revenue_by_user.map(u => `
                <tr>
                  <td>${escapeHtml(u.email || "")}</td>
                  <td style="font-weight:600;color:var(--accent-green);">$${(u.total_paid || 0).toLocaleString()}</td>
                  <td>${u.credits_purchased || 0}</td>
                  <td class="muted-copy">${u.last_purchase ? new Date(u.last_purchase).toLocaleDateString() : "-"}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>` : `<p class="muted-copy">${t("No revenue data yet.", "Sin datos de ingresos aun.")}</p>`}

        <div class="account-card" style="margin-top:2rem;">
          <h4>${t("Stripe Mode", "Modo de Stripe")}</h4>
          <p class="muted-copy" style="margin-bottom:0.5rem;">${t("Current mode:", "Modo actual:")} <strong id="admin-stripe-mode">${escapeHtml(data.stripe_mode || "test")}</strong></p>
          <button class="secondary-button" id="btn-toggle-stripe-mode">${t("Toggle to", "Cambiar a")} ${data.stripe_mode === "live" ? "test" : "live"}</button>
        </div>

        <div class="account-card" style="margin-top:1rem;">
          <h4>${t("Initial Credits for New Users", "Creditos Iniciales para Nuevos Usuarios")}</h4>
          <div style="display:flex;gap:8px;align-items:center;margin-top:0.5rem;">
            <input type="number" id="admin-initial-credits" min="0" max="10000" value="${data.initial_credits ?? 5}" class="otp-code-input" style="text-align:left;letter-spacing:normal;font-size:1rem;width:100px;" />
            <button class="secondary-button" id="btn-save-initial-credits">${t("Save", "Guardar")}</button>
          </div>
        </div>
      `;

      // Toggle stripe mode
      const toggleBtn = el("#btn-toggle-stripe-mode");
      if (toggleBtn) {
        toggleBtn.addEventListener("click", async () => {
          const newMode = (data.stripe_mode === "live") ? "test" : "live";
          const confirmMsg = t(
            "Switch Stripe to " + newMode + " mode? This affects all payment processing.",
            "Cambiar Stripe a modo " + newMode + "? Esto afecta todo el procesamiento de pagos."
          );
          const confirmed = await showModal(confirmMsg, "confirm");
          if (!confirmed) return;
          try {
            const res2 = await setupFetch("/api/v1/admin/settings", {
              method: "PATCH",
              body: JSON.stringify({ stripe_mode: newMode }),
            });
            if (res2.ok) loadAdminRevenue();
          } catch (e) {
            showModal("Error: " + e.message, "alert");
          }
        });
      }

      // Save initial credits
      const saveCreditsBtn = el("#btn-save-initial-credits");
      if (saveCreditsBtn) {
        saveCreditsBtn.addEventListener("click", async () => {
          const val = parseInt(document.getElementById("admin-initial-credits")?.value, 10);
          if (isNaN(val) || val < 0) return;
          try {
            const res2 = await setupFetch("/api/v1/admin/settings", {
              method: "PATCH",
              body: JSON.stringify({ initial_credits: val }),
            });
            if (res2.ok) {
              showModal(t("Saved!", "Guardado!"), "alert");
            }
          } catch (e) {
            showModal("Error: " + e.message, "alert");
          }
        });
      }
    } catch (e) {
      area.innerHTML = `<p style="color:var(--accent-red);">Error: ${escapeHtml(e.message)}</p>`;
    }
  }

  /* ── Billing Area ────────────────────────────────────────────── */
  async function loadBillingArea() {
    const account = await fetchAccount();
    const balanceEl = el("#billing-credit-balance");
    if (balanceEl && account) balanceEl.textContent = account.credits || 0;

    // Show test mode banner if applicable
    try {
      const settingsRes = await setupFetch("/api/v1/billing/config");
      if (settingsRes.ok) {
        const cfg = await settingsRes.json();
        const banner = el("#billing-test-banner");
        if (banner && cfg.stripe_mode === "test") banner.style.display = "block";
      }
    } catch (e) { /* ignore */ }

    // Preset buy buttons
    document.querySelectorAll(".billing-buy-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const qty = parseInt(btn.getAttribute("data-credits"), 10);
        if (qty) purchaseCredits(qty);
      });
    });

    // Custom qty price display
    const customInput = el("#billing-custom-qty");
    const customPrice = el("#billing-custom-price");
    if (customInput && customPrice) {
      customInput.addEventListener("input", () => {
        const qty = parseInt(customInput.value, 10);
        if (qty > 0) {
          customPrice.textContent = "$" + qty + ".00";
        } else {
          customPrice.textContent = "";
        }
      });
    }

    // Custom buy button
    const customBuyBtn = el("#billing-custom-buy");
    if (customBuyBtn) {
      customBuyBtn.addEventListener("click", () => {
        const qty = parseInt(customInput?.value, 10);
        if (qty > 0) purchaseCredits(qty);
      });
    }

    // Load invoices
    loadInvoices();

    // Check for Stripe redirect params
    const params = new URLSearchParams(window.location.search);
    if (params.get("billing") === "success") {
      showModal(t("Payment successful! Credits have been added to your account.", "Pago exitoso! Los creditos se han agregado a tu cuenta."), "alert");
      const url = new URL(window.location);
      url.searchParams.delete("billing");
      url.searchParams.delete("session_id");
      window.history.replaceState({}, "", url);
    } else if (params.get("billing") === "canceled") {
      showModal(t("Payment was canceled.", "El pago fue cancelado."), "alert");
      const url = new URL(window.location);
      url.searchParams.delete("billing");
      window.history.replaceState({}, "", url);
    }
  }

  async function purchaseCredits(qty) {
    try {
      const res = await setupFetch("/api/v1/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ credits: qty }),
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        showModal(data.error || t("Could not start checkout.", "No se pudo iniciar el checkout."), "alert");
      }
    } catch (e) {
      showModal("Error: " + e.message, "alert");
    }
  }

  async function loadInvoices() {
    const area = el("#billing-invoices");
    if (!area) return;
    area.innerHTML = `<p class="muted-copy">${t("Loading...", "Cargando...")}</p>`;
    try {
      const res = await setupFetch("/api/v1/billing/invoices");
      if (!res.ok) {
        area.innerHTML = `<p class="muted-copy">${t("Could not load payment history.", "No se pudo cargar el historial de pagos.")}</p>`;
        return;
      }
      const invoices = await res.json();
      if (!invoices.length) {
        area.innerHTML = `<p class="muted-copy">${t("No payments yet.", "Sin pagos aun.")}</p>`;
        return;
      }
      area.innerHTML = `
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead><tr>
              <th>${t("Date", "Fecha")}</th>
              <th>${t("Credits", "Creditos")}</th>
              <th>${t("Amount", "Monto")}</th>
              <th>${t("Status", "Estado")}</th>
            </tr></thead>
            <tbody>
              ${invoices.map(inv => `
                <tr>
                  <td>${new Date(inv.created_at || inv.date).toLocaleDateString()}</td>
                  <td>${inv.credits || 0}</td>
                  <td>$${(inv.amount_cents ? inv.amount_cents / 100 : inv.amount || 0).toFixed(2)}</td>
                  <td><span class="pill pill-sm ${inv.status === "paid" ? "pill-green" : "pill-blue"}">${inv.status || "paid"}</span></td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>`;
    } catch (e) {
      area.innerHTML = `<p>Error.</p>`;
    }
  }

  /* ── API Keys Area ─────────────────────────────────────────────── */
  async function loadApiArea() {
    const keysArea = el("#app-api-keys-area");
    if (!keysArea) return;

    keysArea.innerHTML = `<p class="muted-copy">${t("Loading keys...", "Cargando keys...")}</p>`;
    const account = await fetchAccount();
    if (!account) {
      keysArea.innerHTML = `<p class="muted-copy">${t("Could not load account data.", "No se pudo cargar la cuenta.")}</p>`;
      return;
    }

    let html = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
        <h3 style="margin:0;">${t("Your API Keys", "Tus API Keys")}</h3>
        <button class="primary-button" id="btn-create-apikey">${t("+ Create Key", "+ Crear Key")}</button>
      </div>
      <div id="new-key-result" class="key-result" style="display:none;"></div>
    `;

    if (!account.api_keys?.length) {
      html += `<div class="empty-state"><p>${t("No API keys yet. Create one to integrate via REST API or MCP.", "Sin API keys. Crea una para integrar via REST API o MCP.")}</p></div>`;
    } else {
      html += account.api_keys
        .map(
          (key) => `
        <div class="api-key-row">
          <div class="api-key-info">
            <span class="api-key-name">${escapeHtml(key.name)}</span>
            <span class="api-key-prefix">${escapeHtml(key.prefix)}••••••••</span>
          </div>
          <button class="ghost-button btn-revoke-apikey" data-id="${key.id}">${t("Revoke", "Revocar")}</button>
        </div>`
        )
        .join("");
    }

    keysArea.innerHTML = html;

    const btnCreate = el("#btn-create-apikey");
    if (btnCreate) {
      btnCreate.addEventListener("click", async () => {
        const name = await showModal(t("Name for the API Key:", "Nombre para la API Key:"), "prompt");
        if (!name) return;
        btnCreate.disabled = true;
        try {
          const res = await setupFetch("/api/v1/api-keys", {
            method: "POST",
            body: JSON.stringify({ name }),
          });
          const data = await res.json();
          if (res.ok) {
            const resDiv = el("#new-key-result");
            if (resDiv) {
              resDiv.style.display = "block";
              resDiv.innerHTML = `
                <div class="key-created-banner">
                  <p class="key-warning">${t("Save this key now — it will NOT be shown again!", "Guarda esta key ahora — NO se mostrara de nuevo!")}</p>
                  <div class="key-value-row">
                    <span class="key-value" id="created-key-value">${escapeHtml(data.api_key)}</span>
                    <button class="btn-copy-key" id="btn-copy-key">${t("Copy", "Copiar")}</button>
                  </div>
                </div>`;
              const copyBtn = el("#btn-copy-key");
              if (copyBtn) {
                copyBtn.addEventListener("click", () => {
                  navigator.clipboard.writeText(data.api_key).then(() => {
                    copyBtn.textContent = t("Copied!", "Copiado!");
                    setTimeout(() => { copyBtn.textContent = t("Copy", "Copiar"); }, 2000);
                  }).catch(() => {
                    // Fallback: select the text
                    const valEl = el("#created-key-value");
                    if (valEl) {
                      const range = document.createRange();
                      range.selectNodeContents(valEl);
                      const sel = window.getSelection();
                      sel.removeAllRanges();
                      sel.addRange(range);
                    }
                  });
                });
              }
            }
            // Reload the key list below the banner (but keep banner visible)
            _refreshKeyList();
          } else {
            showModal(data.detail || "Error", "alert");
          }
        } catch (e) {
          showModal("Error: " + e.message, "alert");
        } finally {
          btnCreate.disabled = false;
        }
      });
    }

    async function _refreshKeyList() {
      const account = await fetchAccount();
      if (!account?.api_keys) return;
      // Update just the key list portion (after the banner)
      const existingRows = keysArea.querySelectorAll(".api-key-row");
      existingRows.forEach((r) => r.remove());
      const emptyState = keysArea.querySelector(".empty-state");
      if (emptyState) emptyState.remove();

      const fragment = document.createDocumentFragment();
      account.api_keys.forEach((key) => {
        const row = document.createElement("div");
        row.className = "api-key-row";
        row.innerHTML = `
          <div class="api-key-info">
            <span class="api-key-name">${escapeHtml(key.name)}</span>
            <span class="api-key-prefix">${escapeHtml(key.prefix)}••••••••</span>
          </div>
          <button class="ghost-button btn-revoke-apikey" data-id="${key.id}">${t("Revoke", "Revocar")}</button>`;
        fragment.appendChild(row);
      });
      keysArea.appendChild(fragment);
      // Re-wire revoke buttons
      keysArea.querySelectorAll(".btn-revoke-apikey").forEach((btn) => {
        btn.addEventListener("click", async () => {
          if (!await showModal(t("Revoke this key?", "Revocar esta key?"), "confirm")) return;
          const id = btn.getAttribute("data-id");
          try {
            const res = await setupFetch(`/api/v1/api-keys/${id}`, { method: "DELETE" });
            if (res.ok) loadApiArea();
            else {
              const data = await res.json().catch(() => ({}));
              showModal(data.detail || "Error", "alert");
            }
          } catch (e) {
            showModal("Error", "alert");
          }
        });
      });
    }

    document.querySelectorAll(".btn-revoke-apikey").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!await showModal(t("Revoke this key?", "Revocar esta key?"), "confirm")) return;
        const id = btn.getAttribute("data-id");
        try {
          const res = await setupFetch(`/api/v1/api-keys/${id}`, { method: "DELETE" });
          if (res.ok) loadApiArea();
          else {
            const data = await res.json().catch(() => ({}));
            showModal(data.detail || "Error", "alert");
          }
        } catch (e) {
          showModal("Error", "alert");
        }
      });
    });
  }

  /* ── Account & Usage ───────────────────────────────────────────── */
  async function loadAccountArea() {
    const accArea = el("#app-account-area");
    if (!accArea) return;

    accArea.innerHTML = `<p class="muted-copy">${t("Loading...", "Cargando...")}</p>`;
    const account = await fetchAccount();
    if (!account) {
      accArea.innerHTML = `<p class="muted-copy">${t("Could not load account.", "No se pudo cargar la cuenta.")}</p>`;
      return;
    }

    accArea.innerHTML = `
      <div class="dashboard-stats" style="margin-bottom:2rem;">
        <div class="stat-card stat-cyan">
          <span class="stat-value">${account.credits || 0}</span>
          <p class="stat-label">${t("Credits Balance", "Saldo de Creditos")}</p>
        </div>
        <div class="stat-card stat-purple">
          <span class="stat-value">${account.total_runs || 0}</span>
          <p class="stat-label">${t("Total Deployments", "Total Despliegues")}</p>
        </div>
        <div class="stat-card stat-green">
          <span class="stat-value">${account.daily_runs || 0}</span>
          <p class="stat-label">${t("Today (24h)", "Hoy (24h)")}</p>
        </div>
      </div>

      <div class="account-details">
        <div class="account-card">
          <h4>${t("Profile", "Perfil")}</h4>
          <div class="detail-row"><span class="muted-copy">${t("Email", "Correo")}</span><span>${escapeHtml(account.email || "")}</span></div>
          <div class="detail-row"><span class="muted-copy">${t("Name", "Nombre")}</span><span id="acc-name-display">${escapeHtml(account.full_name || "-")}</span> <button class="ghost-button" id="btn-edit-name" style="font-size:0.75rem;padding:2px 8px;">${t("Edit", "Editar")}</button></div>
          <div class="detail-row"><span class="muted-copy">${t("Role", "Rol")}</span><span>${account.is_admin ? "Admin" : t("Member", "Miembro")}</span></div>
        </div>
        <div class="account-card">
          <h4>${t("Notifications", "Notificaciones")}</h4>
          <div class="detail-row">
            <span class="muted-copy">${t("Email when deployment is ready", "Email cuando el despliegue este listo")}</span>
            <label class="toggle-switch">
              <input type="checkbox" id="toggle-email-notif" ${account.email_notifications !== false ? "checked" : ""}>
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
        <div class="account-card">
          <h4>${t("API Keys", "API Keys")}</h4>
          ${
            account.api_keys?.length
              ? account.api_keys
                  .map(
                    (k) => `
              <div class="detail-row">
                <span>${escapeHtml(k.name)}</span>
                <span class="mono-cell">${escapeHtml(k.prefix)}••••</span>
              </div>`
                  )
                  .join("")
              : `<p class="muted-copy">${t("No API keys.", "Sin API keys.")}</p>`
          }
          <a class="section-link" href="#api" style="margin-top:0.5rem;display:block;">${t("Manage keys", "Gestionar keys")} &rarr;</a>
        </div>
      </div>
    `;

    // Wire edit name button
    const editNameBtn = el("#btn-edit-name");
    if (editNameBtn) {
      editNameBtn.addEventListener("click", async () => {
        const newName = await showModal(
          t("Enter your name:", "Ingresa tu nombre:"),
          "prompt",
          account.full_name || ""
        );
        if (newName === null) return;
        try {
          const res = await setupFetch("/api/v1/account", {
            method: "PATCH",
            body: JSON.stringify({ full_name: newName }),
          });
          if (res.ok) {
            loadAccountArea();
          } else {
            const data = await res.json().catch(() => ({}));
            showModal(data.detail || "Error", "alert");
          }
        } catch (e) {
          showModal("Error: " + e.message, "alert");
        }
      });
    }

    // Wire email notifications toggle
    const emailToggle = el("#toggle-email-notif");
    if (emailToggle) {
      emailToggle.addEventListener("change", async () => {
        try {
          await setupFetch("/api/v1/account", {
            method: "PATCH",
            body: JSON.stringify({ email_notifications: emailToggle.checked }),
          });
        } catch (e) {
          emailToggle.checked = !emailToggle.checked;
        }
      });
    }
  }

  /* ── Report viewer ─────────────────────────────────────────────── */
  const _reportBackBtn = el("#report-viewer-back");
  if (_reportBackBtn) {
    _reportBackBtn.addEventListener("click", () => {
      switchTab(_reportPreviousTab || "history");
    });
  }
  let _reportPreviousTab = "history";

  // Track lazy-init state for graph/evidence views
  let _graphInitialized = false;
  let _evidenceInitialized = false;
  let _currentSnapshot = null;

  // Wire up tab clicks
  const _rvTabs = els(".rv-tab");
  _rvTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabId = tab.dataset.tab;
      _switchViewerTab(tabId);
    });
  });

  function _switchViewerTab(tabId) {
    // Update tab buttons
    _rvTabs.forEach((t) => t.classList.toggle("rv-tab-active", t.dataset.tab === tabId));
    // Update panels
    ["report", "graph", "evidence", "artifacts"].forEach((id) => {
      const panel = el(`#rv-panel-${id}`);
      if (panel) {
        panel.style.display = id === tabId ? "block" : "none";
        panel.classList.toggle("rv-panel-active", id === tabId);
      }
    });
    // Lazy-init graph and evidence board
    if (tabId === "graph" && !_graphInitialized && _currentSnapshot) {
      _initGraphView(_currentSnapshot);
    }
    if (tabId === "evidence" && !_evidenceInitialized && _currentSnapshot) {
      _initEvidenceView(_currentSnapshot);
    }
  }

  async function _initGraphView(snapshot) {
    try {
      const [mod, { extractSectionJson }] = await Promise.all([
        import("./js/graph-viewer.js"),
        import("./js/report-viewer.js"),
      ]);
      const graphData = extractSectionJson(snapshot.sections, "graph_visualization");
      if (!graphData || !graphData.nodes) return;

      mod.initGraphViewer("rv-graph-container", graphData, {
        onNodeSelect: (nodeData) => mod.renderNodeDetails("rv-graph-details", nodeData),
      });
      mod.renderGraphToolbar("rv-graph-toolbar");
      _graphInitialized = true;
    } catch (e) {
      console.error("Graph viewer init error:", e);
    }
  }

  async function _initEvidenceView(snapshot) {
    try {
      const [mod, { extractSectionJson }] = await Promise.all([
        import("./js/evidence-board.js"),
        import("./js/report-viewer.js"),
      ]);
      const boardData = extractSectionJson(snapshot.sections, "evidence_board");
      if (!boardData) return;

      mod.initEvidenceBoard("rv-evidence-container", boardData);
      _evidenceInitialized = true;
    } catch (e) {
      console.error("Evidence board init error:", e);
    }
  }

  async function _renderOsintSummary(snapshot) {
    const { renderExecutiveSummary, renderPhotoRow } = await import("./js/report-viewer.js");
    renderExecutiveSummary(el("#report-viewer-summary"), snapshot);
    renderPhotoRow(el("#report-viewer-photos"), snapshot);
  }

  window.viewRun = async function (runId) {
    // Remember where we came from so "Back" returns there
    _reportPreviousTab = currentScreen.replace("workspace-", "") || "history";
    _graphInitialized = false;
    _evidenceInitialized = false;
    _currentSnapshot = null;

    // For active runs (queued/running), use the old research view
    const activeTask = _activeTasks.get(runId);
    if (activeTask && ["queued", "running"].includes(activeTask.status)) {
      switchTab("research");
      const statusArea = el("#app-run-status-area");
      if (statusArea) statusArea.style.display = "block";
      resumeRun(runId);
      return;
    }

    // Switch to report viewer section
    switchTab("report-viewer");
    _switchViewerTab("report");

    const titleEl = el("#report-viewer-title");
    const styleEl = el("#report-viewer-style");
    const metaEl = el("#report-viewer-meta");
    const sectionsEl = el("#report-viewer-sections");
    const artifactGridEl = el("#report-viewer-artifact-grid");
    const exportHtmlEl = el("#report-viewer-export-html");

    // Loading state
    if (titleEl) titleEl.textContent = t("Loading deployment...", "Cargando despliegue...");
    if (metaEl) metaEl.textContent = "";
    if (sectionsEl) sectionsEl.innerHTML = "";
    if (artifactGridEl) artifactGridEl.innerHTML = "";

    try {
      const res = await setupFetch(`/api/v1/runs/${encodeURIComponent(runId)}`);
      if (!res.ok) throw new Error(`${res.status}`);
      const snapshot = await res.json();
      _currentSnapshot = snapshot;
      const isOsint = snapshot.research_style === "osint_360";

      // Show/hide OSINT-only tabs
      els(".rv-tab-osint-only").forEach((tab) => {
        tab.style.display = isOsint ? "" : "none";
      });

      // Header
      const prompt = snapshot.prompt || t("Product Deployment", "Despliegue de Producto");
      if (titleEl) titleEl.textContent = prompt;
      if (styleEl) {
        styleEl.textContent = _getCapLabel(snapshot.research_style) || styleLabel(snapshot.research_style);
      }
      const date = snapshot.created_at ? new Date(snapshot.created_at).toLocaleString() : "";
      const statusText = snapshot.status === "completed" ? t("Completed", "Completado")
        : snapshot.status === "failed" ? t("Failed", "Fallido") : snapshot.status;
      let durationText = "";
      if (snapshot.duration_seconds != null) {
        const mins = Math.floor(snapshot.duration_seconds / 60);
        const secs = snapshot.duration_seconds % 60;
        durationText = mins > 0
          ? `  —  ${mins}m ${secs}s`
          : `  —  ${secs}s`;
      }
      if (metaEl) metaEl.textContent = `${statusText} ${date ? "  —  " + date : ""}${durationText}`;

      // Export link
      if (exportHtmlEl) {
        exportHtmlEl.href = `/api/v1/runs/${encodeURIComponent(runId)}/report`;
      }

      // Executive summary (OSINT)
      if (isOsint) {
        _renderOsintSummary(snapshot);
      }

      // Render sections with clickable URLs
      if (sectionsEl) {
        const { makeUrlsClickable } = await import("./js/renderers.js");
        const VISUAL_SECTION_IDS = new Set(["graph_visualization", "evidence_board"]);
        const sections = (snapshot.sections || []).filter((s) => !VISUAL_SECTION_IDS.has(s.id));
        sectionsEl.innerHTML = sections.map((section) => `
          <article class="result-card">
            <p class="eyebrow">${escapeHtml(styleLabel(snapshot.research_style) || "deployment")}</p>
            <h3>${escapeHtml(section.title)}</h3>
            <div class="result-html">${makeUrlsClickable(section.html || "")}</div>
          </article>
        `).join("");
      }

      // Render artifacts in artifacts tab
      if (artifactGridEl) {
        const artifacts = snapshot.artifacts || [];
        if (artifacts.length) {
          artifactGridEl.innerHTML = artifacts.map((artifact) => `
            <article class="artifact-card ws-artifact-card">
              <div>
                <p class="eyebrow">${escapeHtml(artifact.kind || "file")}</p>
                <h4>${escapeHtml(artifact.name)}</h4>
              </div>
              <a class="ghost-link" href="${artifact.url}" target="_blank" rel="noreferrer">
                ${escapeHtml(t("Open", "Abrir"))}
              </a>
            </article>
          `).join("");
        } else {
          artifactGridEl.innerHTML = `<p class="muted-copy">${escapeHtml(t("No artifacts.", "Sin artefactos."))}</p>`;
        }
      }
    } catch (e) {
      console.error("Report viewer error:", e);
      if (titleEl) titleEl.textContent = t("Error loading deployment", "Error cargando despliegue");
      if (metaEl) metaEl.textContent = e.message;
    }
  };

  /* ── History ───────────────────────────────────────────────────── */
  async function loadHistory() {
    const historyList = el("#app-history-list");
    if (!historyList) return;

    // Wire up filter buttons (only once)
    const applyBtn = el("#app-apply-filters");
    const resetBtn = el("#app-reset-filters");
    if (applyBtn && !applyBtn._wired) {
      applyBtn._wired = true;
      applyBtn.addEventListener("click", () => _fetchAndRenderHistory(historyList));
    }
    if (resetBtn && !resetBtn._wired) {
      resetBtn._wired = true;
      resetBtn.addEventListener("click", () => {
        const fs = el("#app-filter-style"); if (fs) fs.value = "";
        const ft = el("#app-filter-status"); if (ft) ft.value = "";
        const fd = el("#app-filter-date-from"); if (fd) fd.value = "";
        const fdt = el("#app-filter-date-to"); if (fdt) fdt.value = "";
        const fq = el("#app-filter-query"); if (fq) fq.value = "";
        _fetchAndRenderHistory(historyList);
      });
    }

    _fetchAndRenderHistory(historyList);
  }

  async function _fetchAndRenderHistory(historyList) {
    historyList.innerHTML = `<p class="muted-copy">${t("Loading...", "Cargando...")}</p>`;

    const filters = {};
    const styleVal = el("#app-filter-style")?.value;
    const statusVal = el("#app-filter-status")?.value;
    const queryVal = el("#app-filter-query")?.value;
    if (styleVal) filters.research_style = styleVal;
    if (statusVal) filters.status = statusVal;
    if (queryVal) filters.q = queryVal;

    const hist = await fetchHistory(25, filters);
    if (!hist?.runs?.length) {
      const errMsg = hist?._error ? ` <span style="color:var(--accent-red);font-size:0.8rem;">(${escapeHtml(hist._error)})</span>` : "";
      historyList.innerHTML = `<p class="muted-copy">${t("No deployments yet.", "Sin despliegues todavia.")}${errMsg}</p>`;
      return;
    }

    historyList.innerHTML = hist.runs
      .map(
        (run) => `
        <article class="history-card" data-id="${run.job_id}">
          <div class="hc-header">
            <span class="hc-mode">${styleLabel(run.research_style || "deploy_product")}</span>
            <span class="pill ${run.status === "completed" ? "pill-green" : run.status === "failed" ? "pill-red" : "pill-blue"}">${run.status}</span>
          </div>
          <h4 class="hc-prompt">${escapeHtml(run.prompt || "Run " + (run.job_id || "").slice(0, 8))}</h4>
          <div class="hc-footer">
            <span class="hc-date">${run.created_at ? new Date(run.created_at).toLocaleString(undefined, {dateStyle: "medium", timeStyle: "short"}) : ""}</span>
            <div style="display:flex;gap:6px;">
              ${run.status !== "running" && run.status !== "queued" ? `<button class="ghost-button hc-delete" data-job-id="${run.job_id}" style="color:var(--accent-red);">${t("Delete", "Eliminar")}</button>` : ""}
              ${run.status === "completed" ? `<button class="ghost-button hc-view" onclick="window.viewRun('${run.job_id}')">${t("View Deployment", "Ver Despliegue")}</button>` : ""}
            </div>
          </div>
        </article>`
      )
      .join("");

    // Wire delete buttons
    historyList.querySelectorAll(".hc-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const jobId = btn.getAttribute("data-job-id");
        if (!await showModal(t("Delete this deployment?", "Eliminar este despliegue?"), "confirm")) return;
        btn.disabled = true;
        try {
          const res = await setupFetch(`/api/v1/runs/${jobId}`, { method: "DELETE" });
          if (res.ok) {
            _fetchAndRenderHistory(historyList);
          } else {
            const data = await res.json().catch(() => ({}));
            showModal(data.detail || "Error", "alert");
          }
        } catch (e) {
          showModal("Error: " + e.message, "alert");
        }
      });
    });
  }
}

/* ── Landing page boot ───────────────────────────────────────────── */
function bootLanding() {
  const form = document.getElementById("access-request-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("access-request-status");
    const formData = new FormData(form);
    const body = {
      email: formData.get("email"),
      full_name: formData.get("full_name"),
      company: formData.get("company"),
      message: formData.get("message"),
    };

    try {
      const res = await fetch("/api/v1/access/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        if (status) {
          status.style.color = "var(--accent-green)";
          status.textContent = t("Request submitted! We'll review it shortly.", "Solicitud enviada! La revisaremos pronto.");
        }
        form.reset();
      } else {
        const data = await res.json().catch(() => ({}));
        if (status) {
          status.style.color = "var(--accent-red)";
          status.textContent = data.detail || "Something went wrong.";
        }
      }
    } catch (err) {
      if (status) {
        status.style.color = "var(--accent-red)";
        status.textContent = "Network error.";
      }
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
