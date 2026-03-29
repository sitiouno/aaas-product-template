/**
 * Billing section — credit balance, Stripe checkout, payment history.
 * Exported: load(container, ctx)
 *
 * Fetches: /api/v1/account, /api/v1/billing/config,
 *          POST /api/v1/billing/checkout, /api/v1/billing/invoices
 */

async function purchaseCredits(qty, ctx) {
  const { t } = ctx;
  try {
    const res = await fetch("/api/v1/billing/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credits: qty }),
    });
    const data = await res.json();
    if (data.checkout_url) {
      window.location.href = data.checkout_url;
    } else {
      alert(data.error || t("Could not start checkout.", "No se pudo iniciar el checkout."));
    }
  } catch (e) {
    alert("Error: " + e.message);
  }
}

async function loadInvoices(area, ctx) {
  const { t } = ctx;
  if (!area) return;
  area.innerHTML = `<p class="muted-copy">${t("Loading...", "Cargando...")}</p>`;
  try {
    const res = await fetch("/api/v1/billing/invoices");
    if (!res.ok) {
      area.innerHTML = `<p class="muted-copy">${t("Could not load payment history.", "No se pudo cargar el historial de pagos.")}</p>`;
      return;
    }
    const invoices = await res.json();
    if (!invoices.length) {
      area.innerHTML = `<p class="muted-copy">${t("No payments yet.", "Sin pagos aun.")}</p>`;
      return;
    }
    area.innerHTML = `
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr>
            <th>${t("Date","Fecha")}</th>
            <th>${t("Credits","Creditos")}</th>
            <th>${t("Amount","Monto")}</th>
            <th>${t("Status","Estado")}</th>
          </tr></thead>
          <tbody>
            ${invoices.map(inv => `
              <tr>
                <td>${new Date(inv.created_at||inv.date).toLocaleDateString()}</td>
                <td>${inv.credits||0}</td>
                <td>$${(inv.amount_cents ? inv.amount_cents/100 : inv.amount||0).toFixed(2)}</td>
                <td><span class="pill pill-sm ${inv.status==="paid"?"pill-green":"pill-blue"}">${inv.status||"paid"}</span></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    area.innerHTML = `<p>Error.</p>`;
  }
}

export async function load(container, ctx) {
  const { t } = ctx;

  container.innerHTML = `
    <div class="account-card" style="margin-bottom:1.5rem;">
      <h4>${t("Credit Balance", "Saldo de Creditos")}</h4>
      <p style="font-size:2rem;font-weight:700;color:var(--accent-cyan);margin:0.25rem 0;" id="billing-credit-balance">…</p>
      <p class="muted-copy" style="margin:0;">${t("credits remaining", "creditos restantes")}</p>
    </div>

    <div id="billing-test-banner" class="protected-banner locked" style="display:none;margin-bottom:1rem;">
      ${t("Stripe is in test mode — no real charges will be made.", "Stripe está en modo de prueba — no se realizarán cargos reales.")}
    </div>

    <div class="account-card" style="margin-bottom:1.5rem;">
      <h4>${t("Buy Credits", "Comprar Creditos")}</h4>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:1rem;">
        <button class="primary-button billing-buy-btn" data-credits="100">100 ${t("credits","creditos")} — $100</button>
        <button class="primary-button billing-buy-btn" data-credits="250">250 ${t("credits","creditos")} — $250</button>
        <button class="primary-button billing-buy-btn" data-credits="500">500 ${t("credits","creditos")} — $500</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <input type="number" id="billing-custom-qty" min="1" max="10000" placeholder="${t("Custom qty","Cantidad custom")}"
          class="otp-code-input" style="text-align:left;letter-spacing:normal;font-size:1rem;width:130px;" />
        <span id="billing-custom-price" style="font-weight:600;color:var(--accent-cyan);min-width:60px;"></span>
        <button class="secondary-button" id="billing-custom-buy">${t("Buy","Comprar")}</button>
      </div>
    </div>

    <div class="account-card">
      <h4>${t("Payment History", "Historial de Pagos")}</h4>
      <div id="billing-invoices"></div>
    </div>`;

  // Load account balance
  try {
    const res = await fetch("/api/v1/account");
    if (res.ok) {
      const account = await res.json();
      const balEl = container.querySelector("#billing-credit-balance");
      if (balEl) balEl.textContent = account.credits ?? 0;
    }
  } catch (e) { /* ignore */ }

  // Test mode banner
  try {
    const cfgRes = await fetch("/api/v1/billing/config");
    if (cfgRes.ok) {
      const cfg = await cfgRes.json();
      const banner = container.querySelector("#billing-test-banner");
      if (banner && cfg.stripe_mode === "test") banner.style.display = "block";
    }
  } catch (e) { /* ignore */ }

  // Preset buy buttons
  container.querySelectorAll(".billing-buy-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const qty = parseInt(btn.getAttribute("data-credits"), 10);
      if (qty) purchaseCredits(qty, ctx);
    });
  });

  // Custom qty — live price display
  const customInput = container.querySelector("#billing-custom-qty");
  const customPrice = container.querySelector("#billing-custom-price");
  if (customInput && customPrice) {
    customInput.addEventListener("input", () => {
      const qty = parseInt(customInput.value, 10);
      customPrice.textContent = qty > 0 ? `$${qty}.00` : "";
    });
  }

  // Custom buy button
  container.querySelector("#billing-custom-buy")?.addEventListener("click", () => {
    const qty = parseInt(customInput?.value, 10);
    if (qty > 0) purchaseCredits(qty, ctx);
  });

  // Stripe redirect feedback
  const params = new URLSearchParams(window.location.search);
  if (params.get("billing") === "success") {
    alert(t("Payment successful! Credits have been added to your account.", "Pago exitoso! Los creditos se han agregado a tu cuenta."));
    const url = new URL(window.location); url.searchParams.delete("billing"); url.searchParams.delete("session_id");
    window.history.replaceState({}, "", url);
  } else if (params.get("billing") === "canceled") {
    alert(t("Payment was canceled.", "El pago fue cancelado."));
    const url = new URL(window.location); url.searchParams.delete("billing");
    window.history.replaceState({}, "", url);
  }

  loadInvoices(container.querySelector("#billing-invoices"), ctx);
}
