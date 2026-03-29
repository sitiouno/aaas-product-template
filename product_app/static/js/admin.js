/**
 * Admin section — access requests, user management, usage analytics, revenue.
 * Exported: load(container, ctx)
 *
 * Protected by UNLOCK_PROTECTED env flag. When locked, content is shown dimmed
 * with a warning overlay. When unlocked, full interactivity is available.
 */

function protectedWrapper(innerHtml, unlocked, t) {
  const badge = unlocked
    ? `<span class="protected-badge unlocked">&#128275; ${t("Unlocked", "Desbloqueado")}</span>`
    : `<span class="protected-badge locked">&#128274; ${t("Protected", "Protegido")}</span>`;
  const banner = unlocked
    ? `<div class="protected-banner unlocked">
         ${badge}
         <span>${t("Destructive operations enabled. Be careful.", "Operaciones destructivas habilitadas. Tenga cuidado.")}</span>
       </div>`
    : `<div class="protected-banner locked">
         ${badge}
         <span>${t("Read-only mode. Set UNLOCK_PROTECTED=true in .env to enable writes.", "Modo lectura. Establece UNLOCK_PROTECTED=true en .env para habilitar escrituras.")}</span>
       </div>`;
  return `<div class="protected-overlay ${unlocked ? "" : "is-locked"}">${banner}${innerHtml}</div>`;
}

async function loadRequests(area, ctx) {
  const { fetchJson, t, escapeHtml, showToast } = ctx;
  area.innerHTML = `<p class="muted-copy">${t("Loading access requests...", "Cargando solicitudes...")}</p>`;
  try {
    const res = await fetch("/api/v1/admin/access-requests?status=pending");
    if (!res.ok) { area.innerHTML = `<p style="color:var(--accent-red);">${t("Access denied.", "Acceso denegado.")}</p>`; return; }
    const data = await res.json();
    const requests = data.requests || [];
    if (!requests.length) { area.innerHTML = `<div class="empty-state"><p>${t("No pending access requests.", "Sin solicitudes pendientes.")}</p></div>`; return; }
    area.innerHTML = `
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr>
            <th>${t("Email","Email")}</th><th>${t("Name","Nombre")}</th><th>${t("Company","Empresa")}</th>
            <th>${t("Message","Mensaje")}</th><th>${t("Date","Fecha")}</th><th>${t("Actions","Acciones")}</th>
          </tr></thead>
          <tbody>${requests.map(r => `
            <tr>
              <td class="mono-cell">${escapeHtml(r.email)}</td>
              <td>${escapeHtml(r.full_name || "-")}</td>
              <td>${escapeHtml(r.company || "-")}</td>
              <td class="msg-cell" title="${escapeHtml(r.message||"")}">${escapeHtml((r.message||"").substring(0,50))}</td>
              <td>${r.created_at ? new Date(r.created_at).toLocaleDateString() : "-"}</td>
              <td class="action-cell">
                <button class="btn-approve" data-id="${r.id}">${t("Approve","Aprobar")}</button>
                <button class="btn-reject" data-id="${r.id}">${t("Reject","Rechazar")}</button>
              </td>
            </tr>`).join("")}</tbody>
        </table>
      </div>`;
    area.querySelectorAll(".btn-approve").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const credits = window.prompt(t("Initial credits to grant:","Creditos iniciales a otorgar:"), "10");
        if (!credits) return;
        btn.disabled = true;
        const r = await fetch(`/api/v1/admin/access-requests/${id}/approve`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ initial_credits: parseInt(credits,10) }) });
        if (r.ok) { loadRequests(area, ctx); } else { const e = await r.json().catch(()=>({})); alert(e.detail||"Error"); }
        btn.disabled = false;
      });
    });
    area.querySelectorAll(".btn-reject").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        if (!window.confirm(t("Reject this request?","Rechazar esta solicitud?"))) return;
        btn.disabled = true;
        await fetch(`/api/v1/admin/access-requests/${id}/reject`, { method:"POST" });
        loadRequests(area, ctx);
      });
    });
  } catch(e) { area.innerHTML = `<p style="color:var(--accent-red);">Error loading requests.</p>`; }
}

