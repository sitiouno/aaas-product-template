# Template Workspace Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the aaas-product-template from a Research Lab copy into a modular, purpose-built product workspace with vibe coding guide, agent docs, component gallery, and readonly protection.

**Architecture:** Modular rebuild — split 3 monolithic files (app.js 1,833 lines, app.css 3,039 lines, site_renderer.py 800 lines) into focused modules <600 lines each. New workspace sections replace Research Lab residue. Role-based visibility (owner vs regular user). Readonly protection on system-critical sections.

**Tech Stack:** Python/FastAPI, Vanilla JS ES modules with dynamic import(), CSS custom properties, SQLAlchemy, Stripe, ADK pipelines, SSE streaming.

**IMPORTANT RULE:** Maximum 600 lines per file. No exceptions. Split by responsibility.

---

## File Structure

### New files to create:
```
product_app/
  renderer_landing.py      — Public landing page HTML (~250 lines)
  renderer_workspace.py    — Workspace shell, sidebar, section containers (~300 lines)
  renderer_components.py   — Auth modal, user badge, nav items, language switch (~150 lines)
  static/
    css/
      theme.css            — CSS variables, colors, typography scale (~100 lines)
      base.css             — Reset, base elements, utility classes (~150 lines)
      layout.css           — Workspace shell, sidebar, content grid (~200 lines)
      components.css       — Buttons, forms, cards, modals, toasts, tables (~500 lines)
      sections.css         — Dashboard, getting-started, how-it-works, admin (~400 lines)
      landing.css          — Marketing page styles (~300 lines)
      responsive.css       — Media queries, mobile (~250 lines)
    js/
      dashboard.js         — Owner/user dashboard (~150 lines)
      getting-started.js   — Step tracker, component gallery (~200 lines)
      how-it-works.js      — Pipeline docs, agent cards, diagrams (~200 lines)
      admin.js             — User management, analytics (~250 lines)
      billing.js           — Credits, Stripe checkout (~150 lines)
      api-section.js       — API keys, webhooks, MCP (~120 lines)
      account.js           — Profile, preferences (~120 lines)
tests/
  test_renderer_split.py   — Tests for renderer module split (~80 lines)
```

### Files to modify:
```
product_app/
  config.py               — Add PRODUCT_NAME, PRODUCT_DOMAIN, UNLOCK_PROTECTED env vars
  site_renderer.py        — Slim down to entry points + imports from sub-modules (~200 lines)
  static/
    app.js                — Slim down to boot + routing + lazy loading (~150 lines)
    app.css               — DELETE (replaced by css/ modules)
tests/
  test_site_renderer.py   — Update for new renderer structure
```

### Files to keep unchanged:
```
product_app/static/js/auth.js       — 328 lines, magic link (keep as-is)
product_app/static/js/runner.js     — 152 lines, SSE + tasks (keep as-is)
product_app/static/js/utils.js      — 124 lines, helpers (keep as-is)
product_app/static/js/renderers.js  — 150 lines, snapshot rendering (keep as-is)
product_app/static/js/report-viewer.js  — 111 lines (keep as-is)
product_app/static/js/evidence-board.js — 297 lines (keep as-is)
product_app/static/js/graph-viewer.js   — 415 lines (keep as-is)
```

---

### Task 1: Config — Add product identity and protection env vars

**Files:**
- Modify: `product_app/config.py`
- Test: `tests/test_config_new_vars.py`

**Context:** The Settings dataclass in config.py (line 57) holds all env-driven configuration. `load_settings()` (line 127) reads os.environ. We need 4 new fields: PRODUCT_NAME, PRODUCT_DESCRIPTION, PRODUCT_DOMAIN, UNLOCK_PROTECTED. These are consumed by the renderers to personalize the workspace.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_new_vars.py`:

```python
from __future__ import annotations

import os
import unittest
from unittest.mock import patch


