from __future__ import annotations

import unittest

from product_app.mcp_server import TOOL_DEFINITIONS, handle_tool_call


class MCPToolDefinitionsTest(unittest.TestCase):
    def test_tool_names(self) -> None:
        tool_names = {t["name"] for t in TOOL_DEFINITIONS}
        expected = {
            "submit_research",
            "get_research_status",
            "get_research_report",
            "list_research_styles",
            "get_credit_balance",
        }
        self.assertEqual(tool_names, expected)

    def test_submit_research_has_required_params(self) -> None:
        submit = next(t for t in TOOL_DEFINITIONS if t["name"] == "submit_research")
        required = submit["inputSchema"].get("required", [])
        self.assertIn("style", required)
        self.assertIn("prompt", required)

    def test_all_tools_have_input_schema(self) -> None:
        for tool in TOOL_DEFINITIONS:
            self.assertIn("inputSchema", tool, f"{tool['name']} missing inputSchema")
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_handle_unknown_tool(self) -> None:
        result = handle_tool_call("nonexistent_tool", {})
        self.assertIn("error", result)
        self.assertIn("Unknown tool", result["error"])


if __name__ == "__main__":
    unittest.main()
