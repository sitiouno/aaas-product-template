"""Public landing page HTML generation."""

from __future__ import annotations

from html import escape
from typing import Any

from .renderer_components import _t, layout_html


def render_landing_html(
    language: str,
    current_path: str,
    user_summary: dict[str, Any] | None,
    settings: Any | None = None,
) -> str:
    if settings is None:
        from .config import load_settings
        settings = load_settings()

    name = settings.website_name
    tagline_en = settings.website_tagline_en
    tagline_es = settings.website_tagline_es
    desc_en = settings.product_description or tagline_en
    desc_es = settings.product_description_es or tagline_es
    cta_en = settings.product_cta_en
    cta_es = settings.product_cta_es

    description = _t(language, desc_en, desc_es)

    body_html = f"""
    <main class="landing-grid">

      <!-- HERO -->
      <section class="hero-panel" style="padding: 4rem 2rem; text-align: center; max-width: 900px; margin: 0 auto;">
        <div class="hero-copy">
          <p class="eyebrow" style="font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 1rem;">{escape(name)}</p>
          <h1 style="font-size: 3rem; line-height: 1.1; margin-bottom: 1.5rem; letter-spacing: -0.02em; font-weight: 800;">{escape(_t(language, tagline_en, tagline_es))}</h1>
          <p class="hero-text" style="font-size: 1.25rem; color: var(--text-secondary); margin-bottom: 2.5rem; max-width: 800px; margin-left: auto; margin-right: auto;">{escape(description)}</p>
          <div class="hero-actions" style="display: flex; gap: 1rem; justify-content: center; align-items: center; margin-bottom: 3rem;">
            <a class="primary-button" style="padding: 0.8rem 1.5rem; font-size: 1.1rem;" href="/{language}/app">{escape(_t(language, cta_en, cta_es))}</a>
            <a class="ghost-link" style="font-weight: 600;" href="/docs">{escape(_t(language, "API Docs", "Docs de API"))} &rarr;</a>
          </div>
        </div>
      </section>

      <!-- FEATURES -->
      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{escape(_t(language, "What You Get", "Lo Que Obtienes"))}</p>
            <h2>{escape(_t(language, "Everything Included", "Todo Incluido"))}</h2>
          </div>
        </div>
        <div class="step-grid" style="grid-template-columns: repeat(4, minmax(0, 1fr));">
          <article>
            <strong>{escape(_t(language, "AI Agent Pipeline", "Pipeline de Agentes IA"))}</strong>
            <p>{escape(_t(language, "Multi-agent orchestration powers the core research and analysis workflows.", "Orquestacion multi-agente impulsa los flujos de trabajo de investigacion y analisis."))}</p>
          </article>
          <article>
            <strong>{escape(_t(language, "REST API & Webhooks", "API REST y Webhooks"))}</strong>
            <p>{escape(_t(language, "Full REST API with API key auth, rate limiting, and webhook notifications.", "API REST completa con autenticacion por API key, rate limiting y notificaciones webhook."))}</p>
          </article>
          <article>
            <strong>{escape(_t(language, "MCP Server", "Servidor MCP"))}</strong>
            <p>{escape(_t(language, "Connect to Claude, Cursor, or any MCP-compatible client for AI-native integration.", "Conecta con Claude, Cursor o cualquier cliente compatible MCP para integracion AI-nativa."))}</p>
          </article>
          <article>
            <strong>{escape(_t(language, "Credit-Based Billing", "Facturacion por Creditos"))}</strong>
            <p>{escape(_t(language, "Pay-per-use with Stripe. Buy credits, track usage, and manage billing.", "Pago por uso con Stripe. Compra creditos, rastrea uso y gestiona facturacion."))}</p>
          </article>
        </div>
      </section>

      <!-- HOW IT WORKS -->
      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{escape(_t(language, "How It Works", "Como Funciona"))}</p>
            <h2>{escape(_t(language, "Simple 3-Step Process", "Proceso Simple de 3 Pasos"))}</h2>
          </div>
        </div>
        <div class="step-grid">
          <article style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">1</div>
            <strong>{escape(_t(language, "Sign Up", "Registrate"))}</strong>
            <p>{escape(_t(language, "Create your account and get free credits to start.", "Crea tu cuenta y recibe creditos gratis para comenzar."))}</p>
          </article>
          <article style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">2</div>
            <strong>{escape(_t(language, "Submit Your Request", "Envia Tu Solicitud"))}</strong>
            <p>{escape(_t(language, "Describe what you need. AI agents process your request and deliver results.", "Describe lo que necesitas. Los agentes de IA procesan tu solicitud y entregan resultados."))}</p>
          </article>
          <article style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">3</div>
            <strong>{escape(_t(language, "Get Results", "Recibe Resultados"))}</strong>
            <p>{escape(_t(language, "Review your results, download reports, and integrate via API.", "Revisa tus resultados, descarga reportes e integra via API."))}</p>
          </article>
        </div>
      </section>

      <!-- GET STARTED -->
      <section class="panel" id="get-started" style="margin-top: 1rem;">
        <div style="max-width: 700px; margin: 0 auto; text-align: center;">
          <p class="eyebrow">{escape(_t(language, "Ready?", "Listo?"))}</p>
          <h2>{escape(_t(language, f"Start Using {name}", f"Empieza a Usar {name}"))}</h2>
          <p class="hero-text" style="margin-bottom: 32px; font-size: 1.1rem;">{escape(description)}</p>
          <a class="primary-button" style="padding: 0.9rem 2.5rem; font-size: 1.15rem;" href="/{language}/app">{escape(_t(language, cta_en, cta_es))}</a>
        </div>
      </section>

      <!-- CONTACT -->
      <section class="panel" style="text-align: center;">
        <p class="eyebrow">{escape(_t(language, "Questions?", "Preguntas?"))}</p>
        <h2>{escape(_t(language, "Get in Touch", "Contactanos"))}</h2>
        <p class="hero-text" style="max-width: 600px; margin: 0 auto 24px; font-size: 1.05rem;">{escape(_t(language, "Have questions or need a custom solution? We're here to help.", "Tienes preguntas o necesitas una solucion personalizada? Estamos para ayudarte."))}</p>
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
                    var msg='Hi, I\\'m '+n+' ('+e+'). I\\'m interested in {escape(name)}. Can you help me?';
                    window.open('https://api.whatsapp.com/send/?phone=14159435393&text='+encodeURIComponent(msg)+'&type=phone_number&app_absent=0','_blank');
                  }})()">{escape(_t(language, "Chat With Us on WhatsApp", "Chatea con Nosotros por WhatsApp"))} &rarr;</button>
        </form>
      </section>

    </main>
    """

    return layout_html(
        language=language,
        current_path=current_path,
        title=_t(
            language,
            f"{name} | {tagline_en}",
            f"{name} | {tagline_es}",
        ),
        description=description,
        body_html=body_html,
        user_summary=user_summary,
        settings=settings,
        jsonld=[
            {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "name": name,
                "applicationCategory": "BusinessApplication",
                "operatingSystem": "Web",
            }
        ],
    )
