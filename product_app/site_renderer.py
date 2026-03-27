"""Server-rendered marketing pages with bilingual SEO metadata."""

from __future__ import annotations

import json
import os
import time
from html import escape
from typing import Any

from .config import load_settings


def _t(language: str, english: str, spanish: str) -> str:
    return spanish if language == "es" else english


def _lang_href(base_url: str, language: str, path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{path}" if path != "/" else base_url


def _nav_items(language: str) -> tuple[tuple[str, str], ...]:
    return ()


def _user_badge(language: str, user_summary: dict[str, Any] | None) -> str:
    if not user_summary or not user_summary.get("authenticated"):
        return (
            f'<button class="ghost-button" data-auth-action="open">'
            f'{escape(_t(language, "Sign in", "Entrar"))}</button>'
        )
    return (
        f'<a class="ghost-button" href="/{language}/app">'
        f'{escape(user_summary.get("email") or _t(language, "Account", "Cuenta"))}'
        "</a>"
    )


def _language_switch(language: str, current_path: str) -> str:
    if current_path == "/":
        en_path = "/en"
        es_path = "/es"
    elif current_path.startswith("/en"):
        en_path = current_path
        es_path = "/es" + current_path[3:]
    elif current_path.startswith("/es"):
        en_path = "/en" + current_path[3:]
        es_path = current_path
    else:
        en_path = f"/en{current_path}"
        es_path = f"/es{current_path}"

    return (
        '<div class="lang-switch" role="group" aria-label="Language selector">'
        f'<a class="lang-pill{" is-active" if language == "en" else ""}" href="{escape(en_path)}">EN</a>'
        f'<a class="lang-pill{" is-active" if language == "es" else ""}" href="{escape(es_path)}">ES</a>'
        "</div>"
    )


def _auth_modal(language: str) -> str:
    return f"""
<div id="auth-modal" class="auth-overlay">
  <div class="auth-card">
    <button class="auth-close" onclick="document.getElementById('auth-modal').classList.remove('is-active')">&times;</button>
    <h3>{escape(_t(language, 'Sign in to Product Name', 'Iniciar sesion en Product Name'))}</h3>
    <p class="auth-reason"></p>
    <form id="magic-link-form" class="auth-form">
      <label>{escape(_t(language, 'Email address', 'Correo electronico'))}</label>
      <input type="email" name="email" required placeholder="you@company.com" />
      <button type="submit" class="primary-button">
        {escape(_t(language, 'Send verification code', 'Enviar codigo de verificacion'))}
      </button>
    </form>
    <div id="otp-step" class="auth-form" style="display:none;">
      <p class="otp-hint">{escape(_t(language, 'Enter the 6-digit code sent to your email', 'Ingresa el codigo de 6 digitos enviado a tu correo'))}</p>
      <input type="text" id="otp-input" maxlength="6" pattern="[0-9]*" inputmode="numeric"
             placeholder="000000" autocomplete="one-time-code" class="otp-code-input" />
      <button type="button" id="otp-verify-btn" class="primary-button">
        {escape(_t(language, 'Verify', 'Verificar'))}
      </button>
      <button type="button" id="otp-resend-btn" class="ghost-button" style="margin-top:0.5rem;font-size:0.8rem;">
        {escape(_t(language, 'Resend code', 'Reenviar codigo'))}
      </button>
    </div>
    <!-- Step 3: Complete registration (name) -->
    <div id="auth-step-register" style="display:none;">
      <p class="auth-subtitle">{escape(_t(language, 'Almost there! Enter your name to get started.', 'Casi listo! Ingresa tu nombre para comenzar.'))}</p>
      <input type="text" id="register-name" placeholder="{escape(_t(language, 'Your full name', 'Tu nombre completo'))}" minlength="2" maxlength="160"
             class="otp-code-input" autocomplete="name" style="text-align:left;letter-spacing:normal;font-size:1rem;" />
      <button id="btn-complete-register" class="primary-button" type="button">
        {escape(_t(language, 'Create Account', 'Crear Cuenta'))}
      </button>
      <p id="register-error" class="auth-status" style="display:none;color:var(--accent-red);"></p>
    </div>
    <p id="magic-link-status" class="auth-status"></p>
  </div>
</div>"""


def _layout(
    *,
    language: str,
    current_path: str,
    title: str,
    description: str,
    body_html: str,
    user_summary: dict[str, Any] | None,
    jsonld: list[dict[str, Any]] | None = None,
) -> str:
    settings = load_settings()
    asset_version = os.getenv("K_REVISION", str(int(time.time())))
    base_url = settings.public_base_url
    canonical_url = _lang_href(base_url, language, current_path)
    alternates = [
        ("en", _lang_href(base_url, "en", current_path if current_path.startswith("/en") else f"/en{current_path[3:]}" if current_path.startswith("/es") else f"/en{current_path}")),
        ("es", _lang_href(base_url, "es", current_path if current_path.startswith("/es") else f"/es{current_path[3:]}" if current_path.startswith("/en") else f"/es{current_path}")),
        ("x-default", f"{base_url}/"),
    ]
    jsonld = jsonld or []
    jsonld.append(
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": settings.company_legal_name,
            "url": settings.public_base_url,
            "email": settings.support_email,
        }
    )

    nav_html = "".join(
        f'<a href="{
            escape(path)}">{
            escape(label)}</a>' for label,
        path in _nav_items(language))
    alternate_html = "".join(
        f'<link rel="alternate" hreflang="{
            escape(code)}" href="{
            escape(url)}" />' for code,
        url in alternates)
    jsonld_html = "".join(
        f'<script type="application/ld+json">{json.dumps(item, ensure_ascii=True)}</script>'
        for item in jsonld
    )
    page_state = json.dumps(
        {
            "appContext": "marketing",
            "language": language,
            "baseUrl": base_url,
            "devAuthEnabled": settings.enable_dev_auth,
        },
        ensure_ascii=True,
    )

    return f"""<!DOCTYPE html>
<html lang="{language}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <meta name="description" content="{escape(description)}" />
    <meta name="robots" content="index,follow,max-image-preview:large" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="{escape(title)}" />
    <meta property="og:description" content="{escape(description)}" />
    <meta property="og:url" content="{escape(canonical_url)}" />
    <meta property="og:site_name" content="{escape(settings.website_name)}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{escape(title)}" />
    <meta name="twitter:description" content="{escape(description)}" />
      <meta property="og:image" content="{escape(base_url)}/static/og-image.jpg" />
      <meta name="twitter:image" content="{escape(base_url)}/static/og-image.jpg" />
      <meta name="keywords" content="{escape(_t(language, 'Product Name, AI Agents, Deploy MVP, Cloud Run, Stripe, MCP, Developer Tools, AaaS, Agent Framework', 'Product Name, Agentes IA, Desplegar MVP, Cloud Run, Stripe, MCP, Herramientas de Desarrollador, AaaS, Framework de Agentes'))}" />
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />
    <link rel="canonical" href="{escape(canonical_url)}" />
    {alternate_html}
    <link rel="stylesheet" href="/static/app.css?v={escape(asset_version)}" />
    <script>window.__QUIEN_PAGE__ = {page_state};</script>
    <script type="module" src="/static/app.js?v={escape(asset_version)}" defer></script>
    {jsonld_html}
  </head>
  <body class="ctx-marketing">
    <div class="marketing-shell">
      <header class="site-header">
        <a class="brand-lockup" href="/{language}">
          <span class="brand-mark">M</span>
          <span>
            <strong>{escape(settings.website_name)}</strong>
            <small>{escape(_t(language, settings.website_tagline_en, settings.website_tagline_es))}</small>
          </span>
        </a>
        <nav class="site-nav">{nav_html}</nav>
        <div class="site-actions">
          {_language_switch(language, current_path)}
          {_user_badge(language, user_summary)}
        </div>
      </header>
      {body_html}
      <footer class="site-footer">
          <p>{escape(_t(language, "Product Name — Deploy AI-powered products in minutes. Infrastructure, billing, and agents included.", "Product Name — Despliega productos con IA en minutos. Infraestructura, facturacion y agentes incluidos."))}</p>
        <p>{escape(_t(language, "Developed by: ", "Desarrollado por: "))}<a href="https://www.sitiouno.us/">Sitio Uno Inc</a></p>
        <div class="footer-links">
          <a href="/docs">API Docs</a>
        </div>
      </footer>
    </div>
    {_auth_modal(language)}
  </body>
</html>"""


