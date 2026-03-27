"""MCP server exposing research tools for AI agent consumption.

Run standalone: python -m product_app.mcp_server
Or import TOOL_DEFINITIONS for testing.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "submit_research",
        "description": "Submit a new research request. Returns a job_id for tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "style": {
                    "type": "string",
                    "description": "Research style: deploy_product, market_intelligence, world_news_briefing, company_deep_dive, industry_analysis, osint_360",
                    "enum": ["deploy_product", "market_intelligence", "world_news_briefing", "company_deep_dive", "industry_analysis", "osint_360"],
                },
                "prompt": {
                    "type": "string",
                    "description": "The research prompt/query describing what to investigate.",
                },
                "language": {
                    "type": "string",
                    "description": "Report language: en or es. Defaults to en.",
                    "enum": ["en", "es"],
                    "default": "en",
                },
                "webhook_url": {
                    "type": "string",
                    "description": "Optional webhook URL to receive results when complete.",
                },
            },
            "required": ["style", "prompt"],
        },
    },
    {
        "name": "get_research_status",
        "description": "Get the status and progress of a research run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job_id returned from submit_research.",
                },
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "get_research_report",
        "description": "Get the completed research report. Only available after status is 'completed'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job_id of the completed research.",
                },
                "format": {
                    "type": "string",
                    "description": "Report format: json (structured), text (plain), or html. Defaults to json.",
                    "enum": ["json", "text", "html"],
                    "default": "json",
                },
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_research_styles",
        "description": "List all available research styles with descriptions, costs, and estimated durations.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_credit_balance",
        "description": "Get the current credit balance and recent usage summary.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _make_api_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make an HTTP request to the local API."""
    import urllib.request

    base_url = os.environ.get("RESEARCH_LAB_API_URL", "http://127.0.0.1:8000")
    api_key = os.environ.get("RESEARCH_LAB_API_KEY", "")
    url = f"{base_url}{path}"

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle a single MCP tool call."""
    if name == "submit_research":
        return _make_api_request("POST", "/api/v1/runs", {
            "prompt": arguments["prompt"],
            "research_style": arguments["style"],
            "language": arguments.get("language", "en"),
            "webhook_url": arguments.get("webhook_url"),
        })

    elif name == "get_research_status":
        return _make_api_request("GET", f"/api/v1/runs/{arguments['job_id']}")

    elif name == "get_research_report":
        result = _make_api_request("GET", f"/api/v1/runs/{arguments['job_id']}")
        fmt = arguments.get("format", "json")
        if fmt == "text":
            sections = result.get("sections", [])
            return {"text": "\n\n".join(s.get("text", "") for s in sections)}
        elif fmt == "html":
            sections = result.get("sections", [])
            return {"html": "\n".join(s.get("html", "") for s in sections)}
        return result

    elif name == "list_research_styles":
        return _make_api_request("GET", "/api/v1/research/capabilities")

    elif name == "get_credit_balance":
        account = _make_api_request("GET", "/api/v1/account")
        return {
            "credits": account.get("credits", 0),
            "email": account.get("email", ""),
        }

    return {"error": f"Unknown tool: {name}"}


def main():
    """Run as MCP stdio server."""
    try:
        from mcp.server.stdio import stdio_server  # noqa: F401
        from mcp.server import Server  # noqa: F401
        from mcp import types  # noqa: F401

        server = Server("research-lab-studio")

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name=t["name"],
                    description=t["description"],
                    inputSchema=t["inputSchema"],
                )
                for t in TOOL_DEFINITIONS
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            result = handle_tool_call(name, arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        import asyncio
        asyncio.run(stdio_server(server))

    except ImportError:
        print("MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