class ConfigNewVarsTest(unittest.TestCase):
    def test_product_name_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRODUCT_NAME", None)
            from product_app.config import load_settings
            import importlib, product_app.config
            importlib.reload(product_app.config)
            from product_app.config import load_settings
            s = load_settings()
            self.assertEqual(s.product_name, "My Product")

    def test_product_name_from_env(self) -> None:
        with patch.dict(os.environ, {"PRODUCT_NAME": "Weather Pro"}):
            from product_app.config import load_settings
            import importlib, product_app.config
            importlib.reload(product_app.config)
            from product_app.config import load_settings
            s = load_settings()
            self.assertEqual(s.product_name, "Weather Pro")

    def test_unlock_protected_default_false(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UNLOCK_PROTECTED", None)
            from product_app.config import load_settings
            import importlib, product_app.config
            importlib.reload(product_app.config)
            from product_app.config import load_settings
            s = load_settings()
            self.assertFalse(s.unlock_protected)

    def test_unlock_protected_true(self) -> None:
        with patch.dict(os.environ, {"UNLOCK_PROTECTED": "true"}):
            from product_app.config import load_settings
            import importlib, product_app.config
            importlib.reload(product_app.config)
            from product_app.config import load_settings
            s = load_settings()
            self.assertTrue(s.unlock_protected)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_new_vars.py -v`
Expected: FAIL — `AttributeError: 'Settings' has no attribute 'product_name'`

- [ ] **Step 3: Add new fields to Settings dataclass and load_settings()**

In `product_app/config.py`, add these fields to the Settings dataclass (after `webhook_retry_max`):

```python
    # Product identity
    product_name: str = "My Product"
    product_description: str = ""
    product_domain: str = ""
    unlock_protected: bool = False
```

In `load_settings()`, add before the `return Settings(` call, read the env vars:

```python
    product_name = os.environ.get("PRODUCT_NAME", "My Product")
    product_description = os.environ.get("PRODUCT_DESCRIPTION", "")
    product_domain = os.environ.get("PRODUCT_DOMAIN", "")
    unlock_protected = _as_bool(os.environ.get("UNLOCK_PROTECTED"), False)
```

And pass them into the Settings constructor:

```python
    product_name=product_name,
    product_description=product_description,
    product_domain=product_domain,
    unlock_protected=unlock_protected,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_new_vars.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add product_app/config.py tests/test_config_new_vars.py
git commit -m "feat: add product identity and protection config vars"
```

---

### Task 2: Split CSS monolith into modules

**Files:**
- Create: `product_app/static/css/theme.css`
- Create: `product_app/static/css/base.css`
- Create: `product_app/static/css/layout.css`
- Create: `product_app/static/css/components.css`
- Create: `product_app/static/css/sections.css`
- Create: `product_app/static/css/landing.css`
- Create: `product_app/static/css/responsive.css`
- Delete: `product_app/static/app.css` (after migration)

**Context:** The current `app.css` is 3,039 lines. We split it by concern into 7 files, each under 600 lines. The CSS is purely structural — no JS behavior changes. The split boundaries are based on the section analysis:
- Lines 1-100: CSS variables → `theme.css`
- Lines 101-250: Reset, typography → `base.css`
- Lines 251-450: Workspace shell, sidebar → `layout.css`
- Lines 451-1300: Modals, toasts, task queue, cards, forms, buttons → `components.css`
- Lines 1301-2200: Dashboard stats, results, artifacts, visualizations → `sections.css`
- Lines 2201-2600: Marketing shell, site header, hero → `landing.css`
- Lines 2601-3039: Media queries → `responsive.css`

- [ ] **Step 1: Create the css/ directory**

```bash
mkdir -p product_app/static/css
```

- [ ] **Step 2: Split app.css into theme.css**

Extract lines 1-100 from `app.css` (the `:root` block and color variables) into `product_app/static/css/theme.css`. Add a header comment:

```css
/* theme.css — CSS custom properties, colors, typography scale */
```

Keep all `--bg-*`, `--text-*`, `--accent-*`, `--border-*`, `--shadow-*`, `--radius-*` variables.

- [ ] **Step 3: Split app.css into base.css**

Extract lines 101-250 (reset, `*` box-sizing, body, html, typography, `a`, `code`, `pre` styles) into `product_app/static/css/base.css`. Add header:

```css
/* base.css — Reset, base element styles, utility classes */
```

- [ ] **Step 4: Split app.css into layout.css**

Extract lines 251-450 (`.workspace-shell`, `.workspace-sidebar`, `.workspace-nav`, `.workspace-main`, sidebar nav items, hamburger) into `product_app/static/css/layout.css`. Add header:

```css
/* layout.css — Workspace shell, sidebar, content grid */
```

- [ ] **Step 5: Split app.css into components.css**

Extract lines 451-1300 (`.modal-*`, `.toast-*`, `.task-queue-*`, `.style-card`, `.product-card`, `.panel`, `.primary-button`, `.field-label`, `.form-footer`, all form elements) into `product_app/static/css/components.css`. Add header:

```css
/* components.css — Buttons, forms, cards, modals, toasts, tables, progress */
```

If this exceeds 600 lines, split further: remove visualization-specific card styles (`.rv-*`, `.artifact-*`) and move them to sections.css.

- [ ] **Step 6: Split app.css into sections.css**

Extract lines 1301-2200 (`.stat-card`, `.stat-*` variants, results rendering, artifact grid, visualization styles, and add new section-specific styles for getting-started, how-it-works placeholders) into `product_app/static/css/sections.css`. Add header:

```css
/* sections.css — Dashboard, getting-started, how-it-works, admin, results */
```

If this exceeds 600 lines, split visualization styles (`.rv-*` report viewer, evidence board, graph) into a separate `visualizations.css`.

- [ ] **Step 7: Split app.css into landing.css**

Extract lines 2201-2600 (`.marketing-shell`, `.site-header`, `.brand-lockup`, `.hero-*`, footer, landing-specific elements) into `product_app/static/css/landing.css`. Add header:

```css
/* landing.css — Marketing/public landing page styles */
```

- [ ] **Step 8: Split app.css into responsive.css**

Extract lines 2601-3039 (all `@media` queries) into `product_app/static/css/responsive.css`. Add header:

```css
/* responsive.css — Media queries, mobile sidebar, hamburger menu */
```

- [ ] **Step 9: Add new section styles to sections.css**

Append these new styles for the template-specific sections to `product_app/static/css/sections.css`:

```css
/* --- Getting Started --- */
.gs-progress-bar { background: var(--bg-secondary); border-radius: 4px; height: 8px; }
.gs-progress-fill { background: var(--accent-gradient); border-radius: 4px; height: 100%; transition: width 0.3s; }
.gs-step { background: var(--bg-card); border-radius: 8px; padding: 14px; margin-bottom: 8px; border-left: 3px solid var(--border-subtle); }
.gs-step.completed { border-left-color: var(--accent-green); }
.gs-step.current { border-left-color: var(--accent-blue); border: 1px solid rgba(37, 99, 235, 0.3); }
.gs-step.pending { opacity: 0.7; }
.gs-step-header { display: flex; justify-content: space-between; align-items: center; }
.gs-step-icon { font-size: 18px; margin-right: 10px; }
.gs-step-badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; }
.gs-step-badge.done { background: rgba(52, 211, 153, 0.1); color: var(--accent-green); }
.gs-step-badge.active { background: rgba(37, 99, 235, 0.1); color: var(--accent-blue); }
.gs-step-body { margin-top: 12px; margin-left: 28px; padding: 12px; background: var(--bg-primary); border-radius: 6px; }
.gs-prompt-card { background: var(--bg-secondary); border-radius: 4px; padding: 8px 12px; margin-bottom: 6px; }
.gs-prompt-label { color: var(--accent-amber); font-size: 11px; }
.gs-prompt-text { color: var(--text-secondary); font-size: 11px; font-style: italic; }
.gs-component-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.gs-component-card { background: var(--bg-card); border-radius: 8px; padding: 12px; border: 1px dashed var(--border-subtle); }
.gs-component-label { color: var(--accent-cyan); font-size: 11px; margin-bottom: 6px; }
.gs-component-preview { background: var(--bg-secondary); border-radius: 6px; padding: 10px; min-height: 60px; }
.gs-component-hint { color: var(--text-secondary); font-size: 11px; margin-top: 6px; }

/* --- How It Works --- */
.hiw-agent-card { background: var(--bg-card); border-radius: 8px; padding: 16px; margin-bottom: 16px; border: 1px solid var(--border-subtle); }
.hiw-agent-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.hiw-badge { font-size: 10px; padding: 3px 8px; border-radius: 4px; }
.hiw-badge.canonical { background: rgba(37, 99, 235, 0.1); color: var(--accent-blue); }
.hiw-badge.custom { background: rgba(168, 139, 250, 0.1); color: #a78bfa; }
.hiw-badge.active { background: rgba(52, 211, 153, 0.1); color: var(--accent-green); }
.hiw-pipeline-diagram { background: var(--bg-primary); border-radius: 6px; padding: 14px; display: flex; align-items: center; flex-wrap: wrap; gap: 0; justify-content: center; }
.hiw-agent-node { background: var(--bg-card); border-radius: 8px; padding: 10px 14px; text-align: center; min-width: 100px; }
.hiw-agent-node.research { border: 1px solid var(--accent-blue); }
.hiw-agent-node.report { border: 1px solid var(--accent-cyan); }
.hiw-agent-node.output { background: rgba(52, 211, 153, 0.1); border: 1px dashed var(--accent-green); }
.hiw-arrow { color: var(--border-subtle); font-size: 18px; padding: 0 6px; }
.hiw-parallel-group { border: 1px dashed var(--accent-cyan); border-radius: 8px; padding: 8px; display: flex; flex-direction: column; gap: 4px; }
.hiw-pipeline-types { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.hiw-type-card { background: var(--bg-card); border-radius: 8px; padding: 14px; }
.hiw-meta { display: flex; gap: 12px; margin-top: 10px; color: var(--text-muted); font-size: 11px; }

/* --- Readonly Protection --- */
.protected-banner { border-radius: 8px; padding: 14px; margin-bottom: 16px; }
.protected-banner.locked { background: rgba(251, 191, 36, 0.08); border: 1px solid rgba(251, 191, 36, 0.3); }
.protected-banner.unlocked { background: rgba(248, 113, 113, 0.08); border: 1px solid rgba(248, 113, 113, 0.3); }
.protected-badge { font-size: 11px; padding: 3px 10px; border-radius: 4px; }
.protected-badge.locked { background: rgba(251, 191, 36, 0.1); color: var(--accent-amber); }
.protected-badge.unlocked { background: rgba(248, 113, 113, 0.1); color: var(--accent-red); }
.protected-overlay { opacity: 0.6; pointer-events: none; }

/* --- Agent Factory placeholder --- */
.af-coming-soon { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 300px; color: var(--text-muted); }
.af-coming-soon-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.af-coming-soon-title { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
.af-coming-soon-text { font-size: 13px; max-width: 400px; text-align: center; line-height: 1.5; }
```

- [ ] **Step 10: Verify no file exceeds 600 lines**

```bash
wc -l product_app/static/css/*.css
```

If any file exceeds 600 lines, split it further. `components.css` is the most likely candidate — if it's too large, extract modal/toast styles into `overlays.css`.

- [ ] **Step 11: Delete app.css**

```bash
rm product_app/static/app.css
```

- [ ] **Step 12: Commit**

```bash
git add product_app/static/css/ -A
git rm product_app/static/app.css
git commit -m "refactor: split monolithic app.css into 7 focused CSS modules"
```

---

### Task 3: Split Python renderer into modules

**Files:**
- Create: `product_app/renderer_components.py`
- Create: `product_app/renderer_landing.py`
- Create: `product_app/renderer_workspace.py`
- Modify: `product_app/site_renderer.py`
- Test: `tests/test_renderer_split.py`

**Context:** Current `site_renderer.py` is 800 lines with two main functions: `render_app_shell()` (213-649) and `render_landing()` (651-800), plus helpers. Split into 4 files: entry point + 3 sub-modules.

- [ ] **Step 1: Write the test**

Create `tests/test_renderer_split.py`:

```python
from __future__ import annotations

import unittest


class RendererSplitTest(unittest.TestCase):
    """Verify the renderer split preserves public API."""

    def test_render_landing_importable_from_site_renderer(self) -> None:
        from product_app.site_renderer import render_landing
        self.assertTrue(callable(render_landing))

    def test_render_app_shell_importable_from_site_renderer(self) -> None:
        from product_app.site_renderer import render_app_shell
        self.assertTrue(callable(render_app_shell))

    def test_render_landing_returns_html(self) -> None:
        from product_app.site_renderer import render_landing
        html = render_landing("en", "/en", None)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn('hreflang="en"', html)

    def test_render_app_shell_returns_html(self) -> None:
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        self.assertIn("workspace", html.lower())

    def test_submodules_importable(self) -> None:
        from product_app.renderer_components import auth_modal_html
        from product_app.renderer_landing import render_landing_html
        from product_app.renderer_workspace import render_workspace_html
        self.assertTrue(callable(auth_modal_html))
        self.assertTrue(callable(render_landing_html))
        self.assertTrue(callable(render_workspace_html))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_renderer_split.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'product_app.renderer_components'`

- [ ] **Step 3: Create renderer_components.py**

Create `product_app/renderer_components.py` — extract helper functions from `site_renderer.py`:
- `_t()` (line 14-15)
- `_lang_href()` (line 18-20)
- `_nav_items()` (line 23-24)
- `_user_badge()` (line 27-37)
- `_language_switch()` (line 40-59)
- `_auth_modal()` (line 62-99) → rename export to `auth_modal_html()`

```python
"""Shared HTML components: auth modal, user badge, nav, language switch."""

from __future__ import annotations


def _t(language: str, english: str, spanish: str) -> str:
    return spanish if language == "es" else english


def lang_href(base_url: str, language: str) -> tuple[str, str]:
    # Copy lines 18-20 from site_renderer.py
    ...


def nav_items_html(language: str) -> str:
    # Copy lines 23-24
    ...


def user_badge_html(language: str, identity: object | None) -> str:
    # Copy lines 27-37
    ...


def language_switch_html(language: str, base_url: str) -> str:
    # Copy lines 40-59
    ...


def auth_modal_html(language: str) -> str:
    # Copy lines 62-99
    ...
```

The function bodies should be copied exactly from the original `site_renderer.py`, just with the `_t` helper imported locally within the module.

- [ ] **Step 4: Create renderer_landing.py**

Create `product_app/renderer_landing.py` — extract `render_landing()` (lines 651-800):

```python
"""Public marketing landing page HTML generation."""

from __future__ import annotations

from .renderer_components import (
    _t, auth_modal_html, language_switch_html, user_badge_html,
)


def render_landing_html(language: str, base_url: str, identity: object | None) -> str:
    # Copy the body of render_landing() from site_renderer.py lines 651-800
    # Replace internal _t/_auth_modal/_user_badge/_language_switch calls
    # with imports from renderer_components
    ...
```

- [ ] **Step 5: Create renderer_workspace.py**

Create `product_app/renderer_workspace.py` — extract `render_app_shell()` (lines 213-649). **This is where the workspace HTML changes for the new sections.**

Rewrite the workspace HTML to include:
- New sidebar navigation (owner vs regular user items)
- New section containers: `#workspace-dashboard`, `#workspace-getting-started`, `#workspace-how-it-works`, `#workspace-agent-factory`, `#workspace-api`, `#workspace-account`, `#workspace-billing`, `#workspace-admin`
- New CSS file includes (7 files instead of 1 app.css)
- New JS module loading (`<script type="module" src="/static/js/app.js">`)
- Pass `productName`, `productDomain`, `unlockProtected` in `window.__QUIEN_PAGE__`

```python
"""Authenticated workspace shell HTML generation."""

from __future__ import annotations

from .renderer_components import _t, auth_modal_html, user_badge_html


def _css_includes() -> str:
    """Generate link tags for all CSS modules."""
    files = [
        "css/theme.css", "css/base.css", "css/layout.css",
        "css/components.css", "css/sections.css", "css/landing.css",
        "css/responsive.css",
    ]
    return "\n".join(
        f'    <link rel="stylesheet" href="/static/{f}">' for f in files
    )


def _sidebar_owner_html(language: str) -> str:
    """Sidebar navigation for product owner/admin."""
    t = lambda en, es: _t(language, en, es)
    return f"""
    <nav class="workspace-nav" id="workspace-nav">
      <div class="ws-product-name" id="ws-product-name"></div>
      <div class="ws-nav-divider"></div>
      <a href="#dashboard" class="ws-nav-item active" data-section="dashboard">
        <span class="ws-nav-icon">📊</span> {t('Dashboard', 'Panel')}
      </a>
      <a href="#getting-started" class="ws-nav-item" data-section="getting-started">
        <span class="ws-nav-icon">🎯</span> {t('Getting Started', 'Primeros Pasos')}
      </a>
      <a href="#how-it-works" class="ws-nav-item" data-section="how-it-works">
        <span class="ws-nav-icon">⚙️</span> {t('How It Works', 'Cómo Funciona')}
      </a>
      <a href="#agent-factory" class="ws-nav-item ws-nav-disabled" data-section="agent-factory">
        <span class="ws-nav-icon">🤖</span> Agent Factory
        <span class="ws-nav-badge-soon">{t('Soon', 'Pronto')}</span>
      </a>
      <div class="ws-nav-divider"></div>
      <a href="#api" class="ws-nav-item" data-section="api">
        <span class="ws-nav-icon">🔑</span> API & MCP
      </a>
      <a href="#account" class="ws-nav-item" data-section="account">
        <span class="ws-nav-icon">👤</span> {t('My Account', 'Mi Cuenta')}
      </a>
      <a href="#billing" class="ws-nav-item" data-section="billing">
        <span class="ws-nav-icon">💳</span> {t('Billing', 'Facturación')}
      </a>
      <a href="#admin" class="ws-nav-item ws-nav-admin" data-section="admin">
        <span class="ws-nav-icon">🛡️</span> Admin
      </a>
    </nav>"""


def _sidebar_user_html(language: str) -> str:
    """Sidebar navigation for regular users."""
    t = lambda en, es: _t(language, en, es)
    return f"""
    <nav class="workspace-nav" id="workspace-nav">
      <div class="ws-product-name" id="ws-product-name"></div>
      <div class="ws-nav-divider"></div>
      <a href="#dashboard" class="ws-nav-item active" data-section="dashboard">
        <span class="ws-nav-icon">📊</span> {t('Dashboard', 'Panel')}
      </a>
      <a href="#components" class="ws-nav-item" data-section="components">
        <span class="ws-nav-icon">🧩</span> {t('Components', 'Componentes')}
      </a>
      <div class="ws-nav-divider"></div>
      <a href="#api" class="ws-nav-item" data-section="api">
        <span class="ws-nav-icon">🔑</span> API & MCP
      </a>
      <a href="#account" class="ws-nav-item" data-section="account">
        <span class="ws-nav-icon">👤</span> {t('My Account', 'Mi Cuenta')}
      </a>
      <a href="#billing" class="ws-nav-item" data-section="billing">
        <span class="ws-nav-icon">💳</span> {t('Billing', 'Facturación')}
      </a>
    </nav>"""


def _section_containers_html() -> str:
    """Empty section containers populated by JS modules."""
    sections = [
        "dashboard", "getting-started", "how-it-works",
        "agent-factory", "components", "api", "account",
        "billing", "admin",
    ]
    return "\n".join(
        f'      <section id="workspace-{s}" class="workspace-section" '
        f'style="display:none"></section>'
        for s in sections
    )


def render_workspace_html(
    language: str,
    base_url: str,
    identity: object | None,
    settings: object | None = None,
) -> str:
    """Render the full workspace HTML shell."""
    # Build the page with:
    # - _css_includes() in <head>
    # - Sidebar (owner or user based on identity.is_admin)
    # - Section containers
    # - <script type="module" src="/static/js/app.js">
    # - window.__QUIEN_PAGE__ with productName, productDomain, unlockProtected
    # - window.__QUIEN_ACCOUNT__ with user data
    ...
```

The full implementation copies the `_layout()` wrapper from the original `site_renderer.py` (lines 102-211) but updates:
1. CSS links: replace single `app.css` with `_css_includes()` output
2. JS: replace `<script src="/static/app.js">` with `<script type="module" src="/static/js/app.js">`
3. Sidebar: use `_sidebar_owner_html()` or `_sidebar_user_html()` based on role
4. Body: use `_section_containers_html()` instead of the old research-style sections
5. Page state: add `productName`, `productDomain`, `unlockProtected` to `window.__QUIEN_PAGE__`

- [ ] **Step 6: Slim down site_renderer.py to entry points**

Rewrite `product_app/site_renderer.py` to be a thin facade:

```python
"""Site renderer — public API entry points.

Delegates to sub-modules:
  renderer_components.py — shared HTML components
  renderer_landing.py    — public landing page
  renderer_workspace.py  — authenticated workspace shell
"""

from __future__ import annotations

from .renderer_landing import render_landing_html
from .renderer_workspace import render_workspace_html


def render_landing(language: str, base_url: str, identity: object | None) -> str:
    """Render the public marketing landing page."""
    return render_landing_html(language, base_url, identity)


def render_app_shell(language: str, base_url: str, identity: object | None) -> str:
    """Render the authenticated workspace app shell."""
    from .config import load_settings
    settings = load_settings()
    return render_workspace_html(language, base_url, identity, settings)
```

This keeps the public API (`render_landing`, `render_app_shell`) identical so `webapp.py` needs zero changes.

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_renderer_split.py tests/test_site_renderer.py -v`
Expected: PASS

- [ ] **Step 8: Verify all renderer files under 600 lines**

```bash
wc -l product_app/site_renderer.py product_app/renderer_*.py
```

- [ ] **Step 9: Commit**

```bash
git add product_app/site_renderer.py product_app/renderer_components.py product_app/renderer_landing.py product_app/renderer_workspace.py tests/test_renderer_split.py
git commit -m "refactor: split site_renderer.py into 4 focused renderer modules"
```

---

### Task 4: JS core — Boot, routing, and module loading

**Files:**
- Rewrite: `product_app/static/app.js` (from 1,833 → ~150 lines)

**Context:** The current `app.js` has everything nested inside a massive `boot()` function (lines 278-1785). We rewrite it to be a thin orchestrator that imports section modules on demand via dynamic `import()`. The `boot()` function becomes: detect context → init auth → setup routing → load first section.

- [ ] **Step 1: Rewrite app.js as module orchestrator**

Replace the entire `product_app/static/app.js` with:

```javascript
/**
 * app.js — Boot sequence, hash routing, and lazy module loading.
 * Section modules are loaded on demand via dynamic import().
 */
import { initAuth, onAuthChange, getActiveToken, logout, openAuthModal } from './auth.js';
import { setupFetch, fetchJson, el, els, t, escapeHtml, showToast } from './utils.js';
import { subscribeRunEvents, startNewRun, fetchHistory, fetchAccount } from './runner.js';

/* ── Global state ── */
let currentSection = 'dashboard';
const _sectionCache = {};  // caches loaded module references

/* ── Page context ── */
const PAGE = window.__QUIEN_PAGE__ || {};
const ACCOUNT = window.__QUIEN_ACCOUNT__ || {};
const isAdmin = ACCOUNT.is_admin === true;

/* ── Section registry ── */
const OWNER_SECTIONS = [
  'dashboard', 'getting-started', 'how-it-works', 'agent-factory',
  'api', 'account', 'billing', 'admin',
];
const USER_SECTIONS = [
  'dashboard', 'components', 'api', 'account', 'billing',
];

function availableSections() {
  return isAdmin ? OWNER_SECTIONS : USER_SECTIONS;
}

/* ── Module loader map ── */
const MODULE_MAP = {
  'dashboard':        () => import('./dashboard.js'),
  'getting-started':  () => import('./getting-started.js'),
  'how-it-works':     () => import('./how-it-works.js'),
  'agent-factory':    null, // Coming soon — no module
  'components':       () => import('./getting-started.js'), // reuses gallery
  'api':              () => import('./api-section.js'),
  'account':          () => import('./account.js'),
  'billing':          () => import('./billing.js'),
  'admin':            () => import('./admin.js'),
};

/* ── Routing ── */
async function switchSection(sectionId) {
  if (!availableSections().includes(sectionId)) {
    sectionId = 'dashboard';
  }

  // Hide all sections
  els('.workspace-section').forEach(s => s.style.display = 'none');

  // Update nav active state
  els('.ws-nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.section === sectionId);
  });

  // Show target section
  const target = el(`#workspace-${sectionId}`);
  if (target) target.style.display = 'block';

  currentSection = sectionId;

  // Load module if not cached
  const loader = MODULE_MAP[sectionId];
  if (!loader) {
    // Coming soon or no module
    if (sectionId === 'agent-factory') {
      target.innerHTML = `
        <div class="af-coming-soon">
          <div class="af-coming-soon-icon">🤖</div>
          <div class="af-coming-soon-title">${t('Agent Factory', 'Fábrica de Agentes')}</div>
          <div class="af-coming-soon-text">${t(
            'Create agents interactively without code. Coming soon.',
            'Crea agentes interactivamente sin código. Próximamente.'
          )}</div>
        </div>`;
    }
    return;
  }

  try {
    if (!_sectionCache[sectionId]) {
      const mod = await loader();
      _sectionCache[sectionId] = mod;
    }
    const mod = _sectionCache[sectionId];
    if (typeof mod.load === 'function') {
      await mod.load(target, { PAGE, ACCOUNT, isAdmin, fetchJson, t, escapeHtml, showToast });
    }
  } catch (err) {
    console.error(`Failed to load section "${sectionId}":`, err);
    if (target) {
      target.innerHTML = `<p style="color:var(--accent-red)">Failed to load section. ${escapeHtml(err.message)}</p>`;
    }
  }
}

function handleHashChange() {
  const hash = location.hash.replace('#', '') || 'dashboard';
  switchSection(hash);
}

/* ── Product name ── */
function setProductName() {
  const nameEl = el('#ws-product-name');
  if (nameEl) {
    nameEl.textContent = PAGE.productName || 'My Product';
  }
}

/* ── Hamburger menu (mobile) ── */
function initHamburger() {
  const toggle = el('#hamburger-toggle');
  const sidebar = el('#workspace-sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    sidebar.addEventListener('click', (e) => {
      if (e.target.closest('.ws-nav-item')) sidebar.classList.remove('open');
    });
  }
}

/* ── Boot ── */
async function boot() {
  if (PAGE.appContext !== 'workspace') {
    bootLanding();
    return;
  }

  setProductName();
  initHamburger();

  // Nav click handlers
  els('.ws-nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const section = item.dataset.section;
      if (section && !item.classList.contains('ws-nav-disabled')) {
        location.hash = section;
      }
    });
  });

  // Hash routing
  window.addEventListener('hashchange', handleHashChange);
  handleHashChange();
}