async function loadUsers(area, ctx) {
  const { t, escapeHtml } = ctx;
  area.innerHTML = `<p class="muted-copy">${t("Loading users...","Cargando usuarios...")}</p>`;
  try {
    const res = await fetch("/api/v1/admin/users");
    if (!res.ok) return;
    const { users = [] } = await res.json();
    area.innerHTML = `
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr>
            <th>${t("User","Usuario")}</th><th>${t("Status","Estado")}</th>
            <th>${t("Credits","Creditos")}</th><th>${t("Runs","Runs")}</th><th>${t("Actions","Acciones")}</th>
          </tr></thead>
          <tbody>${users.map(u => `
            <tr>
              <td><span style="font-weight:600;">${escapeHtml(u.email)}</span>
                ${u.is_owner ? '<span class="owner-badge">owner</span>' : u.is_admin ? '<span class="admin-badge">admin</span>' : ""}
              </td>
              <td><span class="pill pill-sm ${u.status==="approved"?"pill-green":u.status==="suspended"?"pill-red":"pill-amber"}">${u.status||"pending"}</span></td>
              <td style="font-weight:600;color:var(--accent-cyan);">${u.credits??0}</td>
              <td>${u.total_runs??0}</td>
              <td class="action-cell">
                <button class="btn-sm btn-grant" data-user-id="${u.id}" data-email="${escapeHtml(u.email)}">+ ${t("Credits","Creditos")}</button>
                ${u.is_owner ? "" : u.status==="suspended"
                  ? `<button class="btn-sm btn-reactivate" data-user-id="${u.id}">${t("Reactivate","Reactivar")}</button>`
                  : `<button class="btn-sm btn-suspend" data-user-id="${u.id}">${t("Suspend","Suspender")}</button>`}
                ${u.is_owner ? "" : `<button class="btn-sm btn-delete-user" data-user-id="${u.id}" data-email="${escapeHtml(u.email)}">${t("Delete","Eliminar")}</button>`}
              </td>
            </tr>`).join("")}</tbody>
        </table>
      </div>`;
    area.querySelectorAll(".btn-grant").forEach(btn => {
      btn.addEventListener("click", async () => {
        const userId = btn.getAttribute("data-user-id");
        const email = btn.getAttribute("data-email");
        const amountStr = window.prompt(t(`Credits to grant to ${email}:`,`Creditos a otorgar a ${email}:`));
        if (!amountStr) return;
        const amount = parseInt(amountStr, 10);
        if (isNaN(amount)||amount<=0) { alert(t("Invalid amount.","Monto invalido.")); return; }
        btn.disabled = true;
        const r = await fetch("/api/v1/admin/grant-credits", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ user_id: userId, amount }) });
        if (r.ok) loadUsers(area, ctx); else { const e = await r.json().catch(()=>({})); alert(e.detail||"Error"); }
        btn.disabled = false;
      });
    });
    area.querySelectorAll(".btn-suspend").forEach(btn => {
      btn.addEventListener("click", async () => {
        const userId = btn.getAttribute("data-user-id");
        if (!window.confirm(t("Suspend this user?","Suspender este usuario?"))) return;
        btn.disabled = true;
        const r = await fetch(`/api/v1/admin/users/${userId}/suspend`, { method:"POST" });
        if (r.ok) loadUsers(area, ctx); btn.disabled = false;
      });
    });
    area.querySelectorAll(".btn-reactivate").forEach(btn => {
      btn.addEventListener("click", async () => {
        const userId = btn.getAttribute("data-user-id");
        btn.disabled = true;
        const r = await fetch(`/api/v1/admin/users/${userId}/reactivate`, { method:"POST" });
        if (r.ok) loadUsers(area, ctx); btn.disabled = false;
      });
    });
    area.querySelectorAll(".btn-delete-user").forEach(btn => {
      btn.addEventListener("click", async () => {
        const userId = btn.getAttribute("data-user-id");
        const email = btn.getAttribute("data-email");
        if (!window.confirm(t(`Permanently delete ${email}?`,`Eliminar permanentemente a ${email}?`))) return;
        btn.disabled = true;
        const r = await fetch(`/api/v1/admin/users/${userId}`, { method:"DELETE" });
        if (r.ok) loadUsers(area, ctx); btn.disabled = false;
      });
    });
  } catch(e) { area.innerHTML = `<p>Error loading users.</p>`; }
}

