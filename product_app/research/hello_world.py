"""Hello World — sample research style for new products."""

from __future__ import annotations
from typing import Any

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search

from .base import ResearchStyleBase, StageDefinition


class HelloWorldStyle(ResearchStyleBase):
    key = "hello_world"
    name_en = "Hello World"
    name_es = "Hola Mundo"
    description_en = "A sample agent pipeline. Replace with your own agents."
    description_es = "Un pipeline de agentes de ejemplo. Reemplaza con tus propios agentes."
    credit_cost = 1
    agent_count = 2
    estimated_duration_minutes = (1, 2)

    def get_stages(self) -> list[StageDefinition]:
        return [
            StageDefinition(
                id="research",
                agent_name="ResearchAgent",
                title="Research",
                description="Gathering information...",
                output_key="research_result",
            ),
            StageDefinition(
                id="report",
                agent_name="ReportAgent",
                title="Report",
                description="Generating report...",
                output_key="report_result",
            ),
        ]

    def get_section_titles(self) -> dict[str, str]:
        return {
            "research_result": "Research Results",
            "report_result": "Final Report",
        }

    def build_pipeline(self, settings: Any) -> LlmAgent:
        researcher = LlmAgent(
            name="ResearchAgent",
            model=settings.search_model,
            description="Researches the given topic.",
            instruction="""You are a research agent. Use Google Search to find information about the user's topic.
Provide factual, well-organized information with sources.""",
            tools=[google_search],
            output_key="research_result",
        )
        reporter = LlmAgent(
            name="ReportAgent",
            model=settings.report_model,
            description="Generates a report from research.",
            instruction="Using {research_result}, write a clear, well-structured report.",
            output_key="report_result",
        )
        pipeline = SequentialAgent(
            name="hello_world_pipeline",
            description="Sample pipeline.",
            sub_agents=[researcher, reporter],
        )
        return LlmAgent(
            name="hello_world_coordinator",
            model=settings.coordinator_model,
            description="Coordinates the sample pipeline.",
            instruction="Run the pipeline and return the final report.",
            sub_agents=[pipeline],
            output_key="hw_final",
        )


STYLE = HelloWorldStyle()