function bootLanding() {
  initAuth();
  onAuthChange((user) => {
    if (user) location.reload();
  });
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', boot);

export { switchSection, currentSection, PAGE, ACCOUNT, isAdmin };
```

- [ ] **Step 2: Verify app.js is under 150 lines**

```bash
wc -l product_app/static/app.js
```

- [ ] **Step 3: Commit**

```bash
git add product_app/static/app.js
git commit -m "refactor: rewrite app.js as thin module orchestrator with lazy loading"
```

---

### Task 5: JS section — dashboard.js

**Files:**
- Create: `product_app/static/js/dashboard.js`

**Context:** The dashboard shows different views for owner vs regular user. Owner sees: product status, URL, agent count, quick actions, getting-started progress preview. Regular user sees: credits, API calls, available services. The `load()` export receives the container element and context object.

- [ ] **Step 1: Create dashboard.js**

Create `product_app/static/js/dashboard.js`:

```javascript
/**
 * dashboard.js — Owner and regular user dashboard rendering.
 */

/* ── Owner Dashboard ── */
function renderOwnerDashboard(container, ctx) {
  const { PAGE, ACCOUNT, fetchJson, t, escapeHtml } = ctx;
  const domain = PAGE.productDomain || `${PAGE.productSlug || 'myproduct'}.x53.ai`;

  container.innerHTML = `
    <div class="section-header">
      <h2>${t('Dashboard', 'Panel')}</h2>
      <p class="section-subtitle">${t('Welcome to your product workspace', 'Bienvenido a tu workspace')}</p>
    </div>

    <div class="stat-row" id="dash-stats"></div>

    <div class="dash-quick-actions">
      <div class="section-label">${t('QUICK ACTIONS', 'ACCIONES RÁPIDAS')}</div>
      <div class="dash-action-buttons">
        <a href="#getting-started" class="primary-button">${t('Getting Started', 'Primeros Pasos')}</a>
        <a href="#how-it-works" class="secondary-button">${t('How It Works', 'Cómo Funciona')}</a>
        <a href="#api" class="secondary-button">${t('API Keys', 'Claves API')}</a>
      </div>
    </div>

    <div class="dash-gs-preview" id="dash-gs-preview"></div>
  `;

  // Load stats
  loadOwnerStats(container, ctx, domain);

  // Load getting-started progress preview
  loadGsPreview(container, ctx);
}

async function loadOwnerStats(container, ctx, domain) {
  const { ACCOUNT, fetchJson, t } = ctx;
  const statsEl = container.querySelector('#dash-stats');
  if (!statsEl) return;

  try {
    const account = await fetchJson('/api/v1/account');
    const agentCount = await fetchJson('/api/v1/research/capabilities')
      .then(r => r.styles?.length || 0)
      .catch(() => 0);

    statsEl.innerHTML = `
      <div class="stat-card stat-green">
        <div class="stat-label">${t('STATUS', 'ESTADO')}</div>
        <div class="stat-value">● ${t('Active', 'Activo')}</div>
      </div>
      <div class="stat-card stat-cyan">
        <div class="stat-label">${t('DOMAIN', 'DOMINIO')}</div>
        <div class="stat-value stat-url">${domain}</div>
      </div>
      <div class="stat-card stat-purple">
        <div class="stat-label">${t('AGENTS', 'AGENTES')}</div>
        <div class="stat-value">${agentCount}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">${t('CREDITS', 'CRÉDITOS')}</div>
        <div class="stat-value">${account.credits ?? 0}</div>
      </div>
    `;
  } catch (err) {
    statsEl.innerHTML = `<p class="text-muted">${t('Could not load stats', 'No se pudieron cargar estadísticas')}</p>`;
  }
}

function loadGsPreview(container, ctx) {
  const { t } = ctx;
  const previewEl = container.querySelector('#dash-gs-preview');
  if (!previewEl) return;

  // Read progress from localStorage
  const progress = JSON.parse(localStorage.getItem('gs_progress') || '{}');
  const steps = ['explore', 'how-it-works', 'api-key', 'ide', 'deploy'];
  const completed = steps.filter(s => progress[s]).length;

  if (completed >= steps.length) {
    previewEl.innerHTML = `
      <div class="dash-gs-done">
        <span class="gs-check">✓</span> ${t('Setup complete!', '¡Configuración completa!')}
      </div>`;
    return;
  }

  previewEl.innerHTML = `
    <a href="#getting-started" class="dash-gs-card">
      <div class="dash-gs-card-header">
        <span>📘 ${t('GETTING STARTED', 'PRIMEROS PASOS')}</span>
        <span class="dash-gs-count">${completed} / ${steps.length}</span>
      </div>
      <div class="gs-progress-bar">
        <div class="gs-progress-fill" style="width:${(completed / steps.length) * 100}%"></div>
      </div>
    </a>`;
}

/* ── Regular User Dashboard ── */
function renderUserDashboard(container, ctx) {
  const { ACCOUNT, fetchJson, t } = ctx;

  container.innerHTML = `
    <div class="section-header">
      <h2>${t('Dashboard', 'Panel')}</h2>
      <p class="section-subtitle">${t('Welcome back', 'Bienvenido')}</p>
    </div>

    <div class="stat-row" id="dash-user-stats"></div>

    <div class="dash-services" id="dash-services">
      <div class="section-label">${t('AVAILABLE SERVICES', 'SERVICIOS DISPONIBLES')}</div>
      <div class="dash-service-list" id="dash-service-list"></div>
    </div>
  `;

  loadUserStats(container, ctx);
  loadServices(container, ctx);
}

async function loadUserStats(container, ctx) {
  const { fetchJson, t } = ctx;
  const statsEl = container.querySelector('#dash-user-stats');
  if (!statsEl) return;

  try {
    const account = await fetchJson('/api/v1/account');
    statsEl.innerHTML = `
      <div class="stat-card">
        <div class="stat-label">${t('CREDITS', 'CRÉDITOS')}</div>
        <div class="stat-value">${account.credits ?? 0}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">${t('TOTAL RUNS', 'EJECUCIONES')}</div>
        <div class="stat-value">${account.total_runs ?? 0}</div>
      </div>
    `;
  } catch {
    statsEl.innerHTML = '';
  }
}

async function loadServices(container, ctx) {
  const { fetchJson, t } = ctx;
  const listEl = container.querySelector('#dash-service-list');
  if (!listEl) return;

  try {
    const caps = await fetchJson('/api/v1/research/capabilities');
    const styles = caps.styles || [];
    listEl.innerHTML = styles.map(s => `
      <div class="dash-service-card">
        <div class="dash-service-name">${s.name}</div>
        <div class="dash-service-desc">${s.description} — ${s.credit_cost} ${t('credit', 'crédito')}${s.credit_cost !== 1 ? 's' : ''}</div>
      </div>
    `).join('') || `<p class="text-muted">${t('No services configured yet', 'No hay servicios configurados')}</p>`;
  } catch {
    listEl.innerHTML = '';
  }
}

/* ── Public API ── */
export async function load(container, ctx) {
  if (ctx.isAdmin) {
    renderOwnerDashboard(container, ctx);
  } else {
    renderUserDashboard(container, ctx);
  }
}
```

- [ ] **Step 2: Verify dashboard.js under 200 lines**

```bash
wc -l product_app/static/js/dashboard.js
```

- [ ] **Step 3: Commit**

```bash
git add product_app/static/js/dashboard.js
git commit -m "feat: add modular dashboard.js with owner and user views"
```

---

### Task 6: JS section — getting-started.js

**Files:**
- Create: `product_app/static/js/getting-started.js`

**Context:** Owner-only section. 5-step progress tracker with localStorage persistence. Component gallery below. Each step is collapsible. Step 4 (IDE) shows clone commands and vibe coding prompt examples.

- [ ] **Step 1: Create getting-started.js**

Create `product_app/static/js/getting-started.js`:

```javascript
/**
 * getting-started.js — Vibe coding onboarding guide with progress tracker
 * and component gallery for the product owner.
 */

const STEPS = [
  { id: 'explore',       title_en: 'Explore your workspace',        title_es: 'Explora tu workspace',          desc_en: 'Familiarize yourself with the dashboard and sections', desc_es: 'Familiarízate con el panel y las secciones', auto: true },
  { id: 'how-it-works',  title_en: 'Check How It Works',            title_es: 'Revisa Cómo Funciona',          desc_en: 'Understand your default agent pipeline',               desc_es: 'Entiende tu pipeline de agentes por defecto',  auto: true },
  { id: 'api-key',       title_en: 'Get your API key',              title_es: 'Obtén tu clave API',             desc_en: 'Create an API key for external integrations',          desc_es: 'Crea una clave API para integraciones externas', auto: true },
  { id: 'ide',           title_en: 'Open in your IDE & customize',  title_es: 'Abre en tu IDE y personaliza',  desc_en: 'Use vibe coding to add your own interfaces',           desc_es: 'Usa vibe coding para agregar tus interfaces',   auto: false },
  { id: 'deploy',        title_en: 'Deploy and go live',            title_es: 'Despliega y publica',            desc_en: 'Push to main to trigger automatic deployment',         desc_es: 'Push a main para despliegue automático',        auto: false },
];

const PROMPTS = [
  { label: 'Add a chat interface',      prompt_en: 'Add a chat window section where users can interact with the Hello World agent in real-time', prompt_es: 'Agrega una ventana de chat donde los usuarios interactúen con el agente Hello World en tiempo real' },
  { label: 'Customize the landing page', prompt_en: 'Redesign the landing page for a weather forecast service with hero section and pricing',   prompt_es: 'Rediseña la landing page para un servicio de pronóstico del clima con hero section y precios' },
  { label: 'Add a new agent',           prompt_en: 'Create a new agent in product_app/research/ that recommends restaurants based on location using Google Search', prompt_es: 'Crea un nuevo agente en product_app/research/ que recomiende restaurantes por ubicación usando Google Search' },
];

const COMPONENTS = [
  { label: 'Card',         hint_en: 'Add a card grid showing...',    hint_es: 'Agrega una grilla de cards que muestre...' },
  { label: 'Chat Window',  hint_en: 'Add a chat interface for...',   hint_es: 'Agrega una interfaz de chat para...' },
  { label: 'Data Table',   hint_en: 'Add a data table showing...',   hint_es: 'Agrega una tabla de datos que muestre...' },
  { label: 'Form',         hint_en: 'Add a form to collect...',      hint_es: 'Agrega un formulario para recopilar...' },
  { label: 'Chart',        hint_en: 'Add a chart displaying...',     hint_es: 'Agrega un gráfico que muestre...' },
  { label: 'Map',          hint_en: 'Add an interactive map...',     hint_es: 'Agrega un mapa interactivo...' },
];

function getProgress() {
  return JSON.parse(localStorage.getItem('gs_progress') || '{}');
}

function setProgress(stepId, done = true) {
  const p = getProgress();
  p[stepId] = done;
  localStorage.setItem('gs_progress', JSON.stringify(p));
}

function renderSteps(container, ctx) {
  const { t } = ctx;
  const progress = getProgress();
  const completedCount = STEPS.filter(s => progress[s.id]).length;

  // Auto-complete "explore" on first visit
  if (!progress.explore) {
    setProgress('explore', true);
    progress.explore = true;
  }

  // Find current step (first incomplete)
  const currentIdx = STEPS.findIndex(s => !progress[s.id]);

  let html = `
    <div class="section-header">
      <div>
        <h2>${t('Getting Started', 'Primeros Pasos')}</h2>
        <p class="section-subtitle">${t('Complete these steps to launch your product', 'Completa estos pasos para lanzar tu producto')}</p>
      </div>
      <span class="gs-counter">${completedCount} / ${STEPS.length}</span>
    </div>
    <div class="gs-progress-bar">
      <div class="gs-progress-fill" style="width:${(completedCount / STEPS.length) * 100}%"></div>
    </div>
  `;

  STEPS.forEach((step, idx) => {
    const done = progress[step.id];
    const isCurrent = idx === currentIdx;
    const cls = done ? 'completed' : isCurrent ? 'current' : 'pending';
    const title = t(step.title_en, step.title_es);
    const desc = t(step.desc_en, step.desc_es);

    html += `<div class="gs-step ${cls}" data-step="${step.id}">`;
    html += `<div class="gs-step-header">`;
    html += `<div style="display:flex;align-items:center;gap:10px;">`;
    html += done
      ? `<span class="gs-step-icon" style="color:var(--accent-green)">✓</span>`
      : `<span class="gs-step-icon" style="color:${isCurrent ? 'var(--accent-blue)' : 'var(--text-muted)'}">${idx + 1}</span>`;
    html += `<div><div class="gs-step-title">${title}</div><div class="gs-step-desc">${desc}</div></div>`;
    html += `</div>`;
    html += done
      ? `<span class="gs-step-badge done">${t('Done', 'Listo')}</span>`
      : isCurrent
        ? `<span class="gs-step-badge active">${t('Current', 'Actual')}</span>`
        : `<span class="gs-step-badge">${t('Pending', 'Pendiente')}</span>`;
    html += `</div>`;

    // Expanded body for current step
    if (isCurrent && step.id === 'ide') {
      html += renderIdeStep(ctx);
    } else if (isCurrent && step.id === 'deploy') {
      html += renderDeployStep(ctx);
    }

    // Manual complete button for non-auto steps
    if (isCurrent && !step.auto) {
      html += `<button class="gs-complete-btn secondary-button" data-complete="${step.id}">${t('Mark as done', 'Marcar como hecho')}</button>`;
    }

    html += `</div>`;
  });

  return html;
}

function renderIdeStep(ctx) {
  const { t } = ctx;
  let html = `<div class="gs-step-body">`;
  html += `<p class="gs-body-text">${t('Clone your repo and start vibe coding:', 'Clona tu repo y empieza a hacer vibe coding:')}</p>`;
  html += `<pre class="gs-code-block">git clone https://github.com/you/my-product.git\ncd my-product\ncursor .  # ${t('or', 'o')} code .</pre>`;
  html += `<div class="gs-body-label">${t('Example prompts for your AI assistant:', 'Prompts de ejemplo para tu asistente AI:')}</div>`;
  PROMPTS.forEach(p => {
    html += `<div class="gs-prompt-card">`;
    html += `<div class="gs-prompt-label">💡 ${p.label}</div>`;
    html += `<div class="gs-prompt-text">"${t(p.prompt_en, p.prompt_es)}"</div>`;
    html += `</div>`;
  });
  html += `</div>`;
  return html;
}

function renderDeployStep(ctx) {
  const { t } = ctx;
  return `<div class="gs-step-body">
    <p class="gs-body-text">${t('Push your changes to trigger deployment:', 'Haz push de tus cambios para desplegar:')}</p>
    <pre class="gs-code-block">git add -A\ngit commit -m "feat: customize my product"\ngit push origin main</pre>
    <p class="gs-body-text">${t('GitHub Actions will build and deploy to Cloud Run automatically.', 'GitHub Actions construirá y desplegará a Cloud Run automáticamente.')}</p>
  </div>`;
}

function renderGallery(ctx) {
  const { t } = ctx;
  let html = `
    <div class="gs-gallery-header">
      <h3>${t('Component Gallery', 'Galería de Componentes')}</h3>
      <p class="section-subtitle">${t('Reference these when asking your AI assistant to build interfaces', 'Úsalos como referencia al pedirle a tu asistente AI que construya interfaces')}</p>
    </div>
    <div class="gs-component-grid">
  `;
  COMPONENTS.forEach(c => {
    html += `
      <div class="gs-component-card">
        <div class="gs-component-label">${c.label.toUpperCase()}</div>
        <div class="gs-component-preview"></div>
        <div class="gs-component-hint">"${t(c.hint_en, c.hint_es)}"</div>
      </div>`;
  });
  html += `</div>`;
  return html;
}

function bindEvents(container) {
  container.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-complete]');
    if (btn) {
      setProgress(btn.dataset.complete, true);
      load(container, container._ctx);
    }
  });
}