async function loadUsage(area, ctx) {
  const { t, escapeHtml } = ctx;
  area.innerHTML = `<p class="muted-copy">${t("Loading platform usage...","Cargando uso de plataforma...")}</p>`;
  try {
    const res = await fetch("/api/v1/admin/users");
    if (!res.ok) return;
    const { users = [] } = await res.json();
    const totalCredits = users.reduce((s,u)=>s+(u.credits||0),0);
    const totalRuns = users.reduce((s,u)=>s+(u.total_runs||0),0);
    area.innerHTML = `
      <div class="dashboard-stats" style="margin-bottom:2rem;">
        <div class="stat-card stat-cyan"><span class="stat-value">${users.length}</span><p class="stat-label">${t("Total Users","Total Usuarios")}</p></div>
        <div class="stat-card stat-purple"><span class="stat-value">${totalRuns}</span><p class="stat-label">${t("Total Runs","Total Runs")}</p></div>
        <div class="stat-card stat-green"><span class="stat-value">${totalCredits}</span><p class="stat-label">${t("Credits Outstanding","Creditos Vigentes")}</p></div>
      </div>
      <h4>${t("Per-User Breakdown","Desglose por Usuario")}</h4>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>${t("User","Usuario")}</th><th>${t("Credits","Creditos")}</th><th>${t("Runs","Runs")}</th><th>${t("Daily","Diarios")}</th></tr></thead>
          <tbody>${users.map(u=>`
            <tr>
              <td>${escapeHtml(u.email)}</td>
              <td style="font-weight:600;color:var(--accent-cyan);">${u.credits??0}</td>
              <td>${u.total_runs??0}</td><td>${u.daily_runs??0}</td>
            </tr>`).join("")}</tbody>
        </table>
      </div>`;
  } catch(e) { area.innerHTML = `<p>Error.</p>`; }
}

async function loadRevenue(area, ctx) {
  const { t, escapeHtml } = ctx;
  area.innerHTML = `<p class="muted-copy">${t("Loading revenue data...","Cargando datos de ingresos...")}</p>`;
  try {
    const [res, settingsRes] = await Promise.all([
      fetch("/api/v1/admin/billing/summary"),
      fetch("/api/v1/admin/settings"),
    ]);
    if (!res.ok) { area.innerHTML = `<p style="color:var(--accent-red);">${t("Could not load revenue data.","No se pudieron cargar los datos de ingresos.")}</p>`; return; }
    const data = await res.json();
    if (settingsRes.ok) { const s = await settingsRes.json(); data.stripe_mode = s.stripe_mode||"test"; data.initial_credits = s.default_initial_credits||"0"; }
    area.innerHTML = `
      <div class="dashboard-stats" style="margin-bottom:2rem;">
        <div class="stat-card stat-cyan"><span class="stat-value">$${(data.total_revenue||0).toLocaleString()}</span><p class="stat-label">${t("Total Revenue","Ingresos Totales")}</p></div>
        <div class="stat-card stat-green"><span class="stat-value">$${(data.month_revenue||0).toLocaleString()}</span><p class="stat-label">${t("This Month","Este Mes")}</p></div>
        <div class="stat-card stat-purple"><span class="stat-value">${data.paying_users||0}</span><p class="stat-label">${t("Paying Users","Usuarios de Pago")}</p></div>
      </div>
      ${data.revenue_by_user?.length ? `
      <h4>${t("Revenue by User","Ingresos por Usuario")}</h4>
      <div class="admin-table-wrap"><table class="admin-table">
        <thead><tr><th>${t("User","Usuario")}</th><th>${t("Total Paid","Total Pagado")}</th><th>${t("Credits Purchased","Creditos Comprados")}</th><th>${t("Last Purchase","Ultima Compra")}</th></tr></thead>
        <tbody>${data.revenue_by_user.map(u=>`
          <tr>
            <td>${escapeHtml(u.email||"")}</td>
            <td style="font-weight:600;color:var(--accent-green);">$${(u.total_paid||0).toLocaleString()}</td>
            <td>${u.credits_purchased||0}</td>
            <td class="muted-copy">${u.last_purchase?new Date(u.last_purchase).toLocaleDateString():"-"}</td>
          </tr>`).join("")}</tbody>
      </table></div>` : `<p class="muted-copy">${t("No revenue data yet.","Sin datos de ingresos aun.")}</p>`}
      <div class="account-card" style="margin-top:2rem;">
        <h4>${t("Stripe Mode","Modo de Stripe")}</h4>
        <p class="muted-copy" style="margin-bottom:0.5rem;">${t("Current mode:","Modo actual:")} <strong id="admin-stripe-mode">${escapeHtml(data.stripe_mode||"test")}</strong></p>
        <button class="secondary-button" id="btn-toggle-stripe-mode">${t("Toggle to","Cambiar a")} ${data.stripe_mode==="live"?"test":"live"}</button>
      </div>
      <div class="account-card" style="margin-top:1rem;">
        <h4>${t("Initial Credits for New Users","Creditos Iniciales para Nuevos Usuarios")}</h4>
        <div style="display:flex;gap:8px;align-items:center;margin-top:0.5rem;">
          <input type="number" id="admin-initial-credits" min="0" max="10000" value="${data.initial_credits??5}" class="otp-code-input" style="text-align:left;letter-spacing:normal;font-size:1rem;width:100px;" />
          <button class="secondary-button" id="btn-save-initial-credits">${t("Save","Guardar")}</button>
        </div>
      </div>`;
    area.querySelector("#btn-toggle-stripe-mode")?.addEventListener("click", async () => {
      const newMode = data.stripe_mode==="live" ? "test" : "live";
      if (!window.confirm(t(`Switch Stripe to ${newMode} mode?`,`Cambiar Stripe a modo ${newMode}?`))) return;
      const r = await fetch("/api/v1/admin/settings", { method:"PATCH", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ stripe_mode: newMode }) });
      if (r.ok) loadRevenue(area, ctx);
    });
    area.querySelector("#btn-save-initial-credits")?.addEventListener("click", async () => {
      const val = parseInt(area.querySelector("#admin-initial-credits")?.value, 10);
      if (isNaN(val)||val<0) return;
      const r = await fetch("/api/v1/admin/settings", { method:"PATCH", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ initial_credits: val }) });
      if (r.ok) alert(t("Saved!","Guardado!"));
    });
  } catch(e) { area.innerHTML = `<p style="color:var(--accent-red);">Error: ${e.message}</p>`; }
}

