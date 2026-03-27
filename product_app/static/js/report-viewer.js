import { escapeHtml, t, styleLabel } from "./utils.js";

/**
 * Report viewer utilities for OSINT 360 reports.
 *
 * These helpers are consumed by app.js to render the executive summary,
 * photo row, and section cards inside the hardcoded report-viewer HTML
 * defined in site_renderer.py.  Tab switching and lazy init of the graph
 * and evidence board live in app.js.
 */

/* ── Executive summary badge row ──────────────────────────────────── */

function _badge(label, value, color) {
  return `<span class="exec-badge" style="background:${color}15;color:${color};border:1px solid ${color}40;padding:4px 10px;border-radius:6px;font-weight:600;font-size:0.85rem;">${escapeHtml(label)}: ${escapeHtml(String(value))}</span>`;
}

/**
 * Parse OSINT snapshot and render an executive summary card into `container`.
 */
export function renderExecutiveSummary(container, snapshot) {
  if (!container) return;
  const sections = snapshot.sections || [];

  const riskSection = sections.find((s) => s.id === "risk_profile");
  const riskText = riskSection ? riskSection.text || "" : "";
  // Match: "Risk Score: 65", "risk score 65/100", "Score (1-100): 65", "Overall: 72"
  const scoreMatch = riskText.match(/(?:risk\s*score|overall)[^0-9]*(\d{1,3})/i)
    || riskText.match(/(\d{1,3})\s*\/\s*100/i);
  const riskScore = scoreMatch ? parseInt(scoreMatch[1], 10) : null;

  const flagSection = sections.find((s) => s.id === "red_flags");
  const flagText = flagSection ? flagSection.text || "" : "";
  // Count red flags by severity keywords or numbered items
  const severityHits = (flagText.match(/\b(HIGH|CRITICAL|SEVERE)\b/gi) || []).length;
  const numberedFlags = (flagText.match(/^\s*[-*]\s+\*?\*?(?:RF|Red Flag|Flag)\b/gim) || []).length;
  const flagCount = Math.max(severityHits, numberedFlags);

  const pepSection = sections.find((s) => s.id === "pep_screening");
  const pepText = pepSection ? pepSection.text || "" : "";
  // Match: "PEP Status: YES", "**PEP**: NO", "PEP Classification: INCONCLUSIVE", "NOT a PEP"
  const pepMatch = pepText.match(/PEP[^:]*:\s*(YES|NO|INCONCLUSIVE)/i)
    || pepText.match(/\b(NOT)\s+(?:a\s+)?PEP\b/i);
  const pepStatus = pepMatch
    ? (pepMatch[1].toUpperCase() === "NOT" ? "NO" : pepMatch[1].toUpperCase())
    : (pepSection ? "NO" : "N/A");

  const riskClass = riskScore >= 70 ? "risk-high" : riskScore >= 40 ? "risk-medium" : "risk-low";

  container.innerHTML = `
    <div class="rv-summary-grid">
      <div class="rv-summary-item">
        <span class="rv-summary-label">${escapeHtml(t("Risk Score", "Puntaje de Riesgo"))}</span>
        <span class="rv-summary-value ${riskClass}">${riskScore !== null ? riskScore + "/100" : "N/A"}</span>
      </div>
      <div class="rv-summary-item">
        <span class="rv-summary-label">${escapeHtml(t("Red Flags", "Alertas"))}</span>
        <span class="rv-summary-value ${flagCount > 0 ? "risk-high" : ""}">${flagCount} ${escapeHtml(t("detected", "detectadas"))}</span>
      </div>
      <div class="rv-summary-item">
        <span class="rv-summary-label">${escapeHtml(t("PEP Status", "Estado PEP"))}</span>
        <span class="rv-summary-value ${pepStatus === "YES" ? "risk-high" : ""}">${escapeHtml(pepStatus)}</span>
      </div>
      <div class="rv-summary-item">
        <span class="rv-summary-label">${escapeHtml(t("Data Sources", "Fuentes de Datos"))}</span>
        <span class="rv-summary-value">${sections.length} ${escapeHtml(t("sections", "secciones"))}</span>
      </div>
    </div>`;
}

/* ── Photo row from collected images ──────────────────────────────── */

/**
 * Render a row of collected photo thumbnails for the OSINT subject.
 */
export function renderPhotoRow(container, snapshot) {
  if (!container) return;
  const photoSection = (snapshot.sections || []).find((s) => s.id === "photo_collection");
  if (!photoSection) { container.innerHTML = ""; return; }

  const artifacts = snapshot.artifacts || [];
  const photoArtifacts = artifacts.filter((a) =>
    a.kind === "image" && a.name && /\.(jpg|jpeg|png|webp)$/i.test(a.name)
  );
  if (!photoArtifacts.length) {
    container.innerHTML = `<span style="color:var(--text-secondary);font-size:0.85rem;font-style:italic;">${escapeHtml(t("No photos could be collected for this subject.", "No se encontraron fotos para este sujeto."))}</span>`;
    return;
  }

  container.innerHTML = photoArtifacts.slice(0, 5).map((a) =>
    `<img class="rv-photo-thumb" src="${escapeHtml(a.url)}" alt="${escapeHtml(a.name)}" loading="lazy" onerror="this.style.display='none'">`
  ).join("") + `<span style="color:var(--text-secondary);font-size:0.8rem;">${photoArtifacts.length} ${escapeHtml(t("photos collected", "fotos recolectadas"))}</span>`;
}

/* ── Parse JSON from a section's text field ───────────────────────── */

/**
 * Extract a JSON object from a section's text (agents may embed JSON in prose).
 * Returns null if not found or not valid JSON.
 */
export function extractSectionJson(sections, sectionId) {
  const section = (sections || []).find((s) => s.id === sectionId);
  if (!section) return null;
  try {
    const text = section.text || "";
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) : null;
  } catch {
    return null;
  }
}