def render_app_shell(language: str, current_path: str,
                     user_summary: dict[str, Any] | None) -> str:
    settings = load_settings()
    asset_version = os.getenv("K_REVISION", str(int(time.time())))
    account_payload = user_summary or {
        "authenticated": False,
        "api_keys": []}
    base_url = settings.public_base_url
    page_state = json.dumps(
        {
            "appContext": "workspace",
            "language": language,
            "baseUrl": base_url,
            "devAuthEnabled": settings.enable_dev_auth,
        },
        ensure_ascii=True,
    )

    return f"""<!DOCTYPE html>
<html lang="{language}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(settings.website_name)} | Workspace</title>
    <meta name="robots" content="noindex,nofollow" />
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />
    <link rel="stylesheet" href="/static/app.css?v={escape(asset_version)}" />
    <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.30.4/dist/cytoscape.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/layout-base@2.0.1/layout-base.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/cose-base@2.2.0/cose-base.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/cytoscape-cose-bilkent@4.1.0/cytoscape-cose-bilkent.js"></script>
    <script>window.__QUIEN_PAGE__ = {page_state};</script>
    <script>window.__QUIEN_ACCOUNT__ = {json.dumps(account_payload, ensure_ascii=True)};</script>
    <script type="module" src="/static/app.js?v={escape(asset_version)}" defer></script>
  </head>
  <body class="ctx-workspace">
    <div class="workspace-shell">
      <header class="workspace-header">
        <button class="hamburger-btn" id="hamburger-toggle" aria-label="Menu">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
        <a class="brand-lockup" href="/{language}/app">
          <span class="brand-mark">M</span>
          <span>
            <strong>{escape(settings.website_name)}</strong>
            <small>{escape(_t(language, 'Deploy Studio', 'Estudio de Despliegue'))}</small>
          </span>
        </a>
        <div class="workspace-header-actions">
          <a class="ghost-link hide-mobile" href="/{language}">{escape(_t(language, 'Public site', 'Sitio publico'))}</a>
          <button class="ghost-button" id="workspace-logout-button">{escape(_t(language, 'Sign out', 'Cerrar sesion'))}</button>
        </div>
      </header>

      <aside class="workspace-sidebar">
          <h2>Product Name</h2>
          <nav class="workspace-nav">
            <a href="#dashboard" data-view="workspace-dashboard" class="is-active">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
              {escape(_t(language, 'Dashboard', 'Panel'))}
            </a>
            <a href="#research" data-view="workspace-research">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
              {escape(_t(language, 'Deploy Product', 'Desplegar Producto'))}
            </a>
            <a href="#history" data-view="workspace-history">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              {escape(_t(language, 'Deployments', 'Despliegues'))}
            </a>
            <a href="#how-it-works" data-view="workspace-how-it-works">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
              {escape(_t(language, 'How It Works', 'Como Funciona'))}
            </a>
            <div class="nav-separator"></div>
            <a href="#api" data-view="workspace-api">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
              {escape(_t(language, 'API & MCP', 'API y MCP'))}
            </a>
            <a href="#account" data-view="workspace-account">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              {escape(_t(language, 'My Account', 'Mi Cuenta'))}
            </a>
            <a href="#billing" data-view="workspace-billing">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
              {escape(_t(language, 'Billing', 'Facturacion'))}
            </a>
            <a href="#admin" id="nav-admin" data-view="workspace-admin" style="display: none;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              {escape(_t(language, 'Admin', 'Admin'))}
            </a>
          </nav>
        </aside>

        <main class="workspace-content">

          <!-- DASHBOARD -->
          <section id="workspace-dashboard" class="workspace-section is-active">
            <div class="ws-panel">
              <div class="dash-header">
                <div>
                  <h2 class="dashboard-welcome" id="dashboard-welcome">{escape(_t(language, 'Welcome to Product Name', 'Bienvenido a Product Name'))}</h2>
                  <p class="muted-copy">{escape(_t(language, 'Your command center for deploying AI-powered products.', 'Tu centro de control para desplegar productos con IA.'))}</p>
                </div>
                <button class="primary-button" onclick="window.location.hash='research'">{escape(_t(language, 'Deploy Product', 'Desplegar Producto'))} &rarr;</button>
              </div>

              <div class="dashboard-stats" id="workspace-stats"></div>

              <div class="dashboard-grid">
                <div class="dashboard-section">
                  <h3>{escape(_t(language, 'Quick Launch', 'Lanzamiento Rapido'))}</h3>
                  <div id="dashboard-quick-launch" class="quick-launch-grid"></div>
                </div>
                <div class="dashboard-section">
                  <h3>{escape(_t(language, 'Recent Deployments', 'Despliegues Recientes'))}</h3>
                  <div id="dashboard-recent" class="recent-activity-list"></div>
                  <a class="section-link" href="#history">{escape(_t(language, 'View all deployments', 'Ver todos los despliegues'))} &rarr;</a>
                </div>
              </div>

              <div class="dashboard-section" style="margin-top:24px;">
                <h3>{escape(_t(language, 'My Products', 'Mis Productos'))}</h3>
                <div id="products-dashboard"></div>
              </div>
            </div>
          </section>

        <!-- RESEARCH LAUNCHER -->
        <section id="workspace-research" class="workspace-section">
          <div class="ws-panel">
            <div class="ws-panel-head">
              <div>
                <p class="eyebrow">{escape(_t(language, 'Launch deployment', 'Lanzar despliegue'))}</p>
                <h2>{escape(_t(language, 'Deploy New Product', 'Desplegar Nuevo Producto'))}</h2>
              </div>
            </div>
            <div class="style-grid" id="research-style-grid">
              <!-- Populated by JS from /api/v1/research/capabilities -->
            </div>
            <div class="research-form" id="research-form-area" style="display:none">
              <h3 id="selected-style-label"></h3>
              <textarea id="app-prompt-input" rows="4" placeholder="{escape(_t(language, 'e.g., A content scheduling tool for social media managers called PostFlow at postflow.studio', 'ej., Una herramienta de programacion de contenido para community managers llamada PostFlow en postflow.studio'))}"></textarea>
              <div class="form-row">
                <select id="app-language-select">
                  <option value="en">English</option>
                  <option value="es">Español</option>
                </select>
                <button id="app-run-submit" class="primary-button" type="button">{escape(_t(language, 'Deploy Product', 'Desplegar Producto'))}</button>
              </div>
              <p class="credit-cost-note" id="credit-cost-note"></p>
            </div>
            <p id="app-run-feedback" class="action-feedback" hidden></p>
            <div class="launcher-results">
              <div id="active-tasks-panel"></div>
              <div class="progress-meter"><div id="app-progress-fill"></div></div>
              <div id="app-run-status-area" style="display:none;">
                <h3 id="app-current-stage-title">{escape(_t(language, 'Waiting for a run', 'Esperando una corrida'))}</h3>
                <p id="app-current-stage-description" class="muted-copy">{escape(_t(language, 'Stage and execution log will appear here.', 'Aqui aparecera la etapa y bitacora de ejecucion.'))}</p>
                <div class="workspace-grid">
                  <div class="workspace-column">
                    <div id="app-stage-list" class="stage-list"></div>
                  </div>
                  <div class="workspace-column">
                    <div id="app-results-stack" class="results-stack"></div>
                    <div id="app-artifact-grid" class="ws-artifact-grid"></div>
                    <div id="app-log-feed" class="log-feed"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- RUNS & HISTORY -->
        <section id="workspace-history" class="workspace-section">
          <div class="ws-panel">
            <div class="ws-panel-head">
              <h2>{escape(_t(language, 'Deployments & History', 'Despliegues e historial'))}</h2>
            </div>
            <div class="history-filters">
              <label>
                <span>{escape(_t(language, 'Style', 'Estilo'))}</span>
                <select id="app-filter-style">
                  <option value="">{escape(_t(language, 'All', 'Todos'))}</option>
                  <option value="deploy_product">Deploy Product</option>
                  <option value="market_intelligence">Market Intelligence</option>
                  <option value="world_news_briefing">World News Briefing</option>
                  <option value="company_deep_dive">Company Deep Dive</option>
                  <option value="industry_analysis">Industry Analysis</option>
                  <option value="osint_360">OSINT 360 Premium</option>
                </select>
              </label>
              <label>
                <span>{escape(_t(language, 'Status', 'Estado'))}</span>
                <select id="app-filter-status">
                  <option value="">{escape(_t(language, 'All', 'Todos'))}</option>
                  <option value="queued">Queued</option>
                  <option value="running">Running</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                </select>
              </label>
              <label>
                <span>{escape(_t(language, 'From', 'Desde'))}</span>
                <input id="app-filter-date-from" type="date" />
              </label>
              <label>
                <span>{escape(_t(language, 'To', 'Hasta'))}</span>
                <input id="app-filter-date-to" type="date" />
              </label>
              <label>
                <span>{escape(_t(language, 'Search', 'Buscar'))}</span>
                <input id="app-filter-query" type="search" placeholder="{escape(_t(language, 'Prompt, ticker, sector...', 'Prompt, ticker, sector...'))}" />
              </label>
              <div style="display:flex;gap:6px;align-items:end;">
                <button id="app-apply-filters" class="secondary-button" type="button">{escape(_t(language, 'Filter', 'Filtrar'))}</button>
                <button id="app-reset-filters" class="ghost-button" type="button">{escape(_t(language, 'Reset', 'Limpiar'))}</button>
              </div>
            </div>
            <div id="app-history-list"></div>
          </div>
        </section>

        <!-- HOW IT WORKS -->
        <section id="workspace-how-it-works" class="workspace-section">
          <div class="ws-panel">
            <div class="ws-panel-head">
              <div>
                <p class="eyebrow">{escape(_t(language, 'Architecture', 'Arquitectura'))}</p>
                <h2>{escape(_t(language, 'How Deployment Pipelines Work', 'Como Funcionan los Pipelines de Despliegue'))}</h2>
              </div>
            </div>
            <p class="muted-copy" style="margin-bottom:2rem;">{escape(_t(language, 'Each deployment runs a multi-agent pipeline with specialized AI agents provisioning infrastructure, designing landing pages, and configuring billing.', 'Cada despliegue ejecuta un pipeline multi-agente con agentes de IA especializados provisionando infraestructura, disenando landing pages y configurando facturacion.'))}</p>
            <div id="pipeline-cards" class="pipeline-grid"></div>
          </div>
        </section>

        <!-- API & MCP -->
        <section id="workspace-api" class="workspace-section">
          <div class="ws-panel">
            <div class="ws-panel-head">
              <div>
                <p class="eyebrow">{escape(_t(language, 'Developer', 'Developer'))}</p>
                <h2>{escape(_t(language, 'API Keys & Integration', 'API Keys e Integracion'))}</h2>
              </div>
            </div>

            <!-- API Keys Management -->
            <div id="app-api-keys-area"></div>

            <!-- REST API Quick Start -->
            <div class="api-panel" style="margin-top:2rem;">
              <h3>{escape(_t(language, 'REST API Quick Start', 'Inicio Rapido REST API'))}</h3>
              <pre class="code-block">curl -X POST {escape(base_url)}/api/v1/runs \\
  -H "X-API-Key: $YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"prompt": "A task manager for remote teams called TaskFlow at taskflow.app", "research_style": "deploy_product"}}'</pre>
              <h4 style="margin:1.5rem 0 0.75rem;">{escape(_t(language, 'Endpoints', 'Endpoints'))}</h4>
              <div class="api-endpoint-list">
                <div class="api-endpoint"><span class="api-method post">POST</span><span class="api-path">/api/v1/runs</span><span class="api-desc">{escape(_t(language, 'Launch deployment', 'Lanzar despliegue'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">GET</span><span class="api-path">/api/v1/runs/{{job_id}}</span><span class="api-desc">{escape(_t(language, 'Get run status & results', 'Estado y resultados'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">GET</span><span class="api-path">/api/v1/runs/{{job_id}}/stream</span><span class="api-desc">{escape(_t(language, 'SSE real-time progress', 'Progreso en tiempo real SSE'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">GET</span><span class="api-path">/api/v1/runs/{{job_id}}/report</span><span class="api-desc">{escape(_t(language, 'HTML report', 'Reporte HTML'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">GET</span><span class="api-path">/api/v1/runs/{{job_id}}/export</span><span class="api-desc">{escape(_t(language, 'Export (json, md, html)', 'Exportar (json, md, html)'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">GET</span><span class="api-path">/api/v1/research/capabilities</span><span class="api-desc">{escape(_t(language, 'Available deployment types', 'Tipos de despliegue disponibles'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">GET</span><span class="api-path">/api/v1/account</span><span class="api-desc">{escape(_t(language, 'Account & balance', 'Cuenta y saldo'))}</span></div>
              </div>
            </div>

            <!-- MCP Server Configuration -->
            <div class="api-panel" style="margin-top:2rem;">
              <h3>{escape(_t(language, 'MCP Server Configuration', 'Configuracion del Servidor MCP'))}</h3>
              <p class="muted-copy" style="margin-bottom:1rem;">{escape(_t(language, 'Connect Product Name to Claude Desktop, Cursor, or any MCP-compatible client. Add this to your MCP config:', 'Conecta Product Name a Claude Desktop, Cursor, o cualquier cliente compatible MCP. Agrega esto a tu configuracion MCP:'))}</p>
              <pre class="code-block">{{
  "mcpServers": {{
    "product-name": {{
      "command": "python",
      "args": ["-m", "product_app.mcp_server"],
      "env": {{
        "PRODUCT_API_URL": "{escape(base_url)}",
        "PRODUCT_API_KEY": "YOUR_API_KEY"
      }}
    }}
  }}
}}</pre>
              <h4 style="margin:1.5rem 0 0.75rem;">{escape(_t(language, 'Available MCP Tools', 'Herramientas MCP Disponibles'))}</h4>
              <div class="api-endpoint-list">
                <div class="api-endpoint"><span class="api-method post">TOOL</span><span class="api-path">submit_deployment</span><span class="api-desc">{escape(_t(language, 'Start a product deployment with prompt', 'Iniciar despliegue de producto con prompt'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">TOOL</span><span class="api-path">get_deployment_status</span><span class="api-desc">{escape(_t(language, 'Check progress of a deployment job', 'Verificar progreso de un despliegue'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">TOOL</span><span class="api-path">get_deployment_report</span><span class="api-desc">{escape(_t(language, 'Get completed deployment report (json/text/html)', 'Obtener reporte de despliegue (json/text/html)'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">TOOL</span><span class="api-path">list_deployment_styles</span><span class="api-desc">{escape(_t(language, 'List deployment types with costs & durations', 'Listar tipos de despliegue con costos y duraciones'))}</span></div>
                <div class="api-endpoint"><span class="api-method get">TOOL</span><span class="api-path">get_credit_balance</span><span class="api-desc">{escape(_t(language, 'Check credit balance', 'Consultar saldo de creditos'))}</span></div>
              </div>
            </div>
          </div>
        </section>

        <!-- BILLING -->
        <section id="workspace-billing" class="workspace-section">
          <div class="ws-panel">
            <div class="ws-panel-head">
              <div>
                <p class="eyebrow">{escape(_t(language, 'Billing', 'Facturacion'))}</p>
                <h2>{escape(_t(language, 'Credits & Billing', 'Creditos y Facturacion'))}</h2>
              </div>
            </div>
            <div id="billing-test-banner" style="display:none;background:var(--accent-amber);color:#000;padding:8px 16px;border-radius:8px;margin-bottom:1rem;font-weight:600;text-align:center;">
              {escape(_t(language, 'TEST MODE - No real charges will be made', 'MODO TEST - No se realizaran cargos reales'))}
            </div>
            <div class="dashboard-stats" style="margin-bottom:2rem;">
              <div class="stat-card stat-cyan">
                <span class="stat-value" id="billing-credit-balance">-</span>
                <p class="stat-label">{escape(_t(language, 'Credits Balance', 'Saldo de Creditos'))}</p>
              </div>
            </div>
            <div class="account-card" style="margin-bottom:2rem;">
              <h4>{escape(_t(language, 'Buy Credits', 'Comprar Creditos'))}</h4>
              <p class="muted-copy" style="margin-bottom:1rem;">{escape(_t(language, 'Each deployment costs 5 credits. Choose a pack or enter a custom amount.', 'Cada despliegue cuesta 5 creditos. Elige un paquete o ingresa un monto personalizado.'))}</p>
              <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:1rem;">
                <button class="primary-button billing-buy-btn" data-credits="25" style="min-width:140px;">25 {escape(_t(language, 'credits', 'creditos'))} — $25</button>
                <button class="primary-button billing-buy-btn" data-credits="50" style="min-width:140px;">50 {escape(_t(language, 'credits', 'creditos'))} — $50</button>
                <button class="primary-button billing-buy-btn" data-credits="100" style="min-width:140px;">100 {escape(_t(language, 'credits', 'creditos'))} — $100</button>
              </div>
              <div style="display:flex;gap:8px;align-items:center;">
                <input type="number" id="billing-custom-qty" min="1" max="10000" placeholder="{escape(_t(language, 'Custom qty', 'Cant. personalizada'))}" class="otp-code-input" style="text-align:left;letter-spacing:normal;font-size:1rem;width:160px;" />
                <span id="billing-custom-price" class="muted-copy"></span>
                <button class="secondary-button" id="billing-custom-buy">{escape(_t(language, 'Buy', 'Comprar'))}</button>
              </div>
            </div>
            <div class="account-card">
              <h4>{escape(_t(language, 'Payment History', 'Historial de Pagos'))}</h4>
              <div id="billing-invoices"></div>
            </div>
          </div>
        </section>

        <!-- ADMIN PANEL -->
        <section id="workspace-admin" class="workspace-section">
          <div class="ws-panel">
            <div class="ws-panel-head">
              <div>
                <p class="eyebrow" style="color:var(--accent-amber);">{escape(_t(language, 'Administration', 'Administracion'))}</p>
                <h2>{escape(_t(language, 'Platform Administration', 'Administracion de la Plataforma'))}</h2>
              </div>
            </div>

            <!-- Admin Sub-tabs -->
            <div class="admin-tabs" id="admin-tabs">
              <button class="admin-tab is-active" data-admin-tab="requests">{escape(_t(language, 'Access Requests', 'Solicitudes de Acceso'))}</button>
              <button class="admin-tab" data-admin-tab="users">{escape(_t(language, 'Users & Credits', 'Usuarios y Creditos'))}</button>
              <button class="admin-tab" data-admin-tab="usage">{escape(_t(language, 'Platform Usage', 'Uso de Plataforma'))}</button>
              <button class="admin-tab" data-admin-tab="revenue">{escape(_t(language, 'Revenue', 'Ingresos'))}</button>
            </div>

            <div id="admin-tab-requests" class="admin-tab-content is-active"></div>
            <div id="admin-tab-users" class="admin-tab-content" style="display:none;"></div>
            <div id="admin-tab-usage" class="admin-tab-content" style="display:none;"></div>
            <div id="admin-tab-revenue" class="admin-tab-content" style="display:none;"></div>
          </div>
        </section>

        <!-- MY ACCOUNT -->
        <section id="workspace-account" class="workspace-section">
          <div class="ws-panel">
            <div class="ws-panel-head">
              <div>
                <p class="eyebrow">{escape(_t(language, 'Account', 'Cuenta'))}</p>
                <h2>{escape(_t(language, 'My Account & Usage', 'Mi Cuenta y Consumo'))}</h2>
              </div>
            </div>
            <div id="app-account-area"></div>
          </div>
        </section>

        <!-- REPORT VIEWER (hidden from nav, accessed via viewRun) -->
        <section id="workspace-report-viewer" class="workspace-section report-viewer-section">
          <div class="report-viewer">
            <div class="report-viewer-toolbar">
              <button id="report-viewer-back" class="ghost-button">&larr; {escape(_t(language, 'Back', 'Volver'))}</button>
              <div class="report-viewer-actions">
                <a id="report-viewer-export-html" class="ghost-button" target="_blank">{escape(_t(language, 'Open HTML', 'Abrir HTML'))}</a>
              </div>
            </div>
            <div class="report-viewer-header">
              <span id="report-viewer-style" class="pill pill-sm pill-blue"></span>
              <h1 id="report-viewer-title"></h1>
              <p id="report-viewer-meta" class="muted-copy"></p>
            </div>
            <!-- Tab navigation -->
            <div id="report-viewer-tabs" class="rv-tabs">
              <button class="rv-tab rv-tab-active" data-tab="report">{escape(_t(language, 'Report', 'Reporte'))}</button>
              <button class="rv-tab rv-tab-osint-only" data-tab="graph" style="display:none;">{escape(_t(language, 'Network Graph', 'Grafo de Red'))}</button>
              <button class="rv-tab rv-tab-osint-only" data-tab="evidence" style="display:none;">{escape(_t(language, 'Evidence Board', 'Tablero de Evidencias'))}</button>
              <button class="rv-tab" data-tab="artifacts">{escape(_t(language, 'Artifacts', 'Artefactos'))}</button>
            </div>
            <!-- Tab panels -->
            <div id="rv-panel-report" class="rv-panel rv-panel-active">
              <div id="report-viewer-summary" class="rv-executive-summary"></div>
              <div id="report-viewer-photos" class="rv-photo-row"></div>
              <div id="report-viewer-sections" class="report-viewer-body"></div>
            </div>
            <div id="rv-panel-graph" class="rv-panel" style="display:none;">
              <div id="rv-graph-toolbar" class="rv-graph-toolbar"></div>
              <div id="rv-graph-container" class="rv-graph-container"></div>
              <div id="rv-graph-details" class="rv-graph-details"></div>
            </div>
            <div id="rv-panel-evidence" class="rv-panel" style="display:none;">
              <div id="rv-evidence-container" class="rv-evidence-container"></div>
            </div>
            <div id="rv-panel-artifacts" class="rv-panel" style="display:none;">
              <div id="report-viewer-artifact-grid" class="ws-artifact-grid"></div>
            </div>
          </div>
        </section>

      </main>

      <!-- Onboarding Modal -->
      <div id="onboarding-modal" class="auth-overlay" style="display:none;">
        <div class="auth-card" style="max-width:520px;">
          <h2 style="color:var(--accent-cyan);margin:0 0 16px;">{escape(_t(language, 'Welcome to Product Name!', 'Bienvenido a Product Name!'))}</h2>
          <p style="font-size:18px;color:var(--accent-purple);margin:0 0 16px;" id="onboarding-credits-msg"></p>
          <p style="margin:0 0 16px;">{escape(_t(language, 'Each deployment costs 5 credits. Describe your product idea and our agents will build it:', 'Cada despliegue cuesta 5 creditos. Describe tu idea de producto y nuestros agentes lo construiran:'))}</p>
          <ul style="list-style:none;padding:0;margin:0 0 24px;">
            <li style="padding:6px 0;border-bottom:1px solid var(--border-subtle);">&bull; <strong>{escape(_t(language, 'AI Agent Pipeline', 'Pipeline de Agentes IA'))}</strong></li>
            <li style="padding:6px 0;border-bottom:1px solid var(--border-subtle);">&bull; <strong>{escape(_t(language, 'Instant Infrastructure', 'Infraestructura Instantanea'))}</strong></li>
            <li style="padding:6px 0;border-bottom:1px solid var(--border-subtle);">&bull; <strong>{escape(_t(language, 'MCP Ready', 'Listo para MCP'))}</strong></li>
            <li style="padding:6px 0;">&bull; <strong>{escape(_t(language, 'Developer-First', 'Para Desarrolladores'))}</strong></li>
          </ul>
          <button id="btn-dismiss-onboarding" class="primary-button" style="width:100%;padding:12px;font-size:16px;">{escape(_t(language, 'Start Deploying', 'Comenzar a Desplegar'))}</button>
        </div>
      </div>

    </div>
  </body>
</html>"""