/* ── Public API ── */
export async function load(container, ctx) {
  container._ctx = ctx;
  container.innerHTML = renderSteps(container, ctx) + renderGallery(ctx);
  bindEvents(container);
}
```

- [ ] **Step 2: Verify under 200 lines**

```bash
wc -l product_app/static/js/getting-started.js
```

- [ ] **Step 3: Commit**

```bash
git add product_app/static/js/getting-started.js
git commit -m "feat: add getting-started.js with progress tracker and component gallery"
```

---

### Task 7: JS section — how-it-works.js

**Files:**
- Create: `product_app/static/js/how-it-works.js`

**Context:** Owner-only section. Shows the default agent pipeline with diagram, explains sequential vs parallel pipeline types, and renders a didactic example (weather forecast product). Agent cards are dynamically generated from the `/api/v1/research/capabilities` endpoint.

- [ ] **Step 1: Create how-it-works.js**

Create `product_app/static/js/how-it-works.js`:

```javascript
/**
 * how-it-works.js — Agent pipeline documentation, diagrams, and didactic examples.
 * Fetches capabilities from API and renders pipeline cards.
 */

function renderPipelineTypes(ctx) {
  const { t } = ctx;
  return `
    <div class="hiw-section-title">${t('Pipeline Types', 'Tipos de Pipeline')}</div>
    <div class="hiw-pipeline-types">
      <div class="hiw-type-card">
        <div class="hiw-type-label" style="color:var(--accent-blue)">${t('Sequential', 'Secuencial')}</div>
        <p class="hiw-type-desc">${t(
          'Agents run one after another. Output of each feeds into the next.',
          'Los agentes se ejecutan uno tras otro. La salida de cada uno alimenta al siguiente.'
        )}</p>
        <div class="hiw-pipeline-diagram">
          <div class="hiw-agent-node research">A</div>
          <span class="hiw-arrow">→</span>
          <div class="hiw-agent-node research">B</div>
          <span class="hiw-arrow">→</span>
          <div class="hiw-agent-node research">C</div>
        </div>
        <div class="gs-prompt-card" style="margin-top:8px">
          <div class="gs-prompt-label">💡 ${t('Prompt example', 'Ejemplo de prompt')}:</div>
          <div class="gs-prompt-text">"${t(
            'Create a sequential pipeline: first research, then analyze, then write report',
            'Crea un pipeline secuencial: primero investiga, luego analiza, luego escribe reporte'
          )}"</div>
        </div>
      </div>
      <div class="hiw-type-card">
        <div class="hiw-type-label" style="color:var(--accent-cyan)">${t('Parallel', 'Paralelo')}</div>
        <p class="hiw-type-desc">${t(
          'Multiple agents run at the same time. Results merge at the end.',
          'Múltiples agentes se ejecutan al mismo tiempo. Los resultados se combinan al final.'
        )}</p>
        <div class="hiw-pipeline-diagram" style="flex-direction:row">
          <div class="hiw-parallel-group">
            <div class="hiw-agent-node research" style="min-width:60px">A</div>
            <div class="hiw-agent-node research" style="min-width:60px">B</div>
            <div class="hiw-agent-node research" style="min-width:60px">C</div>
          </div>
          <span class="hiw-arrow">→</span>
          <div class="hiw-agent-node output">Merge</div>
        </div>
        <div class="gs-prompt-card" style="margin-top:8px">
          <div class="gs-prompt-label">💡 ${t('Prompt example', 'Ejemplo de prompt')}:</div>
          <div class="gs-prompt-text">"${t(
            'Create 3 parallel agents: news, social media, and web search — merge results into a briefing',
            'Crea 3 agentes paralelos: noticias, redes sociales y búsqueda web — combina resultados en un briefing'
          )}"</div>
        </div>
      </div>
    </div>`;
}

