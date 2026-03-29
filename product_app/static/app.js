import { initAuth, onAuthChange, logout } from "./js/auth.js";
import { fetchJson, t, escapeHtml, showToast } from "./js/utils.js";

const PAGE    = window.__QUIEN_PAGE__    || {};
const ACCOUNT = window.__QUIEN_ACCOUNT__ || {};
const isAdmin = !!ACCOUNT.is_admin;

/* ── Section registries ─────────────────────────────────────────── */
const OWNER_SECTIONS = [
  "dashboard", "getting-started", "how-it-works",
  "agent-factory", "api", "account", "billing", "admin",
];
const USER_SECTIONS = ["dashboard", "components", "api", "account", "billing"];
const SECTIONS = isAdmin ? OWNER_SECTIONS : USER_SECTIONS;

/* ── Module loader map ──────────────────────────────────────────── */
const MODULE_MAP = {
  "dashboard":       () => import("./dashboard.js"),
  "getting-started": () => import("./getting-started.js"),
  "how-it-works":    () => import("./how-it-works.js"),
  "agent-factory":   null,   // coming soon — rendered inline
  "components":      () => import("./getting-started.js"),
  "api":             () => import("./api-section.js"),
  "account":         () => import("./account.js"),
  "billing":         () => import("./billing.js"),
  "admin":           () => import("./admin.js"),
};

/* ── Module cache ───────────────────────────────────────────────── */
const _modCache = {};

/* ── Shared context passed to every module ──────────────────────── */
const ctx = { PAGE, ACCOUNT, isAdmin, fetchJson, t, escapeHtml, showToast };

/* ── Section switcher ───────────────────────────────────────────── */
async function switchSection(sectionId) {
  if (!sectionId) sectionId = SECTIONS[0];

  // Validate section is available for current role
  if (!SECTIONS.includes(sectionId)) {
    console.warn(`Section "${sectionId}" not available for current role.`);
    sectionId = SECTIONS[0];
  }

  // Hide all sections, update nav active states
  document.querySelectorAll(".workspace-section").forEach((el) => {
    el.hidden = true;
    el.classList.remove("is-active");
  });
  document.querySelectorAll(".ws-nav-item").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.section === sectionId);
  });

  // Show target section
  const target = document.getElementById(`ws-section-${sectionId}`);
  if (!target) {
    console.error(`Section element #ws-section-${sectionId} not found.`);
    return;
  }
  target.hidden = false;
  target.classList.add("is-active");

  // Agent Factory coming-soon placeholder (no module)
  if (sectionId === "agent-factory") {
    target.innerHTML = `
      <div class="af-coming-soon">
        <div class="af-coming-soon-icon">🤖</div>
        <div class="af-coming-soon-title">${t("Agent Factory", "Fábrica de Agentes")}</div>
        <div class="af-coming-soon-text">${t(
          "Create agents interactively without code. Coming soon.",
          "Crea agentes interactivamente sin código. Próximamente."
        )}</div>
      </div>`;
    return;
  }

  // Lazy-load section module with caching
  const loader = MODULE_MAP[sectionId];
  if (!loader) return;

  try {
    if (!_modCache[sectionId]) {
      _modCache[sectionId] = await loader();
    }
    const mod = _modCache[sectionId];
    if (typeof mod.load === "function") {
      await mod.load(target, ctx);
    }
  } catch (err) {
    console.error(`Failed to load section module "${sectionId}":`, err);
    target.innerHTML = `<p class="muted-copy" style="color:var(--accent-red);">${
      t("Failed to load section.", "Error al cargar la sección.")
    }</p>`;
  }
}

/* ── Hash routing ───────────────────────────────────────────────── */
function handleHashChange() {
  const hash = window.location.hash.replace("#", "") || SECTIONS[0];
  switchSection(hash);
}

/* ── Product name ───────────────────────────────────────────────── */
function setProductName() {
  const el = document.getElementById("ws-product-name");
  if (el && PAGE.productName) el.textContent = PAGE.productName;
}

/* ── Mobile hamburger ───────────────────────────────────────────── */
function initHamburger() {
  const btn     = document.getElementById("hamburger-toggle");
  const sidebar = document.querySelector(".workspace-sidebar");
  if (!btn || !sidebar) return;

  btn.addEventListener("click", () => {
    sidebar.classList.toggle("is-open");
    btn.classList.toggle("is-active");
  });

  sidebar.querySelectorAll(".ws-nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      sidebar.classList.remove("is-open");
      btn.classList.remove("is-active");
    });
  });
}

/* ── Workspace boot ─────────────────────────────────────────────── */
async function boot() {
  const isWorkspace = !!document.querySelector(".workspace-shell");

  if (!isWorkspace) {
    bootLanding();
    return;
  }

  await initAuth();

  setProductName();
  initHamburger();

  // Nav click handlers
  document.querySelectorAll(".ws-nav-item[data-section]").forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const section = item.dataset.section;
      window.location.hash = section;
      switchSection(section);
    });
  });

  // Logout button
  const logoutBtn = document.getElementById("workspace-logout-button");
  if (logoutBtn) logoutBtn.addEventListener("click", () => logout());

  // Hash-based routing
  window.addEventListener("hashchange", handleHashChange);

  // Load first section
  const initialHash = window.location.hash.replace("#", "") || SECTIONS[0];
  switchSection(initialHash);
}

/* ── Landing page boot ──────────────────────────────────────────── */
function bootLanding() {
  initAuth();

  onAuthChange((user) => {
    if (user) window.location.reload();
  });
}

/* ── Entry point ────────────────────────────────────────────────── */
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
