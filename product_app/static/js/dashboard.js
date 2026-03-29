/**
 * Dashboard section — owner (admin) and regular user views.
 * Exported: load(container, ctx)
 */

function statCard(value, label, colorClass) {
  return `<div class="stat-card ${colorClass}">
    <span class="stat-value">${value}</span>
    <p class="stat-label">${label}</p>
  </div>`;
}

function gsProgress(t) {
  let raw = null;
  try { raw = JSON.parse(localStorage.getItem("gs_progress") || "null"); } catch { /* ignore */ }
  const done = raw ? Object.values(raw).filter(Boolean).length : 0;
  if (done >= 5) {
    return `<p style="color:var(--accent-green);font-weight:600;">&#10003; ${t("Setup complete!", "¡Configuración completa!")}</p>`;
  }
  const pct = Math.round((done / 5) * 100);
  return `
    <p style="font-size:13px;color:var(--text-muted);margin:0 0 6px;">
      ${t(`${done} of 5 steps complete`, `${done} de 5 pasos completados`)}
    </p>
    <div class="gs-progress-bar">
      <div class="gs-progress-fill" style="width:${pct}%"></div>
    </div>`;
}

function ownerHtml(ctx) {
  const { PAGE, t } = ctx;
  const domain = PAGE.productDomain || `${PAGE.productSlug || "app"}.x53.ai`;
  return `
    <div class="dash-header">
      <div>
        <p class="dashboard-welcome">${t("Dashboard", "Panel")}</p>
        <p class="dashboard-sub">${t("Your product overview and quick access.", "Vista general del producto y acceso rápido.")}</p>
      </div>
    </div>
    <div class="dashboard-stats" id="dash-stats-row">
      ${statCard('<span class="stat-green" style="font-size:1rem;">&#9679; ' + t("Active", "Activo") + '</span>', t("Status", "Estado"), "stat-green")}
      ${statCard(`<span style="font-size:1rem;word-break:break-all;">${domain}</span>`, t("Domain", "Dominio"), "stat-cyan")}
      <div class="stat-card stat-purple" id="stat-agents">
        <span class="stat-value">—</span>
        <p class="stat-label">${t("Agents", "Agentes")}</p>
      </div>
      <div class="stat-card stat-cyan" id="stat-credits">
        <span class="stat-value">—</span>
        <p class="stat-label">${t("Credits", "Créditos")}</p>
      </div>
    </div>
    <div class="dashboard-grid">
      <div class="dashboard-section">
        <h3>${t("Quick Actions", "Acciones Rápidas")}</h3>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <a href="#getting-started" class="primary-button">${t("Getting Started", "Primeros Pasos")}</a>
          <a href="#how-it-works" class="secondary-button">${t("How It Works", "Cómo Funciona")}</a>
          <a href="#api" class="secondary-button">${t("API Keys", "Claves API")}</a>
        </div>
      </div>
      <div class="dashboard-section">
        <h3>${t("Setup Progress", "Progreso de Configuración")}</h3>
        ${gsProgress(t)}
      </div>
    </div>`;
}

function userHtml(ctx) {
  const { t } = ctx;
  return `
    <div class="dash-header">
      <div>
        <p class="dashboard-welcome">${t("Dashboard", "Panel")}</p>
        <p class="dashboard-sub">${t("Your account overview and available services.", "Vista de tu cuenta y servicios disponibles.")}</p>
      </div>
    </div>
    <div class="dashboard-stats" id="dash-stats-row">
      <div class="stat-card stat-cyan" id="stat-credits">
        <span class="stat-value">—</span>
        <p class="stat-label">${t("Credits", "Créditos")}</p>
      </div>
      <div class="stat-card stat-purple" id="stat-runs">
        <span class="stat-value">—</span>
        <p class="stat-label">${t("Total Runs", "Ejecuciones Totales")}</p>
      </div>
    </div>
    <div class="dashboard-section" style="margin-bottom:1.5rem;">
      <h3>${t("Available Services", "Servicios Disponibles")}</h3>
      <div id="dash-services-list" class="quick-launch-list">
        <p style="color:var(--text-muted);font-size:13px;">${t("Loading…", "Cargando…")}</p>
      </div>
    </div>
    <div class="stat-card" style="opacity:0.45;pointer-events:none;text-align:left;">
      <p style="margin:0;font-size:13px;color:var(--text-muted);">
        ${t("Customize via vibe coding", "Personaliza con vibe coding")}
      </p>
    </div>`;
}

async function fillOwnerStats(ctx) {
  const { fetchJson } = ctx;
  try {
    const [caps, acct] = await Promise.allSettled([
      fetchJson("/api/v1/research/capabilities"),
      fetchJson("/api/v1/account"),
    ]);
    const agentEl = document.getElementById("stat-agents");
    const creditEl = document.getElementById("stat-credits");
    if (agentEl && caps.status === "fulfilled") {
      const count = Array.isArray(caps.value?.styles) ? caps.value.styles.length : "?";
      agentEl.querySelector(".stat-value").textContent = count;
    }
    if (creditEl && acct.status === "fulfilled") {
      creditEl.querySelector(".stat-value").textContent = acct.value?.credits ?? "?";
    }
  } catch { /* silently degrade */ }
}

async function fillUserStats(ctx) {
  const { fetchJson, t, escapeHtml } = ctx;
  const [acct, caps] = await Promise.allSettled([
    fetchJson("/api/v1/account"),
    fetchJson("/api/v1/research/capabilities"),
  ]);

  const creditEl = document.getElementById("stat-credits");
  const runsEl   = document.getElementById("stat-runs");
  if (creditEl && acct.status === "fulfilled") {
    creditEl.querySelector(".stat-value").textContent = acct.value?.credits ?? "?";
  }
  if (runsEl && acct.status === "fulfilled") {
    runsEl.querySelector(".stat-value").textContent = acct.value?.total_runs ?? "?";
  }

  const listEl = document.getElementById("dash-services-list");
  if (!listEl) return;
  if (caps.status !== "fulfilled" || !Array.isArray(caps.value?.styles)) {
    listEl.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">${t("No services found.", "Sin servicios disponibles.")}</p>`;
    return;
  }
  listEl.innerHTML = caps.value.styles.map((s) => `
    <div class="quick-launch-item">
      <div>
        <div class="ql-label">${escapeHtml(s.name || s.id)}</div>
        <div class="ql-desc">${escapeHtml(s.description || "")}</div>
      </div>
      <span style="font-size:12px;color:var(--text-muted);white-space:nowrap;">
        ${s.credit_cost != null ? s.credit_cost + " " + t("cr", "cr") : ""}
      </span>
    </div>`).join("");
}

export async function load(container, ctx) {
  const { isAdmin } = ctx;
  container.innerHTML = isAdmin ? ownerHtml(ctx) : userHtml(ctx);
  if (isAdmin) {
    fillOwnerStats(ctx);
  } else {
    fillUserStats(ctx);
  }
}
