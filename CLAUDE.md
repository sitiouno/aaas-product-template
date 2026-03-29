# AaaS Product Template

## What This Is
An AaaS (Agents as a Service) product built on the MVP Factory template.
Users interact via web UI or API, triggering ADK agent pipelines that do specialized work.
The owner customizes this template via vibe coding in their IDE.

## Architecture Rules

### File Size & Modularity
- **Maximum 600 lines per file** — no exceptions
- Split by responsibility: one file = one purpose
- Prefer small, focused modules over large multi-purpose files
- If a file approaches 500 lines, plan the split proactively

### JavaScript Structure
```
static/js/
  app.js          — Boot, routing, global state (<200 lines)
  dashboard.js    — Dashboard section
  getting-started.js — Vibe coding guide
  how-it-works.js — Agent pipeline docs
  admin.js        — Admin panel
  billing.js      — Credits & Stripe
  api-section.js  — API keys & MCP
  auth.js         — Magic link authentication
  runner.js       — Pipeline execution & SSE
  utils.js        — Shared utilities
  report-viewer.js — Results display
  renderers.js    — Output rendering
```

### CSS Structure
```
static/css/
  theme.css       — CSS variables, colors, typography
  layout.css      — Workspace shell, sidebar, grid
  components.css  — Buttons, cards, forms, modals, toasts
  sections.css    — Section-specific styles
```

### Python Structure
```
product_app/
  webapp.py          — FastAPI routes (split if >600 lines)
  site_renderer.py   — HTML generation (split into partials)
  config.py          — Environment configuration
  models.py          — SQLAlchemy models
  service.py         — Pipeline execution
  security.py        — Auth (magic link, sessions, API keys)
  persistence.py     — Database CRUD
  stripe_billing.py  — Stripe integration
  research/
    base.py          — Abstract ResearchStyleBase
    registry.py      — Auto-discovery registry
    hello_world.py   — Sample agent
```

## Code Quality Standards

### Security
- Never expose secrets in client-side code
- Validate all user input at system boundaries
- Use parameterized queries (SQLAlchemy handles this)
- Sanitize HTML output to prevent XSS
- API keys: show prefix only, hash stored values
- CSRF protection on state-changing endpoints

### Clean Code
- Functions: max 30 lines, single responsibility
- No dead code — delete unused code, don't comment it out
- No magic numbers — use named constants
- Descriptive names: `loadDashboardStats()` not `load()`
- DRY: extract shared logic, but don't abstract prematurely
- YAGNI: don't build for hypothetical requirements

### Error Handling
- Handle errors at system boundaries (API calls, user input)
- Trust internal code and framework guarantees
- User-facing errors: clear, actionable messages
- Log errors server-side with context

### Testing
- `pytest tests/ -v` — run before every commit
- Test behavior, not implementation
- New features need tests; bug fixes need regression tests

## Protected Sections
Admin/system sections (site_renderer partials) have readonly protection.
The owner must explicitly unlock to modify these — prevents accidental template damage.
Protected: Admin panel, Billing integration, Security/Auth, Database models.

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

## Local Dev
```bash
PRODUCT_ENABLE_DEV_AUTH=true python -m product_app.webapp
```

## Deploy
Push to main → GitHub Actions → Cloud Run
