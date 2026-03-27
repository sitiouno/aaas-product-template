import { escapeHtml } from "./utils.js";

const CATEGORIES = ["All", "People", "Companies", "Red Flags", "Evidence", "Locations"];

const ENTITY_BORDER = {
  person: "#34d399",
  company: "#fbbf24",
  address: "#818cf8",
  domain: "#38bdf8",
  political: "#fbbf24",
};

const SEVERITY_ICON = { high: "\u{1f6a9}", medium: "\u26a0\ufe0f", low: "\u2139\ufe0f" };
const SEVERITY_BORDER = { high: "#f87171", medium: "#fbbf24", low: "#38bdf8" };

const CONN_COLOR = { family: "#34d399", business: "#fbbf24", financial: "#38bdf8", suspicious: "#f87171" };

const BASE_CARD = `background:#12121e;border-radius:10px;padding:12px;cursor:pointer;
  position:relative;transition:box-shadow .2s;border:2px solid`;

const RESPONSIVE_STYLE_ID = "evidence-board-responsive";

function ensureResponsiveStyle() {
  if (document.getElementById(RESPONSIVE_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = RESPONSIVE_STYLE_ID;
  style.textContent = `@media(max-width:480px){.eb-grid{grid-template-columns:1fr!important;}}`;
  document.head.appendChild(style);
}

function photoHtml(url, border, size = 50) {
  if (url) {
    return `<img src="${escapeHtml(url)}" style="width:${size}px;height:${size}px;
      border-radius:50%;object-fit:cover;border:2px solid ${border};flex-shrink:0;" />`;
  }
  return `<div style="width:${size}px;height:${size}px;border-radius:50%;
    background:#1e1e2e;border:2px solid ${border};display:flex;align-items:center;
    justify-content:center;font-size:${size * 0.5}px;flex-shrink:0;">\u{1f464}</div>`;
}

function pinDot(color) {
  return `<span style="position:absolute;top:6px;right:6px;width:8px;height:8px;
    border-radius:50%;background:${color};box-shadow:0 0 4px ${color};"></span>`;
}

function riskColor(score) {
  if (score >= 70) return "#f87171";
  if (score >= 40) return "#fbbf24";
  return "#34d399";
}

function matchCategory(filter, item) {
  if (filter === "All") return true;
  const cat = (item.category || item.type || "").toLowerCase();
  const map = {
    people: ["person", "people"],
    companies: ["company", "companies", "business"],
    "red flags": ["red flag", "red flags", "suspicious", "high"],
    evidence: ["evidence", "medium", "low"],
    locations: ["address", "location", "locations"],
  };
  const terms = map[filter.toLowerCase()] || [];
  return terms.some((t) => cat.includes(t));
}

function renderFilterBar(container, onFilter) {
  const bar = document.createElement("div");
  bar.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;";
  CATEGORIES.forEach((cat) => {
    const pill = document.createElement("button");
    pill.textContent = cat;
    pill.dataset.cat = cat;
    pill.style.cssText = `border:none;padding:6px 14px;border-radius:20px;font-size:13px;
      cursor:pointer;font-weight:600;transition:background .15s,color .15s;`;
    if (cat === "All") {
      pill.style.background = "#22d3ee";
      pill.style.color = "#0a0a14";
    } else {
      pill.style.background = "#1e1e2e";
      pill.style.color = "#94a3b8";
    }
    pill.addEventListener("click", () => {
      bar.querySelectorAll("button").forEach((b) => {
        b.style.background = "#1e1e2e";
        b.style.color = "#94a3b8";
      });
      pill.style.background = "#22d3ee";
      pill.style.color = "#0a0a14";
      onFilter(cat);
    });
    bar.appendChild(pill);
  });
  container.appendChild(bar);
}

function buildSubjectCard(subject) {
  const border = "#f87171";
  const photo = subject.photo_urls?.length ? subject.photo_urls[0] : null;
  const rc = riskColor(subject.risk_score || 0);
  return `<div class="eb-card eb-subject" data-id="subject" data-category="people"
    style="${BASE_CARD} ${border};text-align:center;min-width:200px;">
    ${pinDot(border)}
    <div style="display:flex;flex-direction:column;align-items:center;gap:8px;">
      ${photoHtml(photo, border, 64)}
      <h3 style="margin:0;color:#e8eaf0;font-size:15px;">${escapeHtml(subject.name)}</h3>
      <span style="color:#94a3b8;font-size:12px;">${escapeHtml(subject.role || "")}</span>
      <span style="background:${rc}22;color:${rc};padding:2px 10px;border-radius:12px;
        font-size:12px;font-weight:700;">Risk ${subject.risk_score ?? "N/A"}</span>
    </div>
  </div>`;
}

function buildEntityCard(entity) {
  const border = ENTITY_BORDER[entity.type] || "#94a3b8";
  return `<div class="eb-card" data-id="${escapeHtml(entity.id)}" data-category="${escapeHtml(entity.type)}"
    style="${BASE_CARD} ${border};">
    ${pinDot(border)}
    <div style="display:flex;gap:10px;align-items:center;">
      ${photoHtml(entity.photo_url, border)}
      <div style="overflow:hidden;">
        <p style="margin:0;color:#e8eaf0;font-size:14px;font-weight:600;white-space:nowrap;
          overflow:hidden;text-overflow:ellipsis;">${escapeHtml(entity.name)}</p>
        <span style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.5px;">
          ${escapeHtml(entity.type)}</span>
      </div>
    </div>
    <p class="eb-details" style="margin:6px 0 0;color:#94a3b8;font-size:12px;line-height:1.4;
      display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
      ${escapeHtml(entity.details || "")}</p>
  </div>`;
}

function buildEvidenceCard(ev) {
  const icon = SEVERITY_ICON[ev.severity] || "\u2139\ufe0f";
  const border = SEVERITY_BORDER[ev.severity] || "#38bdf8";
  return `<div class="eb-card" data-id="${escapeHtml(ev.id)}" data-category="${escapeHtml(ev.category || ev.severity)}"
    style="${BASE_CARD} ${border};">
    ${pinDot(border)}
    <div style="display:flex;gap:8px;align-items:center;">
      <span style="font-size:22px;flex-shrink:0;">${icon}</span>
      <p style="margin:0;color:#e8eaf0;font-size:14px;font-weight:600;">${escapeHtml(ev.title)}</p>
    </div>
    <span style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.5px;">
      ${escapeHtml(ev.category || "")}</span>
    <p class="eb-details" style="margin:4px 0 0;color:#94a3b8;font-size:12px;line-height:1.4;
      display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
      ${escapeHtml(ev.details || "")}</p>
  </div>`;
}

function buildConnectionsList(connections) {
  if (!connections?.length) return "";
  const rows = connections
    .map((c) => {
      const color = CONN_COLOR[c.type] || "#94a3b8";
      return `<div style="display:flex;gap:8px;align-items:center;padding:6px 0;
        border-bottom:1px solid #1e1e2e;font-size:13px;">
        <span style="color:#e8eaf0;font-weight:600;">${escapeHtml(c.source)}</span>
        <span style="color:#94a3b8;">\u2192</span>
        <span style="color:#e8eaf0;font-weight:600;">${escapeHtml(c.target)}</span>
        <span style="color:#94a3b8;">|</span>
        <span style="color:${color};">${escapeHtml(c.label)}</span>
        <span style="color:#94a3b8;">|</span>
        <span style="color:${color};font-size:11px;text-transform:uppercase;">${escapeHtml(c.type)}</span>
      </div>`;
    })
    .join("");
  return `<div style="margin-top:20px;">
    <h3 style="color:#e8eaf0;font-size:14px;margin:0 0 8px;">Connections</h3>${rows}</div>`;
}

function handleCardClick(container, boardData) {
  container.addEventListener("click", (e) => {
    const card = e.target.closest(".eb-card");
    if (!card) return;
    const id = card.dataset.id;

    // Toggle inline expansion
    const existing = card.querySelector(".eb-expanded");
    if (existing) {
      existing.remove();
      card.style.boxShadow = "";
      container.querySelectorAll(".eb-card").forEach((c) => (c.style.boxShadow = ""));
      return;
    }

    // Collapse any other expansion
    container.querySelectorAll(".eb-expanded").forEach((el) => el.remove());
    container.querySelectorAll(".eb-card").forEach((c) => (c.style.boxShadow = ""));

    // Find related connections
    const related = (boardData.connections || []).filter(
      (c) => c.source === id || c.target === id
    );
    const relatedIds = new Set();
    related.forEach((c) => { relatedIds.add(c.source); relatedIds.add(c.target); });

    // Glow related cards
    container.querySelectorAll(".eb-card").forEach((c) => {
      if (relatedIds.has(c.dataset.id)) {
        c.style.boxShadow = "0 0 12px #22d3ee88";
      }
    });
    card.style.boxShadow = "0 0 16px #22d3eecc";

    // Build expansion panel
    const panel = document.createElement("div");
    panel.className = "eb-expanded";
    panel.style.cssText = `margin-top:10px;padding:10px;background:#1a1a2e;border-radius:8px;
      font-size:12px;color:#e8eaf0;line-height:1.5;animation:ebSlide .2s ease;`;

    // Find full item details
    let item = null;
    if (id === "subject") item = boardData.subject;
    else item = (boardData.entities || []).find((en) => en.id === id)
      || (boardData.evidence || []).find((ev) => ev.id === id);

    let html = item
      ? `<p style="margin:0 0 6px;color:#94a3b8;">${escapeHtml(item.details || item.role || "")}</p>`
      : "";

    if (related.length) {
      html += `<p style="margin:8px 0 4px;font-weight:600;color:#22d3ee;">Related connections:</p>`;
      related.forEach((c) => {
        const color = CONN_COLOR[c.type] || "#94a3b8";
        html += `<p style="margin:2px 0;color:${color};">${escapeHtml(c.source)} \u2192 ${escapeHtml(c.target)} \u2014 ${escapeHtml(c.label)}</p>`;
      });
    }
    panel.innerHTML = html;
    card.appendChild(panel);
  });
}

export function initEvidenceBoard(containerId, boardData) {
  const container = document.getElementById(containerId);
  if (!container) return;

  ensureResponsiveStyle();
  container.innerHTML = "";
  container.style.cssText = "font-family:inherit;";

  // Inject slide animation
  if (!document.getElementById("eb-keyframes")) {
    const kf = document.createElement("style");
    kf.id = "eb-keyframes";
    kf.textContent = `@keyframes ebSlide{from{opacity:0;max-height:0}to{opacity:1;max-height:400px}}`;
    document.head.appendChild(kf);
  }

  let activeFilter = "All";

  const grid = document.createElement("div");
  grid.className = "eb-grid";
  grid.style.cssText = `display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
    gap:12px;`;

  function renderGrid(filter) {
    activeFilter = filter;
    let html = "";

    // Subject card always visible for "All" or "People"
    if (filter === "All" || filter === "People") {
      html += buildSubjectCard(boardData.subject || {});
    }

    (boardData.entities || []).forEach((entity) => {
      if (matchCategory(filter, entity)) html += buildEntityCard(entity);
    });

    (boardData.evidence || []).forEach((ev) => {
      if (matchCategory(filter, ev)) html += buildEvidenceCard(ev);
    });

    grid.innerHTML = html;
  }

  renderFilterBar(container, renderGrid);
  renderGrid("All");
  container.appendChild(grid);

  // Connections section
  const connDiv = document.createElement("div");
  connDiv.innerHTML = buildConnectionsList(boardData.connections);
  container.appendChild(connDiv);

  // Card click interaction
  handleCardClick(container, boardData);
}

export function destroyEvidenceBoard(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  // Replace node to strip all event listeners
  const clone = container.cloneNode(false);
  container.parentNode.replaceChild(clone, container);
  clone.innerHTML = "";
}
