from __future__ import annotations

import unittest

from product_app.site_renderer import (
    render_landing,
)


class SiteRendererTest(unittest.TestCase):
    def test_landing_contains_hreflang_and_access_form(self) -> None:
        html = render_landing("en", "/en", None)

        self.assertIn('hreflang="en"', html)
        self.assertIn('hreflang="es"', html)
        self.assertIn('id="access-request-form"', html)
        self.assertIn('id="auth-modal"', html)
        # Verify 6 research style cards are present
        self.assertIn('VC Due Diligence', html)
        self.assertIn('OSINT 360', html)


if __name__ == "__main__":
    unittest.main()