def render_landing(language: str, current_path: str,
                   user_summary: dict[str, Any] | None) -> str:
    settings = load_settings()
    description = _t(
        language,
        "Deploy AI-Powered MVPs in Minutes. From idea to live product with agents, billing, API, and MCP — ready for developers.",
        "Despliega MVPs con IA en Minutos. De idea a producto en vivo con agentes, facturacion, API y MCP — listo para desarrolladores.",
    )
    body_html = f"""
    <main class="landing-grid">

      <!-- HERO -->
      <section class="hero-panel" style="padding: 4rem 2rem; text-align: center; max-width: 900px; margin: 0 auto;">
        <div class="hero-copy">
          <p class="eyebrow" style="font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 1rem;">{escape(_t(language, "Product Name", "Product Name"))}</p>
          <h1 style="font-size: 3rem; line-height: 1.1; margin-bottom: 1.5rem; letter-spacing: -0.02em; font-weight: 800;">{escape(_t(language, "Deploy AI-Powered MVPs in Minutes", "Despliega MVPs con IA en Minutos"))}</h1>
          <p class="hero-text" style="font-size: 1.25rem; color: var(--text-secondary); margin-bottom: 2.5rem; max-width: 800px; margin-left: auto; margin-right: auto;">{escape(_t(language, "From idea to live product with agents, billing, API, and MCP — ready for developers.", "De idea a producto en vivo con agentes, facturacion, API y MCP — listo para desarrolladores."))}</p>
          <div class="hero-actions" style="display: flex; gap: 1rem; justify-content: center; align-items: center; margin-bottom: 3rem;">
            <a class="primary-button" style="padding: 0.8rem 1.5rem; font-size: 1.1rem;" href="#get-started">{escape(_t(language, "Deploy Your First MVP", "Despliega Tu Primer MVP"))}</a>
            <a class="ghost-link" style="font-weight: 600;" href="/docs">{escape(_t(language, "View API Docs", "Ver Docs de API"))} &rarr;</a>
          </div>
        </div>
      </section>

      <!-- FEATURES -->
      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{escape(_t(language, "What You Get", "Lo Que Obtienes"))}</p>
            <h2>{escape(_t(language, "Everything to Launch Your Product", "Todo para Lanzar Tu Producto"))}</h2>
          </div>
        </div>
        <div class="step-grid" style="grid-template-columns: repeat(4, minmax(0, 1fr));">
          <article>
            <strong>{escape(_t(language, "AI Agent Pipeline", "Pipeline de Agentes IA"))}</strong>
            <p>{escape(_t(language, "Multi-agent orchestration builds your product end-to-end: landing page, API, database, and deployment.", "Orquestacion multi-agente construye tu producto de principio a fin: landing page, API, base de datos y despliegue."))}</p>
          </article>
          <article>
            <strong>{escape(_t(language, "Instant Infrastructure", "Infraestructura Instantanea"))}</strong>
            <p>{escape(_t(language, "Cloud Run, Supabase, Stripe billing, and custom domains — provisioned automatically in minutes.", "Cloud Run, Supabase, facturacion Stripe y dominios personalizados — provisionados automaticamente en minutos."))}</p>
          </article>
          <article>
            <strong>{escape(_t(language, "MCP Ready", "Listo para MCP"))}</strong>
            <p>{escape(_t(language, "Every deployed product includes an MCP server. Connect to Claude, Cursor, or any MCP-compatible client.", "Cada producto desplegado incluye un servidor MCP. Conecta con Claude, Cursor o cualquier cliente compatible MCP."))}</p>
          </article>
          <article>
            <strong>{escape(_t(language, "Developer-First", "Para Desarrolladores"))}</strong>
            <p>{escape(_t(language, "Full source code, REST API, webhooks, and CI/CD pipeline. Own your code from day one.", "Codigo fuente completo, API REST, webhooks y pipeline CI/CD. Tu codigo desde el dia uno."))}</p>
          </article>
        </div>
      </section>

      <!-- HOW IT WORKS -->
      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{escape(_t(language, "How It Works", "Como Funciona"))}</p>
            <h2>{escape(_t(language, "From Idea to Live Product in 3 Steps", "De Idea a Producto en Vivo en 3 Pasos"))}</h2>
          </div>
        </div>
        <div class="step-grid">
          <article style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">1</div>
            <strong>{escape(_t(language, "Describe Your Product", "Describe Tu Producto"))}</strong>
            <p>{escape(_t(language, "Tell us what you want to build: name, domain, features, and target audience.", "Dinos que quieres construir: nombre, dominio, funcionalidades y audiencia objetivo."))}</p>
          </article>
          <article style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">2</div>
            <strong>{escape(_t(language, "Agents Build It", "Los Agentes lo Construyen"))}</strong>
            <p>{escape(_t(language, "AI agents provision infrastructure, generate code, configure billing, and deploy — all automatically.", "Los agentes de IA provisionan infraestructura, generan codigo, configuran facturacion y despliegan — todo automaticamente."))}</p>
          </article>
          <article style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">3</div>
            <strong>{escape(_t(language, "Start Coding", "Empieza a Programar"))}</strong>
            <p>{escape(_t(language, "Get full source code, CI/CD pipeline, and live URL. Customize and iterate from a working product.", "Recibe codigo fuente completo, pipeline CI/CD y URL en vivo. Personaliza e itera desde un producto funcional."))}</p>
          </article>
        </div>
      </section>

      <!-- PRICING & GET STARTED -->
      <section class="panel" id="get-started" style="margin-top: 1rem;">
        <div style="max-width: 700px; margin: 0 auto; text-align: center;">
          <p class="eyebrow">{escape(_t(language, "Simple Pricing", "Precio Simple"))}</p>
          <h2>{escape(_t(language, "5 Credits per Deployment ($5)", "5 Creditos por Despliegue ($5)"))}</h2>
          <p class="hero-text" style="margin-bottom: 32px; font-size: 1.1rem;">{escape(_t(language, "No subscriptions, no contracts. Pay only for what you deploy. Get free credits to start.", "Sin suscripciones, sin contratos. Paga solo lo que despliegas. Recibe creditos gratis para empezar."))}</p>
          <div class="step-grid" style="margin-bottom: 32px;">
            <article style="text-align: center;">
              <div style="font-size: 2rem; margin-bottom: 8px;">1</div>
              <strong>{escape(_t(language, "Sign Up & Get Credits", "Registrate y Recibe Creditos"))}</strong>
              <p>{escape(_t(language, "Create your account in seconds. Free credits to deploy your first product — no card required.", "Crea tu cuenta en segundos. Creditos gratis para tu primer producto — sin tarjeta."))}</p>
            </article>
            <article style="text-align: center;">
              <div style="font-size: 2rem; margin-bottom: 8px;">2</div>
              <strong>{escape(_t(language, "Deploy Your Product", "Despliega Tu Producto"))}</strong>
              <p>{escape(_t(language, "Describe your idea. AI agents build, configure, and deploy it in minutes.", "Describe tu idea. Los agentes de IA lo construyen, configuran y despliegan en minutos."))}</p>
            </article>
            <article style="text-align: center;">
              <div style="font-size: 2rem; margin-bottom: 8px;">3</div>
              <strong>{escape(_t(language, "Own & Scale", "Haz Tuyo y Escala"))}</strong>
              <p>{escape(_t(language, "Get full source code, CI/CD, and live URL. Connect via REST API, MCP, or webhooks.", "Recibe codigo fuente completo, CI/CD y URL en vivo. Conecta via API REST, MCP o webhooks."))}</p>
            </article>
          </div>
          <a class="primary-button" style="padding: 0.9rem 2.5rem; font-size: 1.15rem;" href="/{language}/app">{escape(_t(language, "Deploy Your First MVP", "Despliega Tu Primer MVP"))}</a>
        </div>
      </section>

      <!-- CUSTOM PRODUCTS -->
      <section class="panel" style="text-align: center;">
        <p class="eyebrow">{escape(_t(language, "Need Something Custom?", "Necesitas Algo a la Medida?"))}</p>
        <h2>{escape(_t(language, "Your Custom Product, Built in 24h", "Tu Producto a Medida, Creado en 24h"))}</h2>
        <p class="hero-text" style="max-width: 600px; margin: 0 auto 24px; font-size: 1.05rem;">{escape(_t(language, "Need a specialized agent pipeline or custom deployment? Tell us and we'll build it for you in 24 hours.", "Necesitas un pipeline de agentes especializado o un despliegue personalizado? Escribenos y lo creamos en 24 horas."))}</p>
        <form id="custom-agent-form" class="access-form" style="max-width: 400px; margin: 24px auto 0; text-align: left;"
              onsubmit="return false;">
          <label>
            <span>{escape(_t(language, "Your name", "Tu nombre"))}</span>
            <input type="text" name="ca_name" required placeholder="Jane Smith" />
          </label>
          <label>
            <span>{escape(_t(language, "Your email", "Tu email"))}</span>
            <input type="email" name="ca_email" required placeholder="jane@company.com" />
          </label>
          <button type="button" class="primary-button" style="width: 100%;"
                  onclick="(function(){{
                    var f=document.getElementById('custom-agent-form');
                    var n=f.ca_name.value.trim(), e=f.ca_email.value.trim();
                    if(!n||!e){{ alert('{escape(_t(language, "Please fill in your name and email.", "Por favor completa tu nombre y email."))}'); return; }}
                    var msg='Hi, I\\'m '+n+' ('+e+'). I\\'m interested in a custom product deployment on Product Name. Can you help me?';
                    window.open('https://api.whatsapp.com/send/?phone=14159435393&text='+encodeURIComponent(msg)+'&type=phone_number&app_absent=0','_blank');
                  }})()">{escape(_t(language, "Chat With Us on WhatsApp", "Chatea con Nosotros por WhatsApp"))} &rarr;</button>
        </form>
      </section>

    </main>
    """

    return _layout(language=language,
                   current_path=current_path,
                   title=_t(language,
                            f"{settings.website_name} | Deploy AI-Powered MVPs in Minutes",
                            f"{settings.website_name} | Despliega MVPs con IA en Minutos"),
                   description=description,
                   body_html=body_html,
                   user_summary=user_summary,
                   jsonld=[{"@context": "https://schema.org",
                            "@type": "SoftwareApplication",
                            "name": settings.website_name,
                            "applicationCategory": "BusinessApplication",
                            "operatingSystem": "Web",
                            }],
                   )
