from __future__ import annotations

import json
import re
import unittest

from product_app.site_renderer import (
    render_landing,
    render_app_shell,
)


class SiteRendererTest(unittest.TestCase):
    def test_landing_contains_hreflang_and_auth_modal(self) -> None:
        html = render_landing("en", "/en", None)

        self.assertIn('hreflang="en"', html)
        self.assertIn('hreflang="es"', html)
        self.assertIn('id="auth-modal"', html)
        self.assertIn('id="custom-agent-form"', html)

    def test_app_shell_returns_html(self) -> None:
        html = render_app_shell("en", "/en", None)
        self.assertIn("<!DOCTYPE html>", html)

    def test_app_shell_workspace_section_containers(self) -> None:
        html = render_app_shell("en", "/en", None)
        for section_id in [
            "workspace-dashboard",
            "workspace-getting-started",
            "workspace-how-it-works",
            "workspace-api",
            "workspace-billing",
            "workspace-admin",
        ]:
            self.assertIn(f'id="{section_id}"', html, f"Missing section: {section_id}")

    def test_app_shell_loads_css_modules(self) -> None:
        html = render_app_shell("en", "/en", None)
        for css_file in ["css/theme.css", "css/layout.css", "css/components.css"]:
            self.assertIn(css_file, html, f"Missing CSS module: {css_file}")

    def test_app_shell_uses_js_module_type(self) -> None:
        html = render_app_shell("en", "/en", None)
        self.assertIn('type="module"', html)

    def test_app_shell_includes_product_name_in_page_state(self) -> None:
        html = render_app_shell("en", "/en", None)
        match = re.search(r"window\.__QUIEN_PAGE__\s*=\s*(\{[^;]+\})", html)
        self.assertIsNotNone(match, "Could not find __QUIEN_PAGE__ in HTML")
        state = json.loads(match.group(1))
        self.assertIn("productName", state)
        self.assertIn("unlockProtected", state)


if __name__ == "__main__":
    unittest.main()