function renderDidacticExample(ctx) {
  const { t } = ctx;
  return `
    <div class="hiw-section-title">${t('Example: Weather Forecast Product', 'Ejemplo: Producto de Pronóstico del Clima')}</div>
    <p class="hiw-section-desc">${t(
      'What a 4-agent product might look like after customization',
      'Cómo se vería un producto de 4 agentes después de personalización'
    )}</p>
    <div class="hiw-agent-card">
      <div class="hiw-pipeline-diagram">
        <div class="hiw-agent-node" style="border-color:var(--text-muted)">
          <div style="font-size:10px;color:var(--text-secondary)">${t('User Input', 'Entrada')}</div>
        </div>
        <span class="hiw-arrow">→</span>
        <div class="hiw-parallel-group">
          <span style="color:var(--accent-cyan);font-size:9px;text-align:center">PARALLEL</span>
          <div class="hiw-agent-node research">🌤 Weather</div>
          <div class="hiw-agent-node research">📰 News</div>
        </div>
        <span class="hiw-arrow">→</span>
        <div class="hiw-agent-node" style="border-color:#a78bfa">🧠 Analyst</div>
        <span class="hiw-arrow">→</span>
        <div class="hiw-agent-node report">📝 Reporter</div>
        <span class="hiw-arrow">→</span>
        <div class="hiw-agent-node output">✓ Report</div>
      </div>
      <div class="gs-prompt-card" style="margin-top:10px">
        <div class="gs-prompt-label">💡 ${t('How this was created', 'Cómo se creó')}:</div>
        <div class="gs-prompt-text">"${t(
          'Create a weather forecast pipeline: two parallel agents (weather API + news search), then an analyst to combine, then a reporter for the final briefing',
          'Crea un pipeline de pronóstico: dos agentes paralelos (API del clima + búsqueda de noticias), luego un analista que combine, luego un reportero para el briefing final'
        )}"</div>
      </div>
    </div>`;
}

