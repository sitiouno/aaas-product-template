"""Authenticated workspace shell with sidebar nav and section containers."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from .renderer_components import _t


def _css_includes() -> str:
    files = [
        "css/theme.css", "css/base.css", "css/layout.css",
        "css/components.css", "css/overlays.css", "css/sections.css",
        "css/workspace.css", "css/results.css", "css/landing.css",
        "css/responsive.css",
    ]
    return "\n".join(f'    <link rel="stylesheet" href="/static/{f}">' for f in files)


def _owner_sidebar_nav(language: str) -> str:
    return f"""
          <nav class="workspace-nav">
            <a href="#dashboard" data-section="dashboard" data-view="workspace-dashboard" class="is-active">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
              {escape(_t(language, 'Dashboard', 'Panel'))}
            </a>
            <a href="#getting-started" data-section="getting-started" data-view="workspace-getting-started">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 8 12 12 14 14"/></svg>
              {escape(_t(language, 'Getting Started', 'Comenzar'))}
            </a>
            <a href="#how-it-works" data-section="how-it-works" data-view="workspace-how-it-works">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
              {escape(_t(language, 'How It Works', 'Como Funciona'))}
            </a>
            <a href="#agent-factory" data-section="agent-factory" data-view="workspace-agent-factory" class="nav-disabled" aria-disabled="true" tabindex="-1">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
              {escape(_t(language, 'Agent Factory', 'Fabrica de Agentes'))}
              <span class="nav-badge-soon">{escape(_t(language, 'Soon', 'Pronto'))}</span>
            </a>
            <div class="nav-separator"></div>
            <a href="#api" data-section="api" data-view="workspace-api">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
              {escape(_t(language, 'API & MCP', 'API y MCP'))}
            </a>
            <a href="#account" data-section="account" data-view="workspace-account">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              {escape(_t(language, 'My Account', 'Mi Cuenta'))}
            </a>
            <a href="#billing" data-section="billing" data-view="workspace-billing">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
              {escape(_t(language, 'Billing', 'Facturacion'))}
            </a>
            <a href="#admin" data-section="admin" data-view="workspace-admin" id="nav-admin">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              {escape(_t(language, 'Admin', 'Admin'))}
            </a>
          </nav>"""


def _user_sidebar_nav(language: str) -> str:
    return f"""
          <nav class="workspace-nav">
            <a href="#dashboard" data-section="dashboard" data-view="workspace-dashboard" class="is-active">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
              {escape(_t(language, 'Dashboard', 'Panel'))}
            </a>
            <a href="#components" data-section="components" data-view="workspace-components">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
              {escape(_t(language, 'Components', 'Componentes'))}
            </a>
            <div class="nav-separator"></div>
            <a href="#api" data-section="api" data-view="workspace-api">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
              {escape(_t(language, 'API & MCP', 'API y MCP'))}
            </a>
            <a href="#account" data-section="account" data-view="workspace-account">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              {escape(_t(language, 'My Account', 'Mi Cuenta'))}
            </a>
            <a href="#billing" data-section="billing" data-view="workspace-billing">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
              {escape(_t(language, 'Billing', 'Facturacion'))}
            </a>
          </nav>"""


def _section_containers() -> str:
    return """
<section id="workspace-dashboard" class="workspace-section" style="display:none"></section>
<section id="workspace-getting-started" class="workspace-section" style="display:none"></section>
<section id="workspace-how-it-works" class="workspace-section" style="display:none"></section>
<section id="workspace-agent-factory" class="workspace-section" style="display:none"></section>
<section id="workspace-components" class="workspace-section" style="display:none"></section>
<section id="workspace-api" class="workspace-section" style="display:none"></section>
<section id="workspace-account" class="workspace-section" style="display:none"></section>
<section id="workspace-billing" class="workspace-section" style="display:none"></section>
<section id="workspace-admin" class="workspace-section" style="display:none"></section>"""


def render_workspace_html(
    language: str,
    current_path: str,
    user_summary: dict[str, Any] | None,
    settings: Any | None = None,
) -> str:
    if settings is None:
        from .config import load_settings
        settings = load_settings()

    base_url = settings.public_base_url
    account_payload = user_summary or {"authenticated": False, "api_keys": []}

    is_owner = bool(
        user_summary
        and user_summary.get("authenticated")
        and user_summary.get("email") == settings.admin_email
    )

    page_state = json.dumps(
        {
            "appContext": "workspace",
            "language": language,
            "baseUrl": base_url,
            "devAuthEnabled": settings.enable_dev_auth,
            "productName": settings.product_name,
            "productDomain": settings.product_domain,
            "unlockProtected": settings.unlock_protected,
        },
        ensure_ascii=True,
    )

    sidebar_nav = _owner_sidebar_nav(language) if is_owner else _user_sidebar_nav(language)
    sidebar_title = escape(settings.product_name or settings.website_name)

    return f"""<!DOCTYPE html>
<html lang="{language}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(settings.website_name)} | Workspace</title>
    <meta name="robots" content="noindex,nofollow" />
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />
{_css_includes()}
    <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.30.4/dist/cytoscape.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/layout-base@2.0.1/layout-base.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/cose-base@2.2.0/cose-base.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/cytoscape-cose-bilkent@4.1.0/cytoscape-cose-bilkent.js"></script>
    <script>window.__QUIEN_PAGE__ = {page_state};</script>
    <script>window.__QUIEN_ACCOUNT__ = {json.dumps(account_payload, ensure_ascii=True)};</script>
    <script type="module" src="/static/js/app.js"></script>
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
          <h2>{sidebar_title}</h2>
          {sidebar_nav}
        </aside>

        <main class="workspace-content">
{_section_containers()}
        </main>

    </div>
  </body>
</html>"""
