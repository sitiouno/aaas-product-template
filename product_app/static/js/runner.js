/**
 * Run management — submission, monitoring, history.
 */

import { setupFetch } from "./utils.js";
import { renderSnapshot } from "./renderers.js";

let currentRunId = null;
let eventSource = null;
let pollInterval = null;
let runStateElements = {};
let _runCallback = null;

export function initRunState(elements) {
  runStateElements = elements;
}

/** Fetch recent runs with optional filters. */
export async function fetchHistory(limit = 25, filters = {}) {
  try {
    const params = new URLSearchParams({ limit: String(limit) });
    if (filters.research_style) params.set("research_style", filters.research_style);
    if (filters.status) params.set("status", filters.status);
    if (filters.q) params.set("q", filters.q);
    const res = await setupFetch(`/api/v1/runs?${params.toString()}`);
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      console.error(`[fetchHistory] ${res.status} ${res.statusText}:`, errText);
      return { runs: [], _error: `${res.status}: ${errText}` };
    }
    return res.json();
  } catch (e) {
    console.error("[fetchHistory] exception:", e);
    return { runs: [], _error: e.message };
  }
}

/** Fetch account info. */
export async function fetchAccount() {
  try {
    const res = await setupFetch("/api/v1/account");
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** Start a new research run. */
export async function startNewRun({ prompt, research_style, language, webhook_url }) {
  const body = { prompt, research_style, language };
  if (webhook_url) body.webhook_url = webhook_url;

  const res = await setupFetch("/api/v1/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to start run");
  }
  const data = await res.json();
  startMonitoring(data.job_id);
  return data;
}

/** Monitor an existing run via SSE (only for active in-memory runs). */
export function startMonitoring(runId) {
  stopMonitoring();
  currentRunId = runId;
  eventSource = new EventSource(`/api/v1/runs/${encodeURIComponent(runId)}/stream`);

  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      const snapshot = payload?.snapshot || payload;
      if (_runCallback) _runCallback(payload);
      renderSnapshot(runStateElements, snapshot);
      if (["completed", "failed"].includes(snapshot.status)) {
        stopMonitoring();
      }
    } catch (e) {
      console.error("SSE parse error:", e);
    }
  };

  eventSource.onerror = () => {
    stopMonitoring();
    // Fallback: load snapshot via GET
    _loadSnapshotOnce(runId);
  };
}

/** Load a run snapshot via GET and render it. */
async function _loadSnapshotOnce(runId) {
  try {
    const res = await setupFetch(`/api/v1/runs/${encodeURIComponent(runId)}`);
    if (res.ok) {
      const snapshot = await res.json();
      if (_runCallback) _runCallback({ type: "snapshot", snapshot });
      renderSnapshot(runStateElements, snapshot);
    }
  } catch (e) {
    console.error("Load snapshot error:", e);
  }
}

/** Stop monitoring. */
export function stopMonitoring() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

/** Resume or view an existing run — tries GET first, then SSE if still active. */
export async function resumeRun(runId) {
  stopMonitoring();
  currentRunId = runId;
  // Always load snapshot via GET first (works for both completed and active runs)
  try {
    const res = await setupFetch(`/api/v1/runs/${encodeURIComponent(runId)}`);
    if (res.ok) {
      const snapshot = await res.json();
      if (_runCallback) _runCallback({ type: "snapshot", snapshot });
      renderSnapshot(runStateElements, snapshot);
      // If still active, start SSE for live updates
      if (["queued", "running"].includes(snapshot.status)) {
        startMonitoring(runId);
      }
      return;
    }
  } catch (e) {
    console.error("Resume run error:", e);
  }
  // Fallback: try SSE directly
  startMonitoring(runId);
}

/** Subscribe to run events with a callback. */
export function subscribeRunEvents(callback) {
  if (typeof callback === "function") {
    _runCallback = callback;
  } else {
    // Legacy: passed elements object
    initRunState(callback);
  }
}
