from __future__ import annotations

import unittest
from pathlib import Path

from product_app.research.registry import StyleRegistry
from product_app.service import _artifact_kind, _build_sections
from product_app.tools import _build_pdf_report


class ServiceHelpersTest(unittest.TestCase):
    def test_registry_provides_stage_definitions(self) -> None:
        registry = StyleRegistry()
        registry.auto_discover()
        vc_style = registry.get("deploy_product")
        stages = vc_style.get_stages()
        self.assertEqual(len(stages), 7)
        self.assertEqual(stages[0].id, "company_info")

        mi_style = registry.get("market_intelligence")
        stages = mi_style.get_stages()
        self.assertEqual(len(stages), 6)
        self.assertEqual(stages[0].id, "market_state")

    def test_build_sections_returns_ordered_rendered_sections(self) -> None:
        state = {
            "market_analysis": "## Market Opportunity\n- Large and growing category",
            "company_info": "## Company Overview\n- Productive AI company",
        }

        sections = _build_sections(state, "deploy_product")

        self.assertEqual([section.id for section in sections], ["company_info", "market_analysis"])
        self.assertIn("<h2>Company Overview</h2>", sections[0].html)
        self.assertIn("<li>Large and growing category</li>", sections[1].html)

    def test_artifact_kind_recognizes_pdf_reports(self) -> None:
        self.assertEqual(_artifact_kind(Path("report.pdf")), "report_pdf")
        self.assertEqual(_artifact_kind(Path("report.html")), "report_html")

    def test_build_pdf_report_returns_pdf_bytes(self) -> None:
        pdf_bytes = _build_pdf_report("## Executive Summary\n- Strong pipeline", "March 13, 2026")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
