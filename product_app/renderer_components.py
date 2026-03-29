"""Shared HTML components: auth modal, user badge, language switch, layout wrapper."""

from __future__ import annotations

import json
import os
import time
from html import escape
from typing import Any


def _t(language: str, english: str, spanish: str) -> str:
    return spanish if language == "es" else english


def _lang_href(base_url: str, language: str, path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{path}" if path != "/" else base_url


def _nav_items(language: str) -> tuple[tuple[str, str], ...]:
    return ()


def auth_modal_html(language: str) -> str:
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


def user_badge_html(language: str, user_summary: dict[str, Any] | None) -> str:
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


def language_switch_html(language: str, current_path: str) -> str:
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


def layout_html(
    *,
    language: str,
    current_path: str,
    title: str,
    description: str,
    body_html: str,
    user_summary: dict[str, Any] | None,
    settings: Any,
    jsonld: list[dict[str, Any]] | None = None,
) -> str:
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
        f'<a href="{escape(path)}">{escape(label)}</a>'
        for label, path in _nav_items(language)
    )
    alternate_html = "".join(
        f'<link rel="alternate" hreflang="{escape(code)}" href="{escape(url)}" />'
        for code, url in alternates
    )
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
          {language_switch_html(language, current_path)}
          {user_badge_html(language, user_summary)}
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
    {auth_modal_html(language)}
  </body>
</html>"""