function renderAgentCard(style, ctx) {
  const { t } = ctx;
  const isCanonical = style.is_canonical !== false;
  const badgeClass = isCanonical ? 'canonical' : 'custom';
  const badgeText = isCanonical ? '🔒 Canonical' : '✏️ Custom';
  const agents = style.agents || [];

  let diagramHtml = '<div class="hiw-pipeline-diagram">';
  agents.forEach((agent, i) => {
    if (i > 0) diagramHtml += '<span class="hiw-arrow">→</span>';
    diagramHtml += `<div class="hiw-agent-node research">${agent.icon || '🤖'} ${agent.name || agent}</div>`;
  });
  diagramHtml += '<span class="hiw-arrow">→</span><div class="hiw-agent-node output">✓</div>';
  diagramHtml += '</div>';

  return `
    <div class="hiw-agent-card">
      <div class="hiw-agent-header">
        <div>
          <div style="color:var(--accent-cyan);font-size:11px;letter-spacing:1px">${isCanonical ? t('DEFAULT AGENT', 'AGENTE POR DEFECTO') : t('CUSTOM AGENT', 'AGENTE PERSONALIZADO')}</div>
          <div style="color:var(--text-primary);font-size:15px;font-weight:600">${style.name}</div>
        </div>
        <div style="display:flex;gap:6px">
          <span class="hiw-badge active">● ${t('Active', 'Activo')}</span>
          <span class="hiw-badge ${badgeClass}">${badgeText}</span>
        </div>
      </div>
      ${diagramHtml}
      <div class="hiw-meta">
        <span>⚡ ${style.agent_count || agents.length} ${t('agents', 'agentes')}</span>
        <span>💰 ${style.credit_cost || 1} ${t('credit', 'crédito')}${(style.credit_cost || 1) !== 1 ? 's' : ''}</span>
        ${style.estimated_duration ? `<span>⏱ ${style.estimated_duration}</span>` : ''}
      </div>
    </div>`;
}

