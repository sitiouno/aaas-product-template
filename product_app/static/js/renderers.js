import { escapeHtml, t, humanStatus, styleLabel } from "./utils.js";

/**
 * Make URLs in HTML content clickable. Only wraps URLs not already inside href="".
 */
export function makeUrlsClickable(html) {
  if (!html) return html;
  return html.replace(
    /(?<!=["'])(https?:\/\/[^\s<>"')\]]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
  );
}

export function renderStages(stageListElement, stages) {
  if (!stageListElement) return;
  if (!stages || !stages.length) {
    stageListElement.innerHTML = "";
    return;
  }
  stageListElement.innerHTML = stages
    .map(
      (stage) => `
        <article class="stage-card" data-status="${escapeHtml(stage.status)}">
          <span class="stage-dot" aria-hidden="true"></span>
          <div class="stage-copy">
            <h4>${escapeHtml(stage.title)}</h4>
            <p>${escapeHtml(stage.description)}</p>
          </div>
        </article>
      `
    )
    .join("");
}

export function renderSummary(summaryElement, snapshot) {
  if (!summaryElement) return;
  if (!snapshot.final_text) {
    summaryElement.classList.add("is-empty");
    summaryElement.innerHTML = `<p>${escapeHtml(
      t(
        "Run a preview to see the teaser and unlock a full report after signup.",
        "Ejecuta un preview para ver el teaser y desbloquea el informe completo al registrarte."
      )
    )}</p>`;
    return;
  }
  summaryElement.classList.remove("is-empty");
  summaryElement.innerHTML = `
    <p class="eyebrow">${escapeHtml(styleLabel(snapshot.research_style) || t("Research", "Investigacion"))}</p>
    <p>${escapeHtml(snapshot.final_text)}</p>
  `;
}

export function renderSections(resultsElement, sections, snapshotMode) {
  if (!resultsElement) return;
  resultsElement.innerHTML = (sections || [])
    .map(
      (section) => `
        <article class="result-card">
          <p class="eyebrow">${escapeHtml(styleLabel(snapshotMode) || "research")}</p>
          <h3>${escapeHtml(section.title)}</h3>
          <div class="result-html">${makeUrlsClickable(section.html || "")}</div>
        </article>
      `
    )
    .join("");
}

export function renderArtifacts(artifactElement, artifacts) {
  if (!artifactElement) return;
  if (!artifacts || !artifacts.length) {
    artifactElement.innerHTML = `<p class="muted-copy">${escapeHtml(t("Artifacts will appear here.", "Los artefactos apareceran aqui."))}</p>`;
    return;
  }
  artifactElement.innerHTML = artifacts
    .map(
      (artifact) => `
        <article class="artifact-card ws-artifact-card">
          <div>
            <p class="eyebrow">${escapeHtml(artifact.kind || "file")}</p>
            <h4>${escapeHtml(artifact.name)}</h4>
          </div>
          <a class="ghost-link" href="${artifact.url}" target="_blank" rel="noreferrer">
            ${escapeHtml(t("Open", "Abrir"))}
          </a>
        </article>
      `
    )
    .join("");
}

export function renderLogs(logElement, logs) {
  if (!logElement) return;
  if (!logs || !logs.length) {
    logElement.innerHTML = `<p class="muted-copy">${escapeHtml(t("No logs yet.", "Todavia no hay eventos."))}</p>`;
    return;
  }
  logElement.innerHTML = logs
    .map(
      (log) => `
        <article class="log-item">
          <div class="log-meta">
            <span>${escapeHtml(log.author || "system")}</span>
            <span>${escapeHtml(log.timestamp || "")}</span>
          </div>
          <p>${escapeHtml(log.message || "")}</p>
        </article>
      `
    )
    .join("");
}

export function renderSnapshot(elements, snapshot) {
  if (!snapshot) return;

  if (elements.statusPill) {
    elements.statusPill.textContent = humanStatus(snapshot.status);
    elements.statusPill.className = "pill";
    if (snapshot.status === "completed") elements.statusPill.classList.add("pill-green");
    else if (snapshot.status === "running") elements.statusPill.classList.add("pill-blue");
    else if (snapshot.status === "failed") elements.statusPill.classList.add("pill-red");
  }

  if (elements.progressFill) {
    elements.progressFill.style.width = `${snapshot.progress_percent || 0}%`;
  }

  const currentStage = (snapshot.stages || []).find((stage) => stage.id === snapshot.current_stage_id);

  if (elements.stageTitle) {
    elements.stageTitle.textContent = currentStage?.title ||
      (snapshot.status === "completed" ? t("Analysis completed", "Analisis completado") : t("Waiting for run", "Esperando corrida"));
  }

  if (elements.stageDescription) {
    elements.stageDescription.textContent = currentStage?.description || snapshot.error ||
      t("Execution logs will appear here.", "Asqui aparecera el log de ejecucion.");
  }

  if (elements.disableButtons) {
    const isBusy = ["queued", "running"].includes(snapshot.status);
    elements.disableButtons.forEach(btn => { if (btn) btn.disabled = isBusy; });
  }

  renderStages(elements.stageList, snapshot.stages);
  if (elements.summaryCard) renderSummary(elements.summaryCard, snapshot);
  renderSections(elements.resultsStack, snapshot.sections, snapshot.research_style);
  renderArtifacts(elements.artifactGrid, snapshot.artifacts);
  renderLogs(elements.logFeed, snapshot.logs);
}
