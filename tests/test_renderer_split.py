"""Tests for the split renderer modules (Task 3)."""

from __future__ import annotations

import unittest


class TestRendererSplit(unittest.TestCase):

    def test_render_landing_importable_from_site_renderer(self):
        from product_app.site_renderer import render_landing
        assert callable(render_landing)

    def test_render_app_shell_importable_from_site_renderer(self):
        from product_app.site_renderer import render_app_shell
        assert callable(render_app_shell)

    def test_render_landing_returns_html(self):
        from product_app.site_renderer import render_landing
        html = render_landing("en", "/en", None)
        assert "<!DOCTYPE html>" in html
        assert 'hreflang="en"' in html

    def test_render_app_shell_returns_html(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        assert "workspace" in html.lower()

    def test_app_shell_contains_workspace_sections(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        assert 'id="workspace-dashboard"' in html
        assert 'id="workspace-getting-started"' in html
        assert 'id="workspace-how-it-works"' in html
        assert 'id="workspace-api"' in html

    def test_app_shell_loads_css_modules(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        assert "css/theme.css" in html
        assert "css/layout.css" in html

    def test_app_shell_loads_js_module(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        assert 'type="module"' in html

    def test_app_shell_includes_product_name(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        assert "productName" in html

    def test_submodules_importable(self):
        from product_app.renderer_components import auth_modal_html
        from product_app.renderer_landing import render_landing_html
        from product_app.renderer_workspace import render_workspace_html
        assert callable(auth_modal_html)
        assert callable(render_landing_html)
        assert callable(render_workspace_html)

    def test_app_shell_contains_all_section_ids(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        for section_id in [
            "workspace-dashboard",
            "workspace-getting-started",
            "workspace-how-it-works",
            "workspace-agent-factory",
            "workspace-components",
            "workspace-api",
            "workspace-account",
            "workspace-billing",
            "workspace-admin",
        ]:
            assert f'id="{section_id}"' in html, f"Missing section: {section_id}"

    def test_app_shell_sidebar_has_data_section_attrs(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        assert 'data-section="dashboard"' in html
        assert 'data-section="api"' in html

    def test_app_shell_loads_all_css_modules(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        for css_file in [
            "css/theme.css", "css/base.css", "css/layout.css",
            "css/components.css", "css/overlays.css", "css/sections.css",
            "css/workspace.css", "css/results.css", "css/landing.css",
            "css/responsive.css",
        ]:
            assert css_file in html, f"Missing CSS module: {css_file}"

    def test_app_shell_js_module_path(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        assert "/static/js/app.js" in html

    def test_app_shell_page_state_has_product_fields(self):
        import json
        import re
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("en", "/en", None)
        match = re.search(r"window\.__QUIEN_PAGE__\s*=\s*(\{[^;]+\})", html)
        assert match, "Could not find __QUIEN_PAGE__ in HTML"
        state = json.loads(match.group(1))
        assert "productName" in state
        assert "productDomain" in state
        assert "unlockProtected" in state

    def test_spanish_workspace_renders(self):
        from product_app.site_renderer import render_app_shell
        html = render_app_shell("es", "/es/app", None)
        assert "<!DOCTYPE html>" in html
        assert 'lang="es"' in html

    def test_spanish_landing_renders(self):
        from product_app.site_renderer import render_landing
        html = render_landing("es", "/es", None)
        assert "<!DOCTYPE html>" in html
        assert 'hreflang="es"' in html


if __name__ == "__main__":
    unittest.main()