export async function load(container, ctx) {
  const { PAGE, t } = ctx;
  const unlocked = !!PAGE?.unlockProtected;

  const skeleton = `
    <div class="tabs is-boxed admin-tabs" style="margin-bottom:1.5rem;">
      <ul>
        <li class="admin-tab is-active" data-admin-tab="requests"><a>${t("Access Requests","Solicitudes de Acceso")}</a></li>
        <li class="admin-tab" data-admin-tab="users"><a>${t("Users","Usuarios")}</a></li>
        <li class="admin-tab" data-admin-tab="usage"><a>${t("Usage","Uso")}</a></li>
        <li class="admin-tab" data-admin-tab="revenue"><a>${t("Revenue","Ingresos")}</a></li>
      </ul>
    </div>
    <div id="admin-tab-requests" class="admin-tab-content"></div>
    <div id="admin-tab-users"    class="admin-tab-content" style="display:none;"></div>
    <div id="admin-tab-usage"    class="admin-tab-content" style="display:none;"></div>
    <div id="admin-tab-revenue"  class="admin-tab-content" style="display:none;"></div>`;

  container.innerHTML = protectedWrapper(skeleton, unlocked, t);

  // Sub-tab switching
  const tabs = container.querySelectorAll(".admin-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t2 => t2.classList.remove("is-active"));
      tab.classList.add("is-active");
      const target = tab.getAttribute("data-admin-tab");
      container.querySelectorAll(".admin-tab-content").forEach(c => { c.style.display="none"; c.classList.remove("is-active"); });
      const el = container.querySelector(`#admin-tab-${target}`);
      if (el) { el.style.display="block"; el.classList.add("is-active"); }
    });
  });

  // Disable buttons if locked
  if (!unlocked) {
    container.querySelector(".protected-overlay")?.addEventListener("click", e => {
      if (e.target.tagName==="BUTTON"||e.target.closest("button")) {
        e.preventDefault(); e.stopPropagation();
        alert(t("Set UNLOCK_PROTECTED=true in .env to enable admin writes.","Establece UNLOCK_PROTECTED=true en .env para habilitar escrituras de admin."));
      }
    }, true);
  }

  loadRequests(container.querySelector("#admin-tab-requests"), ctx);
  loadUsers(container.querySelector("#admin-tab-users"), ctx);
  loadUsage(container.querySelector("#admin-tab-usage"), ctx);
  loadRevenue(container.querySelector("#admin-tab-revenue"), ctx);
}
