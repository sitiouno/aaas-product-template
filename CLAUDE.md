# [Product Name]

## What This Is
An AaaS (Agents as a Service) product built on the MVP Factory template.
Users interact via web UI or API, triggering ADK agent pipelines that do specialized work.

## Key Files
- `product_app/webapp.py` — FastAPI application (routes, auth, billing)
- `product_app/config.py` — Environment configuration
- `product_app/models.py` — SQLAlchemy database models
- `product_app/service.py` — Pipeline execution engine
- `product_app/research/base.py` — Abstract base for agent styles
- `product_app/research/registry.py` — Auto-discovery registry
- `product_app/research/hello_world.py` — Sample agent (replace with yours)
- `product_app/site_renderer.py` — Server-rendered HTML pages
- `product_app/security.py` — Auth (magic link, sessions, API keys)
- `product_app/stripe_billing.py` — Stripe billing

## How to Add Agents
1. Create `product_app/research/my_style.py`
2. Subclass `ResearchStyleBase`
3. Implement `build_pipeline()`, `get_stages()`, `get_section_titles()`
4. End with `STYLE = MyStyle()`
5. Auto-discovered on startup

## Patterns
- Bilingual: `_t(language, english, spanish)` in site_renderer
- Auth: magic link OTP → session cookie
- Billing: credit-based ($1/credit) via Stripe
- Progress: SSE streaming from pipeline stages
- Config: all via env vars in config.py

## Testing
pytest tests/ -v

## Local Dev
PRODUCT_ENABLE_DEV_AUTH=true python -m product_app.webapp

## Deploy
Push to main → GitHub Actions → Cloud Run
