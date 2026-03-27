import { escapeHtml } from "./utils.js";

/* ------------------------------------------------------------------ */
/*  State held in closure — no globals                                 */
/* ------------------------------------------------------------------ */

let _cy = null;
let _container = null;
let _onNodeSelect = null;

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const NODE_ICONS = {
  person: "\u{1F464}",
  company: "\u{1F3E2}",
  address: "\u{1F4CD}",
  domain: "\u{1F310}",
  political: "\u{1F3DB}\uFE0F",
};

const NODE_SHAPES = {
  person: "ellipse",
  company: "diamond",
  address: "rectangle",
  domain: "hexagon",
  political: "pentagon",
};

const RISK_COLORS = {
  high: "#f87171",
  medium: "#fbbf24",
  low: "#34d399",
  none: "#64748b",
  unknown: "#64748b",
};

const THEME = {
  bg: "#0a0a12",
  surface: "#12121e",
  text: "#e8eaf0",
  textMuted: "#94a3b8",
  border: "rgba(255,255,255,0.06)",
  accent: "#38bdf8",
  purple: "#818cf8",
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function riskColor(risk) {
  return RISK_COLORS[risk] || RISK_COLORS.unknown;
}

function nodeShape(type) {
  return NODE_SHAPES[type] || "ellipse";
}

function nodeIcon(type) {
  return NODE_ICONS[type] || "";
}

function edgeStyle(strength) {
  if (strength === "strong") return { width: 2, style: "solid", color: THEME.textMuted };
  if (strength === "weak") return { width: 1, style: "solid", color: THEME.textMuted };
  if (strength === "inferred" || strength === "suspicious") {
    return { width: 1.5, style: "dashed", color: RISK_COLORS.high };
  }
  return { width: 1, style: "solid", color: THEME.textMuted };
}

function parseToCytoscapeElements(graphData) {
  const nodes = (graphData.nodes || []).map((n) => ({
    data: {
      id: String(n.id),
      label: n.label || n.id,
      type: n.type || "unknown",
      risk: n.risk || "unknown",
      details: n.details || "",
      icon: nodeIcon(n.type),
      isSubject: n.id === (graphData.metadata?.subject_id),
    },
  }));

  const edges = (graphData.edges || []).map((e, idx) => ({
    data: {
      id: `e${idx}`,
      source: String(e.source),
      target: String(e.target),
      label: e.label || "",
      strength: e.strength || "weak",
    },
  }));

  return [...nodes, ...edges];
}

function buildStylesheet() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        shape: (el) => nodeShape(el.data("type")),
        "background-color": (el) => riskColor(el.data("risk")),
        width: (el) => (el.data("isSubject") ? 60 : Math.min(40 + el.degree() * 4, 80)),
        height: (el) => (el.data("isSubject") ? 60 : Math.min(40 + el.degree() * 4, 80)),
        "font-size": 11,
        color: THEME.text,
        "text-valign": "bottom",
        "text-margin-y": 6,
        "text-outline-width": 2,
        "text-outline-color": THEME.bg,
        "border-width": 2,
        "border-color": THEME.border,
        "overlay-opacity": 0,
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 3,
        "border-color": THEME.accent,
      },
    },
    {
      selector: "edge",
      style: {
        label: "data(label)",
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "target-arrow-color": (el) => edgeStyle(el.data("strength")).color,
        "line-color": (el) => edgeStyle(el.data("strength")).color,
        width: (el) => edgeStyle(el.data("strength")).width,
        "line-style": (el) => edgeStyle(el.data("strength")).style,
        "font-size": 9,
        color: THEME.textMuted,
        "text-rotation": "autorotate",
        "text-outline-width": 2,
        "text-outline-color": THEME.bg,
        "overlay-opacity": 0,
      },
    },
    {
      selector: "edge.highlighted",
      style: {
        "line-color": THEME.accent,
        "target-arrow-color": THEME.accent,
        width: 3,
      },
    },
  ];
}

