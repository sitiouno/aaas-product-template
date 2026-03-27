from __future__ import annotations

import unittest

from product_app.research.base import ResearchStyleBase, StageDefinition


class FakeStyle(ResearchStyleBase):
    key = "fake_test"
    name_en = "Fake Test"
    name_es = "Prueba Falsa"
    description_en = "A test style"
    description_es = "Un estilo de prueba"
    credit_cost = 1
    agent_count = 1
    estimated_duration_minutes = (1, 2)

    def build_pipeline(self, settings):
        return None

    def get_stages(self) -> list[StageDefinition]:
        return [
            StageDefinition(
                id="fake_stage",
                agent_name="FakeAgent",
                title="Fake Stage",
                description="Does nothing.",
                output_key="fake_output",
            ),
        ]

    def get_section_titles(self) -> dict[str, str]:
        return {"fake_output": "Fake Section"}


class ResearchStyleBaseTest(unittest.TestCase):
    def test_style_has_required_attributes(self) -> None:
        style = FakeStyle()
        self.assertEqual(style.key, "fake_test")
        self.assertEqual(style.credit_cost, 1)
        self.assertEqual(style.estimated_duration_minutes, (1, 2))

    def test_get_stages_returns_stage_definitions(self) -> None:
        style = FakeStyle()
        stages = style.get_stages()
        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0].id, "fake_stage")
        self.assertEqual(stages[0].agent_name, "FakeAgent")

    def test_get_section_titles_returns_mapping(self) -> None:
        style = FakeStyle()
        titles = style.get_section_titles()
        self.assertEqual(titles["fake_output"], "Fake Section")

    def test_name_for_language(self) -> None:
        style = FakeStyle()
        self.assertEqual(style.name_for_language("en"), "Fake Test")
        self.assertEqual(style.name_for_language("es"), "Prueba Falsa")
        self.assertEqual(style.name_for_language("fr"), "Fake Test")

    def test_description_for_language(self) -> None:
        style = FakeStyle()
        self.assertEqual(style.description_for_language("en"), "A test style")
        self.assertEqual(style.description_for_language("es"), "Un estilo de prueba")


class StyleRegistryTest(unittest.TestCase):
    def test_register_and_get(self) -> None:
        from product_app.research.registry import StyleRegistry

        registry = StyleRegistry()
        style = FakeStyle()
        registry.register(style)
        self.assertIs(registry.get("fake_test"), style)

    def test_get_unknown_raises(self) -> None:
        from product_app.research.registry import StyleRegistry

        registry = StyleRegistry()
        with self.assertRaises(KeyError):
            registry.get("nonexistent")

    def test_all_returns_copy(self) -> None:
        from product_app.research.registry import StyleRegistry

        registry = StyleRegistry()
        registry.register(FakeStyle())
        all_styles = registry.all()
        self.assertIn("fake_test", all_styles)
        all_styles.pop("fake_test")
        self.assertIsNotNone(registry.get("fake_test"))

    def test_auto_discover_runs_without_error(self) -> None:
        from product_app.research.registry import StyleRegistry

        registry = StyleRegistry()
        registry.auto_discover()

    def test_capabilities_list(self) -> None:
        from product_app.research.registry import StyleRegistry

        registry = StyleRegistry()
        registry.register(FakeStyle())
        caps = registry.capabilities("en")
        self.assertEqual(len(caps), 1)
        self.assertEqual(caps[0]["key"], "fake_test")
        self.assertEqual(caps[0]["name"], "Fake Test")
        self.assertEqual(caps[0]["credit_cost"], 1)

    def test_all_six_styles_discovered(self) -> None:
        from product_app.research.registry import StyleRegistry

        registry = StyleRegistry()
        registry.auto_discover()
        all_styles = registry.all()
        expected = {
            "deploy_product",
            "market_intelligence",
            "world_news_briefing",
            "company_deep_dive",
            "industry_analysis",
            "osint_360",
        }
        self.assertEqual(set(all_styles.keys()), expected)


if __name__ == "__main__":
    unittest.main()
