"""Thin facade — public API re-exported from renderer sub-modules.

webapp.py imports render_landing and render_app_shell from here.
"""

from __future__ import annotations

from typing import Any

from .renderer_landing import render_landing_html
from .renderer_workspace import render_workspace_html


def render_landing(
    language: str,
    base_url: str,
    identity: dict[str, Any] | None,
) -> str:
    return render_landing_html(language, base_url, identity)


def render_app_shell(
    language: str,
    base_url: str,
    identity: dict[str, Any] | None,
) -> str:
    from .config import load_settings
    settings = load_settings()
    return render_workspace_html(language, base_url, identity, settings)
