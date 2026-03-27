export const pageState = window.__QUIEN_PAGE__ || {};
export const language = pageState.language || "en";
export const workspaceAccount = window.__QUIEN_ACCOUNT__ || null;

export function t(en, es) {
  return language === "es" ? es : en;
}

export function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function humanStatus(status) {
  return {
    idle: t("Ready", "Listo"),
    queued: t("Queued", "En cola"),
    running: t("Running", "En curso"),
    completed: t("Completed", "Completado"),
    failed: t("Failed", "Fallido"),
  }[status] || t("Ready", "Listo");
}

export function notify(message) {
  window.alert(message);
}

/** Show a non-blocking toast notification that auto-dismisses. */
export function showToast(message, { tone = "info", duration = 5000, html = false, persist = false } = {}) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `toast toast-${tone}`;
  if (html) toast.innerHTML = message;
  else toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("toast-visible"));
  if (!persist) {
    setTimeout(() => dismissToast(toast), duration);
  }
  return toast;
}

export function dismissToast(toast) {
  if (!toast) return;
  toast.classList.remove("toast-visible");
  toast.addEventListener("transitionend", () => toast.remove(), { once: true });
  setTimeout(() => toast.remove(), 400); // fallback
}

export function setFeedback(element, tone, message) {
  if (!element) return;
  if (!message) {
    element.hidden = true;
    element.textContent = "";
    element.removeAttribute("data-tone");
    return;
  }
  element.hidden = false;
  element.setAttribute("data-tone", tone || "info");
  element.textContent = message;
}

export async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { detail: text };
  }
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || text || response.statusText);
  }
  return payload;
}
export function el(selector) {
  return document.querySelector(selector);
}

export function els(selector) {
  return Array.from(document.querySelectorAll(selector));
}

export async function setupFetch(url, options = {}) {
  return fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
}

export const STYLE_LABELS = {
  deploy_product: { en: "VC Due Diligence", es: "Due Diligence VC" },
  market_intelligence: { en: "Market Intelligence", es: "Inteligencia de Mercado" },
  world_news_briefing: { en: "World News Briefing", es: "Briefing de Noticias" },
  company_deep_dive: { en: "Company Deep Dive", es: "Analisis de Empresa" },
  industry_analysis: { en: "Industry Analysis", es: "Analisis de Industria" },
  osint_360: { en: "OSINT 360 Investigation", es: "Investigacion OSINT 360" },
};

export function styleLabel(key) {
  const entry = STYLE_LABELS[key];
  return entry ? (language === "es" ? entry.es : entry.en) : key;
}
