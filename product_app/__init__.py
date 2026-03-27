"""Product Name package."""

from __future__ import annotations

import warnings

warnings.filterwarnings(
    "ignore",
    message=r".*non-text parts in the response.*",
)

__all__ = ["get_registry"]


def __getattr__(name: str):
    if name == "get_registry":
        from .service import get_registry

        return get_registry
    if name == "root_agent":
        from .service import get_registry

        registry = get_registry()
        style = registry.get("deploy_product")
        from .config import load_settings

        return style.build_pipeline(load_settings())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
