# Template Workspace Redesign — Design Spec

## Goal

Transform the aaas-product-template from a Research Lab copy into a purpose-built product workspace that guides the owner through vibe coding customization, while providing regular users a clean simplified experience.

## Architecture

Modular rebuild: split all monolithic files (app.js 1,833 lines, app.css 3,039 lines, site_renderer.py ~900 lines) into focused modules under 600 lines each. The template is what the owner modifies with vibe coding — small, focused files make that experience dramatically better.

## Tech Stack

- Python/FastAPI (backend, server-rendered HTML)
- Vanilla JS with ES modules (`<script type="module">`, dynamic `import()`)
- CSS custom properties with file-per-concern splitting
- Existing: SQLAlchemy, Stripe, ADK pipelines, SSE streaming

---

## 1. Workspace Sections by Role

### Owner (Admin) Sees

| Section | Purpose |
|---------|---------|
| **Dashboard** | Product status, URL, agent count, quick actions, getting started progress preview |
| **Getting Started** | 5-step vibe coding guide with progress tracker, component gallery, prompt examples |
| **How It Works** | Default agent pipeline documented, sequential vs parallel explained, didactic example |
| **Agent Factory** | Placeholder "Coming Soon" — implemented in future phase C |
| **API & MCP** | API key management, endpoints, webhook config |
| **My Account** | Profile, preferences |
| **Billing** | Credit balance, Stripe checkout, invoices |
| **Admin** | User management, access requests, usage analytics, revenue |

### Regular User Sees

| Section | Purpose |
|---------|---------|
| **Dashboard** | Credits, API call count, available services |
| **Components** | Owner-created custom sections shown as service cards; defaults to sample placeholders until owner adds real content via vibe coding |
| **API & MCP** | Personal API key |
| **My Account** | Profile |
| **Billing** | Credit balance, purchase |

### Visibility Logic

Sections are shown/hidden based on `is_admin` flag from `window.__QUIEN_ACCOUNT__`. The sidebar renders different nav items per role. Admin-only sections: Getting Started, How It Works, Agent Factory, Admin.

---

## 2. Dashboard

### Owner Dashboard
- **Stats row**: Product status (Active/Inactive), Product URL (`slug.x53.ai`), Agent count
- **Quick actions**: Open IDE, View Docs, API Keys — gradient primary button + secondary buttons
- **Getting Started preview**: Progress bar (X of 5 complete) with link to full guide, dashed border highlight

### Regular User Dashboard
- **Stats row**: Credits remaining, API calls made
- **Available services**: Card list of active agents with name, description, credit cost
- **Placeholder components**: Dimmed cards showing "Customize via vibe coding" for owner-added sections

---

## 3. Getting Started Guide

Owner-only section. Collapsible step-by-step onboarding.

### Steps
1. **Explore your workspace** — Auto-completes on first visit
2. **Check How It Works** — Auto-completes when owner visits How It Works section
3. **Get your API key** — Auto-completes when owner creates first API key
4. **Open in your IDE & customize** — Manual completion. Expandable with:
   - Clone command (`git clone` + `cursor .` / `code .`)
   - 3 example prompts: add chat interface, customize landing page, add new agent
5. **Deploy and go live** — Manual completion. Shows `git push` command + explains CI/CD

### Progress Tracking
- Progress stored in `localStorage` keyed by user ID
- Progress bar at top: "X of 5 complete"
- Completed steps show green checkmark, collapsed
- Current step highlighted with blue border, expanded
- Pending steps dimmed with number indicator

### Component Gallery
Below the steps. Grid of 6 visual placeholder components:
- **Card** — wireframe card with title + body
- **Chat Window** — message bubbles + input field
- **Data Table** — header + rows wireframe
- **Form** — labels + inputs + submit button
- **Chart / Graph** — bar chart wireframe
- **Map / Location** — map container with pin

Each placeholder includes a suggested prompt snippet: `"Add a card grid showing..."`, `"Add a chat interface for..."`, etc.

---

## 4. How It Works

Owner-only section. Agent pipeline documentation.

### Default Agent Card
- **Hello World Pipeline** displayed as canonical (immutable, badge "🔒 Canonical")
- Sequential pipeline diagram: Research Agent → Report Agent → Final Report
- Metadata: 2 agents, 1 credit, 1-2 min estimated duration
- Status badge: Active

### Pipeline Types (Didactic)
Side-by-side explanation:
- **Sequential**: A → B → C diagram. "Agents run one after another." + example prompt
- **Parallel**: A, B, C → Merge diagram. "Multiple agents run simultaneously." + example prompt

### Example Pipeline (Didactic)
Weather Forecast Product — 4-agent mixed pipeline:
- User input → [Parallel: Weather API + News Agent] → Analyst → Reporter → Report
- Shows the exact vibe coding prompt that would create this pipeline
- Marked as "Example" — not an actual running agent

### Agent Cards (Dynamic)
When the owner creates agents (via vibe coding or future Agent Factory), each gets a card in this section with:
- Name, description, status (Active/Inactive)
- Pipeline diagram auto-generated from `get_stages()`
- Metadata: agent count, credit cost, estimated duration
- User-created agents marked as "Custom" (editable), vs "Canonical" (factory defaults, immutable)

---

## 5. Readonly Protection

### UI Level (Runtime)
Protected sections render with:
- **Locked state** (default): Content dimmed (opacity 0.6), actions disabled, yellow "🔒 Protected" badge, warning banner explaining how to unlock
- **Unlocked state**: Red "🔓 Unlocked — Edit with caution" badge, red warning banner, full interactivity