/* ── Public API ── */
export async function load(container, ctx) {
  const { fetchJson, t } = ctx;

  // Mark how-it-works as visited for getting-started progress
  const progress = JSON.parse(localStorage.getItem('gs_progress') || '{}');
  if (!progress['how-it-works']) {
    progress['how-it-works'] = true;
    localStorage.setItem('gs_progress', JSON.stringify(progress));
  }

  let html = `
    <div class="section-header">
      <h2>${t('How It Works', 'Cómo Funciona')}</h2>
      <p class="section-subtitle">${t('Your product runs on AI agent pipelines. Here\\'s how they work.', 'Tu producto funciona con pipelines de agentes AI. Así es cómo funcionan.')}</p>
    </div>
  `;

  // Fetch capabilities and render agent cards
  try {
    const caps = await fetchJson('/api/v1/research/capabilities');
    const styles = caps.styles || [];
    styles.forEach(s => { html += renderAgentCard(s, ctx); });
  } catch {
    html += `<p class="text-muted">${t('Could not load agent capabilities', 'No se pudieron cargar las capacidades')}</p>`;
  }

  html += renderPipelineTypes(ctx);
  html += renderDidacticExample(ctx);

  container.innerHTML = html;
}
```

- [ ] **Step 2: Verify under 200 lines**

```bash
wc -l product_app/static/js/how-it-works.js
```

- [ ] **Step 3: Commit**

```bash
git add product_app/static/js/how-it-works.js
git commit -m "feat: add how-it-works.js with pipeline docs and didactic examples"
```

---

### Task 8: JS sections — admin.js, billing.js, api-section.js, account.js

**Files:**
- Create: `product_app/static/js/admin.js`
- Create: `product_app/static/js/billing.js`
- Create: `product_app/static/js/api-section.js`
- Create: `product_app/static/js/account.js`

**Context:** Extract existing section logic from the monolithic `app.js` into separate modules. Each module exports a `load(container, ctx)` function. The code is largely the same as the original `boot()` nested functions, adapted to the module pattern.

The key extraction map from `app.js`:
- `loadAdminArea()` lines 1248-1450 → `admin.js`
- `loadBillingArea()` lines 1046-1245 → `billing.js`
- `loadApiArea()` lines 719-881 → `api-section.js`
- `loadAccountArea()` lines 884-1043 → `account.js`

- [ ] **Step 1: Create admin.js**

Extract `loadAdminArea()` (lines 1248-1450) from `app.js` into `product_app/static/js/admin.js`. Adapt:
- Replace closure variables with `ctx` parameter access (`ctx.fetchJson`, `ctx.t`, `ctx.escapeHtml`, `ctx.showToast`)
- Replace `el('#workspace-admin')` with the `container` parameter
- Export as `load(container, ctx)`
- Add readonly protection check: if `!ctx.PAGE.unlockProtected`, wrap content in `.protected-overlay` with warning banner

```javascript
/**
 * admin.js — Admin panel: user management, access requests, analytics.
 * Protected section — requires UNLOCK_PROTECTED=true to edit.
 */

