/**
 * Account section — profile, stats, notifications, API key summary.
 * Exported: load(container, ctx)
 *
 * Fetches: /api/v1/account, PATCH /api/v1/account
 */

export async function load(container, ctx) {
  const { t, escapeHtml } = ctx;

  container.innerHTML = `<p class="muted-copy">${t("Loading...", "Cargando...")}</p>`;

  let account = null;
  try {
    const res = await fetch("/api/v1/account");
    if (res.ok) account = await res.json();
  } catch (e) { /* ignore */ }

  if (!account) {
    container.innerHTML = `<p class="muted-copy">${t("Could not load account.", "No se pudo cargar la cuenta.")}</p>`;
    return;
  }

  container.innerHTML = `
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
        <div class="detail-row">
          <span class="muted-copy">${t("Email", "Correo")}</span>
          <span>${escapeHtml(account.email || "")}</span>
        </div>
        <div class="detail-row">
          <span class="muted-copy">${t("Name", "Nombre")}</span>
          <span id="acc-name-display">${escapeHtml(account.full_name || "-")}</span>
          <button class="ghost-button" id="btn-edit-name" style="font-size:0.75rem;padding:2px 8px;">${t("Edit","Editar")}</button>
        </div>
        <div class="detail-row">
          <span class="muted-copy">${t("Role", "Rol")}</span>
          <span>${account.is_admin ? "Admin" : t("Member", "Miembro")}</span>
        </div>
      </div>

      <div class="account-card">
        <h4>${t("Language", "Idioma")}</h4>
        <div class="detail-row">
          <span class="muted-copy">${t("Interface language", "Idioma de interfaz")}</span>
          <select id="acc-lang-select" style="background:var(--bg-card);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;padding:4px 8px;">
            <option value="en" ${(account.language||"en")==="en"?"selected":""}>English</option>
            <option value="es" ${(account.language||"en")==="es"?"selected":""}>Español</option>
          </select>
        </div>
      </div>

      <div class="account-card">
        <h4>${t("Notifications", "Notificaciones")}</h4>
        <div class="detail-row">
          <span class="muted-copy">${t("Email when deployment is ready","Email cuando el despliegue este listo")}</span>
          <label class="toggle-switch">
            <input type="checkbox" id="toggle-email-notif" ${account.email_notifications !== false ? "checked" : ""}>
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>

      <div class="account-card">
        <h4>${t("API Keys", "API Keys")}</h4>
        ${account.api_keys?.length
          ? account.api_keys.map(k => `
              <div class="detail-row">
                <span>${escapeHtml(k.name)}</span>
                <span class="mono-cell">${escapeHtml(k.prefix)}••••</span>
              </div>`).join("")
          : `<p class="muted-copy">${t("No API keys.", "Sin API keys.")}</p>`}
        <a class="section-link" href="#api" style="margin-top:0.5rem;display:block;">${t("Manage keys","Gestionar keys")} &rarr;</a>
      </div>
    </div>`;

  // Edit name
  container.querySelector("#btn-edit-name")?.addEventListener("click", async () => {
    const newName = window.prompt(t("Enter your name:", "Ingresa tu nombre:"), account.full_name || "");
    if (newName === null) return;
    try {
      const res = await fetch("/api/v1/account", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: newName }),
      });
      if (res.ok) {
        load(container, ctx);
      } else {
        const data = await res.json().catch(() => ({}));
        alert(data.detail || "Error");
      }
    } catch (e) { alert("Error: " + e.message); }
  });

  // Language change
  container.querySelector("#acc-lang-select")?.addEventListener("change", async (e) => {
    try {
      await fetch("/api/v1/account", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: e.target.value }),
      });
      // Reload so UI reflects new language
      load(container, ctx);
    } catch (err) { /* ignore */ }
  });

  // Email notifications toggle
  container.querySelector("#toggle-email-notif")?.addEventListener("change", async (e) => {
    try {
      await fetch("/api/v1/account", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_notifications: e.target.checked }),
      });
    } catch (err) { e.target.checked = !e.target.checked; }
  });
}
