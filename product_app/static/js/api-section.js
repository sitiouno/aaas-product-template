/**
 * API Keys section — list keys, create, revoke, webhook URL config.
 * Exported: load(container, ctx)
 *
 * On load sets api-key:true in localStorage gs_progress (getting-started tracking).
 * Fetches: /api/v1/account, POST /api/v1/api-keys,
 *          DELETE /api/v1/api-keys/{id}, PATCH /api/v1/account
 */

function keyRowHtml(key, t, escapeHtml) {
  return `
    <div class="api-key-row">
      <div class="api-key-info">
        <span class="api-key-name">${escapeHtml(key.name)}</span>
        <span class="api-key-prefix">${escapeHtml(key.prefix)}••••••••</span>
      </div>
      <button class="ghost-button btn-revoke-apikey" data-id="${key.id}">${t("Revoke","Revocar")}</button>
    </div>`;
}

function wireRevokeButtons(container, ctx, reloadFn) {
  const { t } = ctx;
  container.querySelectorAll(".btn-revoke-apikey").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!window.confirm(t("Revoke this key?","Revocar esta key?"))) return;
      const id = btn.getAttribute("data-id");
      btn.disabled = true;
      try {
        const res = await fetch(`/api/v1/api-keys/${id}`, { method:"DELETE" });
        if (res.ok) { reloadFn(); }
        else { const d = await res.json().catch(()=>({})); alert(d.detail||"Error"); btn.disabled=false; }
      } catch(e) { alert("Error"); btn.disabled=false; }
    });
  });
}

async function refreshKeyList(keysArea, ctx, reloadFn) {
  const { t, escapeHtml } = ctx;
  try {
    const res = await fetch("/api/v1/account");
    if (!res.ok) return;
    const account = await res.json();
    if (!account?.api_keys) return;
    keysArea.querySelectorAll(".api-key-row").forEach(r => r.remove());
    keysArea.querySelector(".empty-state")?.remove();
    if (!account.api_keys.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.innerHTML = `<p>${t("No API keys yet.","Sin API keys aun.")}</p>`;
      keysArea.appendChild(empty);
    } else {
      account.api_keys.forEach(key => {
        const row = document.createElement("div");
        row.innerHTML = keyRowHtml(key, t, escapeHtml);
        keysArea.appendChild(row.firstElementChild);
      });
    }
    wireRevokeButtons(keysArea, ctx, reloadFn);
  } catch(e) { /* ignore */ }
}

export async function load(container, ctx) {
  const { t, escapeHtml } = ctx;

  // Mark getting-started step
  try {
    const prog = JSON.parse(localStorage.getItem("gs_progress") || "{}");
    prog["api-key"] = true;
    localStorage.setItem("gs_progress", JSON.stringify(prog));
  } catch(e) { /* ignore */ }

  container.innerHTML = `<p class="muted-copy">${t("Loading keys...","Cargando keys...")}</p>`;

  let account = null;
  try {
    const res = await fetch("/api/v1/account");
    if (res.ok) account = await res.json();
  } catch(e) { /* ignore */ }

  if (!account) {
    container.innerHTML = `<p class="muted-copy">${t("Could not load account data.","No se pudo cargar la cuenta.")}</p>`;
    return;
  }

  const keysHtml = account.api_keys?.length
    ? account.api_keys.map(k => keyRowHtml(k, t, escapeHtml)).join("")
    : `<div class="empty-state"><p>${t("No API keys yet. Create one to integrate via REST API or MCP.","Sin API keys. Crea una para integrar via REST API o MCP.")}</p></div>`;

  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
      <h3 style="margin:0;">${t("Your API Keys","Tus API Keys")}</h3>
      <button class="primary-button" id="btn-create-apikey">${t("+ Create Key","+ Crear Key")}</button>
    </div>
    <div id="new-key-result" class="key-result" style="display:none;"></div>
    <div id="api-keys-list">${keysHtml}</div>

    <div class="account-card" style="margin-top:2rem;">
      <h4>${t("Webhook URL","URL de Webhook")}</h4>
      <p class="muted-copy" style="margin-bottom:0.5rem;">
        ${t("Receive POST notifications when deployments complete.","Recibe notificaciones POST cuando los despliegues se completan.")}
      </p>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <input type="url" id="webhook-url-input" value="${escapeHtml(account.webhook_url||"")}"
          placeholder="https://your-server.com/webhook" class="otp-code-input"
          style="text-align:left;letter-spacing:normal;font-size:0.9rem;width:320px;max-width:100%;" />
        <button class="secondary-button" id="btn-save-webhook">${t("Save","Guardar")}</button>
      </div>
    </div>`;

  const keysList = container.querySelector("#api-keys-list");
  const reloadFn = () => load(container, ctx);

  wireRevokeButtons(keysList, ctx, reloadFn);

  // Create key
  const btnCreate = container.querySelector("#btn-create-apikey");
  btnCreate?.addEventListener("click", async () => {
    const name = window.prompt(t("Name for the API Key:","Nombre para la API Key:"));
    if (!name) return;
    btnCreate.disabled = true;
    try {
      const res = await fetch("/api/v1/api-keys", {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ name }),
      });
      const data = await res.json();
      if (res.ok) {
        const resDiv = container.querySelector("#new-key-result");
        if (resDiv) {
          resDiv.style.display = "block";
          resDiv.innerHTML = `
            <div class="key-created-banner">
              <p class="key-warning">${t("Save this key now — it will NOT be shown again!","Guarda esta key ahora — NO se mostrara de nuevo!")}</p>
              <div class="key-value-row">
                <span class="key-value" id="created-key-value">${escapeHtml(data.api_key)}</span>
                <button class="btn-copy-key" id="btn-copy-key">${t("Copy","Copiar")}</button>
              </div>
            </div>`;
          container.querySelector("#btn-copy-key")?.addEventListener("click", () => {
            navigator.clipboard.writeText(data.api_key).then(() => {
              const btn = container.querySelector("#btn-copy-key");
              if (btn) { btn.textContent = t("Copied!","Copiado!"); setTimeout(()=>{ btn.textContent=t("Copy","Copiar"); }, 2000); }
            }).catch(() => {
              const valEl = container.querySelector("#created-key-value");
              if (valEl) { const r=document.createRange(); r.selectNodeContents(valEl); const sel=window.getSelection(); sel.removeAllRanges(); sel.addRange(r); }
            });
          });
        }
        refreshKeyList(keysList, ctx, reloadFn);
      } else {
        alert(data.detail || "Error");
      }
    } catch(e) { alert("Error: "+e.message); }
    finally { btnCreate.disabled = false; }
  });

  // Save webhook URL
  container.querySelector("#btn-save-webhook")?.addEventListener("click", async () => {
    const url = container.querySelector("#webhook-url-input")?.value?.trim() || "";
    try {
      const res = await fetch("/api/v1/account", {
        method: "PATCH",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ webhook_url: url }),
      });
      if (res.ok) alert(t("Webhook URL saved!","URL de webhook guardada!")); else alert("Error saving webhook URL.");
    } catch(e) { alert("Error: "+e.message); }
  });
}