const COSE_FALLBACK = { name: "cose", animate: true, nodeDimensionsIncludeLabels: true };
const COSE_BILKENT = { name: "cose-bilkent", animate: "end", nodeDimensionsIncludeLabels: true, idealEdgeLength: 120 };

function resolveLayout() {
  /* cytoscape-cose-bilkent may fail at runtime if cose-base is missing
     from the CDN bundle.  We detect + handle gracefully. */
  if (!window.cytoscape) return COSE_FALLBACK;
  try {
    const probe = window.cytoscape({ headless: true, elements: [{ data: { id: "a" } }] });
    const layout = probe.layout({ name: "cose-bilkent" });
    layout.stop();
    probe.destroy();
    return COSE_BILKENT;
  } catch {
    return COSE_FALLBACK;
  }
}

/* ------------------------------------------------------------------ */
/*  Core init                                                          */
/* ------------------------------------------------------------------ */

export function initGraphViewer(containerId, graphData, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) throw new Error(`Graph container #${containerId} not found`);
  if (!window.cytoscape) throw new Error("Cytoscape.js is not loaded");

  _container = container;
  _onNodeSelect = options.onNodeSelect || null;

  container.style.background = THEME.bg;
  container.style.position = "relative";
  container.style.width = container.style.width || "100%";
  container.style.height = container.style.height || "600px";

  const elements = parseToCytoscapeElements(graphData);

  _cy = window.cytoscape({
    container,
    elements,
    style: buildStylesheet(),
    layout: resolveLayout(),
    minZoom: 0.2,
    maxZoom: 5,
    wheelSensitivity: 0.3,
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
  });

  /* --- interactions ------------------------------------------------ */
  _cy.on("tap", "node", (evt) => {
    const node = evt.target;
    _cy.edges().removeClass("highlighted");
    node.connectedEdges().addClass("highlighted");
    if (_onNodeSelect) {
      _onNodeSelect({
        id: node.data("id"),
        label: node.data("label"),
        type: node.data("type"),
        risk: node.data("risk"),
        details: node.data("details"),
        connections: node.degree(),
      });
    }
  });

  _cy.on("tap", (evt) => {
    if (evt.target === _cy) {
      _cy.elements().unselect();
      _cy.edges().removeClass("highlighted");
    }
  });

  if (options.fullscreen) {
    toggleFullscreen(containerId);
  }

  return _cy;
}

/* ------------------------------------------------------------------ */
/*  Toolbar functions                                                   */
/* ------------------------------------------------------------------ */

export function fitGraph() {
  if (_cy) _cy.fit(undefined, 40);
}

export function searchNode(query) {
  if (!_cy || !query) return null;
  const q = query.toLowerCase();
  const match = _cy.nodes().filter((n) => n.data("label").toLowerCase().includes(q)).first();
  if (match && match.length) {
    _cy.animate({ center: { eles: match }, zoom: 2 }, { duration: 400 });
    match.select();
    match.connectedEdges().addClass("highlighted");
    return match.data();
  }
  return null;
}

