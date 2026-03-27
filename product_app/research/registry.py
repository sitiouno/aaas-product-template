"""Style registry with auto-discovery."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from .base import ResearchStyleBase


class StyleRegistry:
    """Discovers and manages research style implementations."""

    def __init__(self) -> None:
        self._styles: dict[str, ResearchStyleBase] = {}

    def register(self, style: ResearchStyleBase) -> None:
        self._styles[style.key] = style

    def get(self, key: str) -> ResearchStyleBase:
        if key not in self._styles:
            raise KeyError(f"Unknown research style: {key!r}")
        return self._styles[key]

    def all(self) -> dict[str, ResearchStyleBase]:
        return dict(self._styles)

    def auto_discover(self) -> None:
        """Import all sibling modules and register any ResearchStyleBase subclass instances."""
        package = importlib.import_module("product_app.research")
        for importer, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if module_name in ("base", "registry", "common"):
                continue
            module = importlib.import_module(f"product_app.research.{module_name}")
            style = getattr(module, "STYLE", None)
            if isinstance(style, ResearchStyleBase):
                self.register(style)

    def capabilities(self, language: str = "en") -> list[dict[str, Any]]:
        """Return a list of style metadata dicts for the API."""
        return [
            {
                "key": style.key,
                "name": style.name_for_language(language),
                "description": style.description_for_language(language),
                "credit_cost": style.credit_cost,
                "agent_count": style.agent_count,
                "estimated_duration_minutes": list(style.estimated_duration_minutes),
            }
            for style in self._styles.values()
        ]
