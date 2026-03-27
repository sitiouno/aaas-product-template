"""Abstract base class for research styles."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StageDefinition:
    """Defines a pipeline stage for progress tracking."""

    id: str
    agent_name: str
    title: str
    description: str
    output_key: str | None = None


class ResearchStyleBase(ABC):
    """Base class all research styles must implement."""

    key: str
    name_en: str
    name_es: str
    description_en: str
    description_es: str
    credit_cost: int
    agent_count: int
    estimated_duration_minutes: tuple[int, int]

    @abstractmethod
    def build_pipeline(self, settings: Any) -> Any:
        """Build and return the ADK root agent for this style."""
        ...

    @abstractmethod
    def get_stages(self) -> list[StageDefinition]:
        """Return ordered stage definitions for progress tracking."""
        ...

    @abstractmethod
    def get_section_titles(self) -> dict[str, str]:
        """Return mapping of output_key to display title for report sections."""
        ...

    def name_for_language(self, language: str) -> str:
        """Return localized name (fallback to English)."""
        if language == "es":
            return self.name_es
        return self.name_en

    def description_for_language(self, language: str) -> str:
        """Return localized description (fallback to English)."""
        if language == "es":
            return self.description_es
        return self.description_en