export function exportPNG() {
  if (!_cy) return;
  const blob64 = _cy.png({ full: true, scale: 2, bg: THEME.bg });
  const link = document.createElement("a");
  link.href = blob64;
  link.download = "investigation-graph.png";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function toggleFullscreen(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!document.fullscreenElement) {
    el.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

export function destroyGraph() {
  if (_cy) {
    _cy.destroy();
    _cy = null;
  }
  _container = null;
  _onNodeSelect = null;
}

/* ------------------------------------------------------------------ */
/*  Toolbar renderer                                                   */
/* ------------------------------------------------------------------ */

export function renderGraphToolbar(toolbarId, graphInstance) {
  const toolbar = document.getElementById(toolbarId);
  if (!toolbar) return;

  const btnStyle = [
    `background:${THEME.surface}`,
    `color:${THEME.text}`,
    `border:1px solid ${THEME.border}`,
    "border-radius:6px",
    "padding:6px 14px",
    "cursor:pointer",
    "font-size:13px",
    "font-family:inherit",
  ].join(";");

  const inputStyle = [
    `background:${THEME.surface}`,
    `color:${THEME.text}`,
    `border:1px solid ${THEME.border}`,
    "border-radius:6px",
    "padding:6px 10px",
    "font-size:13px",
    "font-family:inherit",
    "outline:none",
    "min-width:160px",
  ].join(";");

  toolbar.style.cssText = [
    "display:flex",
    "gap:8px",
    "align-items:center",
    "flex-wrap:wrap",
    `background:${THEME.bg}`,
    "padding:8px 0",
  ].join(";");

  toolbar.innerHTML = `
    <input id="graph-search-input" type="text"
           placeholder="Search node\u2026" style="${inputStyle}" />
    <button id="graph-search-btn" style="${btnStyle}">Search</button>
    <button id="graph-fit-btn" style="${btnStyle}">Fit</button>
    <button id="graph-png-btn" style="${btnStyle}">PNG</button>
    <button id="graph-fs-btn" style="${btnStyle}">Fullscreen</button>
  `;

  const searchInput = toolbar.querySelector("#graph-search-input");
  const searchBtn = toolbar.querySelector("#graph-search-btn");
  const fitBtn = toolbar.querySelector("#graph-fit-btn");
  const pngBtn = toolbar.querySelector("#graph-png-btn");
  const fsBtn = toolbar.querySelector("#graph-fs-btn");

  searchBtn.addEventListener("click", () => {
    searchNode(searchInput.value.trim());
  });
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchNode(searchInput.value.trim());
  });
  fitBtn.addEventListener("click", () => fitGraph());
  pngBtn.addEventListener("click", () => exportPNG());
  fsBtn.addEventListener("click", () => {
    if (_container) toggleFullscreen(_container.id);
  });
}

/* ------------------------------------------------------------------ */
/*  Node detail panel                                                  */
/* ------------------------------------------------------------------ */

export function renderNodeDetails(panelId, nodeData) {
  const panel = document.getElementById(panelId);
  if (!panel) return;

  if (!nodeData) {
    panel.innerHTML = `<p style="color:${THEME.textMuted};font-size:13px;">
      Click a node to see details.
    </p>`;
    return;
  }

  const icon = nodeIcon(nodeData.type);
  const color = riskColor(nodeData.risk);
  const riskLabel = nodeData.risk || "unknown";

  panel.style.cssText = [
    `background:${THEME.surface}`,
    `border:1px solid ${THEME.border}`,
    "border-radius:10px",
    "padding:16px",
    `color:${THEME.text}`,
    "font-family:inherit",
  ].join(";");

  panel.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
      <span style="font-size:28px;">${icon}</span>
      <div>
        <h3 style="margin:0;font-size:16px;color:${THEME.text};">
          ${escapeHtml(nodeData.label)}
        </h3>
        <span style="font-size:12px;color:${THEME.textMuted};text-transform:capitalize;">
          ${escapeHtml(nodeData.type)}
        </span>
      </div>
    </div>
    <div style="display:flex;gap:12px;margin-bottom:12px;">
      <span style="
        display:inline-block;padding:3px 10px;border-radius:999px;
        font-size:12px;font-weight:600;color:#000;background:${color};
        text-transform:capitalize;
      ">${escapeHtml(riskLabel)}</span>
      <span style="font-size:12px;color:${THEME.textMuted};">
        ${nodeData.connections ?? 0} connection${nodeData.connections === 1 ? "" : "s"}
      </span>
    </div>
    ${
      nodeData.details
        ? `<p style="font-size:13px;color:${THEME.textMuted};line-height:1.5;margin:0;">
            ${escapeHtml(nodeData.details)}
           </p>`
        : ""
    }
  `;
}
