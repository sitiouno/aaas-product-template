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

    return layout_html(
        language=language,
        current_path=current_path,
        title=_t(
            language,
            f"{settings.website_name} | Deploy AI-Powered MVPs in Minutes",
            f"{settings.website_name} | Despliega MVPs con IA en Minutos",
        ),
        description=description,
        body_html=body_html,
        user_summary=user_summary,
        settings=settings,
        jsonld=[
            {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "name": settings.website_name,
                "applicationCategory": "BusinessApplication",
                "operatingSystem": "Web",
            }
        ],
    )