export async function load(container, ctx) {
  const { PAGE, fetchJson, t, escapeHtml, showToast } = ctx;
  const locked = !PAGE.unlockProtected;

  let html = `
    <div class="section-header">
      <h2>Admin</h2>
      ${locked
        ? '<span class="protected-badge locked">🔒 Protected</span>'
        : '<span class="protected-badge unlocked">🔓 Unlocked</span>'}
    </div>
  `;

  if (locked) {
    html += `
      <div class="protected-banner locked">
        <div style="font-weight:600;color:var(--accent-amber)">⚠️ Protected Section</div>
        <p style="color:var(--text-secondary);font-size:12px;margin-top:4px">
          ${t(
            'This section controls core functionality. To edit, add UNLOCK_PROTECTED=true to your .env file.',
            'Esta sección controla funcionalidad crítica. Para editar, agrega UNLOCK_PROTECTED=true a tu archivo .env.'
          )}
        </p>
      </div>
      <div class="protected-overlay">`;
  } else {
    html += `
      <div class="protected-banner unlocked">
        <div style="font-weight:600;color:var(--accent-red)">🔓 Editing Enabled</div>
        <p style="color:var(--text-secondary);font-size:12px;margin-top:4px">
          ${t('Protected sections are unlocked. Proceed carefully.', 'Secciones protegidas desbloqueadas. Procede con cuidado.')}
        </p>
      </div>`;
  }

  // Paste the admin panel rendering logic from original loadAdminArea()
  // (access requests table, user management, usage analytics, revenue)
  // Replace all el() calls with container.querySelector()
  // Replace all fetchJson/showToast with ctx versions
  html += `<div id="admin-content"></div>`;

  if (locked) html += `</div>`; // close protected-overlay

  container.innerHTML = html;

  // Load admin data into #admin-content
  if (!locked) {
    await loadAdminContent(container.querySelector('#admin-content'), ctx);
  } else {
    await loadAdminContentReadonly(container.querySelector('#admin-content'), ctx);
  }
}

async function loadAdminContent(target, ctx) {
  // Full interactive admin panel — extract from original loadAdminArea() lines 1248-1450
  // Include: access requests, user table with top-up, usage stats
  const { fetchJson, t, escapeHtml, showToast } = ctx;
  // ... (copy and adapt the rendering logic from original boot() → loadAdminArea)
}

async function loadAdminContentReadonly(target, ctx) {
  // Same data display but without action buttons (readonly view)
  const { fetchJson, t } = ctx;
  // ... (same rendering but omit buttons/forms)
}
```

The implementer should copy the full body of `loadAdminArea()` from the original `app.js` lines 1248-1450, replacing all closure-scoped variables with `ctx.*` equivalents.

- [ ] **Step 2: Create billing.js**

Extract `loadBillingArea()` (lines 1046-1245) from `app.js` into `product_app/static/js/billing.js`:

```javascript
/**
 * billing.js — Credit balance, Stripe checkout, invoice history.
 */

export async function load(container, ctx) {
  const { fetchJson, t, showToast } = ctx;
  // Copy and adapt loadBillingArea() from original app.js lines 1046-1245
  // Replace el('#workspace-billing') with container
  // Replace closure fetchJson/t with ctx versions
}
```

- [ ] **Step 3: Create api-section.js**

Extract `loadApiArea()` (lines 719-881) from `app.js` into `product_app/static/js/api-section.js`:

```javascript
/**
 * api-section.js — API key management, webhook config, MCP endpoints.
 */

export async function load(container, ctx) {
  const { fetchJson, t, escapeHtml, showToast } = ctx;

  // Mark api-key step as complete for getting-started
  const progress = JSON.parse(localStorage.getItem('gs_progress') || '{}');
  if (!progress['api-key']) {
    progress['api-key'] = true;
    localStorage.setItem('gs_progress', JSON.stringify(progress));
  }

  // Copy and adapt loadApiArea() from original app.js lines 719-881
  // Replace el('#workspace-api') with container
}
```

- [ ] **Step 4: Create account.js**

Extract `loadAccountArea()` (lines 884-1043) from `app.js` into `product_app/static/js/account.js`:

```javascript
/**
 * account.js — User profile and preferences.
 */

export async function load(container, ctx) {
  const { fetchJson, t, showToast } = ctx;
  // Copy and adapt loadAccountArea() from original app.js lines 884-1043
  // Replace el('#workspace-account') with container
}
```

- [ ] **Step 5: Verify all files under 300 lines**

```bash
wc -l product_app/static/js/admin.js product_app/static/js/billing.js product_app/static/js/api-section.js product_app/static/js/account.js
```

- [ ] **Step 6: Commit**

```bash
git add product_app/static/js/admin.js product_app/static/js/billing.js product_app/static/js/api-section.js product_app/static/js/account.js
git commit -m "feat: extract admin, billing, API, and account into separate JS modules"
```

---

### Task 9: Update tests and integration

**Files:**
- Modify: `tests/test_site_renderer.py`
- Modify: `tests/test_renderer_split.py` (update if needed)
- Create: `tests/test_workspace_sections.py`

**Context:** Update existing tests for the new renderer structure and add basic tests for the workspace sections being present in the HTML output.

- [ ] **Step 1: Update test_site_renderer.py**

```python
from __future__ import annotations

import unittest

from product_app.site_renderer import render_landing, render_app_shell


class SiteRendererTest(unittest.TestCase):
    def test_landing_contains_hreflang_and_auth(self) -> None:
        html = render_landing("en", "/en", None)
        self.assertIn('hreflang="en"', html)
        self.assertIn('hreflang="es"', html)
        self.assertIn('id="auth-modal"', html)

    def test_app_shell_contains_workspace_sections(self) -> None:
        html = render_app_shell("en", "/en", None)
        self.assertIn('id="workspace-dashboard"', html)
        self.assertIn('id="workspace-getting-started"', html)
        self.assertIn('id="workspace-how-it-works"', html)
        self.assertIn('id="workspace-api"', html)
        self.assertIn('id="workspace-billing"', html)
        self.assertIn('id="workspace-admin"', html)

    def test_app_shell_loads_css_modules(self) -> None:
        html = render_app_shell("en", "/en", None)
        self.assertIn('css/theme.css', html)
        self.assertIn('css/layout.css', html)
        self.assertIn('css/components.css', html)

    def test_app_shell_loads_js_module(self) -> None:
        html = render_app_shell("en", "/en", None)
        self.assertIn('type="module"', html)
        self.assertIn('js/app.js', html)

    def test_app_shell_includes_product_name(self) -> None:
        html = render_app_shell("en", "/en", None)
        self.assertIn('productName', html)

    def test_app_shell_includes_unlock_protected(self) -> None:
        html = render_app_shell("en", "/en", None)
        self.assertIn('unlockProtected', html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS. If any pre-existing tests fail due to the restructuring, fix them.

- [ ] **Step 3: Run linting**

```bash
cd /d/Source-Code/3-parts/aaas-product-template
python -m flake8 product_app/site_renderer.py product_app/renderer_*.py --max-line-length=120
```

- [ ] **Step 4: Verify no file exceeds 600 lines**

```bash
find product_app/static/js/ -name "*.js" -exec wc -l {} + | sort -n
find product_app/static/css/ -name "*.css" -exec wc -l {} + | sort -n
wc -l product_app/site_renderer.py product_app/renderer_*.py
```

All files must be under 600 lines. If any exceed, split further.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: update renderer and workspace tests for modular architecture"
```

---

### Task 10: Final cleanup and deploy

**Files:**
- Verify: All new and modified files
- Delete: `product_app/static/app.css` (if not deleted in Task 2)

- [ ] **Step 1: Verify file structure**

```bash
echo "=== JS Modules ==="
ls -la product_app/static/js/
echo "=== CSS Modules ==="
ls -la product_app/static/css/
echo "=== Python Renderers ==="
ls -la product_app/renderer_*.py product_app/site_renderer.py
echo "=== Line counts ==="
find product_app/static/js/ -name "*.js" -exec wc -l {} + | sort -n
find product_app/static/css/ -name "*.css" -exec wc -l {} + | sort -n
wc -l product_app/site_renderer.py product_app/renderer_*.py
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Verify old app.css is removed**

```bash
test ! -f product_app/static/app.css && echo "DELETED" || echo "STILL EXISTS — delete it"
```

- [ ] **Step 4: Final commit if any remaining changes**

```bash
git status
# If any unstaged changes:
git add -A
git commit -m "chore: final cleanup for template workspace modular redesign"
```

- [ ] **Step 5: Push to deploy**

```bash
git push origin master
```