### Unlock Mechanism
Environment variable: `UNLOCK_PROTECTED=true` in `.env` file. The backend reads this and passes `protectedUnlocked: true/false` in `window.__QUIEN_PAGE__`. JS checks this flag before enabling protected section interactivity.

### Code Level (Vibe Coding)
Protected files listed in CLAUDE.md, AGENTS.md, and .cursorrules:
- `product_app/security.py` — Authentication system
- `product_app/models.py` — Database schema
- `product_app/stripe_billing.py` — Billing integration
- `product_app/database.py` — Database connection

AI coding assistants are instructed not to modify these files unless the owner explicitly requests an unlock.

### Protected UI Sections
- Admin panel (user management, analytics)
- Billing integration settings
- API key internal logic

---

## 6. Modular File Architecture

### JavaScript: `static/js/`

| File | Responsibility | Est. Lines |
|------|---------------|-----------|
| `app.js` | Boot sequence, hash routing, global state, section lazy-loading | ~120 |
| `dashboard.js` | Owner/user dashboard rendering, stats, quick actions | ~150 |
| `getting-started.js` | Step tracker, progress persistence, component gallery | ~200 |
| `how-it-works.js` | Pipeline diagrams, agent cards, didactic examples | ~180 |
| `admin.js` | User management, access requests, analytics, revenue | ~250 |
| `billing.js` | Credit balance, Stripe checkout, invoice history | ~120 |
| `api-section.js` | API key CRUD, webhook config, MCP endpoints | ~100 |
| `auth.js` | Magic link flow (exists, keep as-is) | existing |
| `runner.js` | Pipeline execution, SSE streaming, task queue (exists, keep) | existing |
| `utils.js` | Shared helpers, API fetch wrapper, toast system (exists, keep) | existing |
| `report-viewer.js` | Results display (exists, keep) | existing |
| `renderers.js` | Output rendering (exists, keep) | existing |

**Loading**: `app.js` loaded as `<script type="module">`. Section modules loaded via dynamic `import()` on first navigation to that section.

### CSS: `static/css/`

| File | Responsibility | Est. Lines |
|------|---------------|-----------|
| `theme.css` | CSS custom properties, colors, typography scale | ~100 |
| `base.css` | Reset, base element styles, utility classes | ~120 |
| `layout.css` | Workspace shell, sidebar, content grid, responsive shell | ~200 |
| `components.css` | Buttons, cards, forms, inputs, modals, toasts, tables, progress bars | ~350 |
| `sections.css` | Dashboard, getting-started, how-it-works, admin specific styles | ~300 |
| `landing.css` | Marketing/public landing page styles | ~250 |
| `responsive.css` | Media queries, mobile sidebar, hamburger menu | ~200 |

**Loading**: All CSS files loaded in `<head>` in cascade order: theme → base → layout → components → sections → landing → responsive.

### Python: `product_app/`

| File | Responsibility | Est. Lines |
|------|---------------|-----------|
| `site_renderer.py` | Entry points (`render_landing`, `render_app_shell`), `_layout()` wrapper, CSS/JS inclusion | ~200 |
| `renderer_landing.py` | Public landing page HTML generation | ~250 |
| `renderer_workspace.py` | Authenticated workspace shell, section containers, sidebar nav | ~300 |
| `renderer_components.py` | Shared components: auth modal, user badge, language switch, nav items | ~150 |

**Loading**: `site_renderer.py` imports from sub-modules. `webapp.py` only imports from `site_renderer.py` — public API unchanged.

---

## 7. Sidebar Navigation

### Owner Sidebar
```
🚀 [Product Name]
─────────────────
📊 Dashboard
🎯 Getting Started
⚙️ How It Works
🤖 Agent Factory  [Soon]
─────────────────
🔑 API & MCP
👤 My Account
💳 Billing
🛡️ Admin
```

### Regular User Sidebar
```
🚀 [Product Name]
─────────────────
📊 Dashboard
🧩 Components
─────────────────
🔑 API & MCP
👤 My Account
💳 Billing
```

Product name comes from `window.__QUIEN_PAGE__.productName` (config.py `PRODUCT_NAME` env var).

---

## 8. Landing Page

Keep the existing bilingual landing page structure but update content to reflect the specific product (not Factory/Research Lab). The landing page uses `renderer_landing.py` and `css/landing.css`.

Key changes:
- Replace Factory-specific copy with generic product copy
- Keep: auth modal (magic link), hreflang tags, SEO meta, language switcher
- Product name and description from config env vars

---

## 9. What Gets Removed

From the current template (Research Lab residue):
- **Style picker grid** — no more selecting from 6 research styles
- **Research submission form** — textarea prompt replaced by section-specific UIs
- **PIPELINE_INFO hardcoded** — replaced by dynamic agent cards from registry
- **History table** — removed (products don't have a run history list, they have agent interactions)
- **Research-specific copy** — "Due Diligence", "Company Deep Dive", etc.

---

## 10. Config Environment Variables

New env vars for the template:
- `PRODUCT_NAME` — Display name in sidebar and landing (default: "My Product")
- `PRODUCT_DESCRIPTION` — Landing page description
- `PRODUCT_DOMAIN` — Custom domain if configured (e.g., `myproduct.x53.ai`)
- `UNLOCK_PROTECTED` — `true` to unlock protected sections (default: unset/false)

These are read in `config.py` and passed to renderers via the existing config pattern.
