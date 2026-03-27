"""Common agent builders shared across research styles."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from ..tools import generate_html_report, generate_infographic


def build_report_formatter(settings: Any) -> LlmAgent:
    return LlmAgent(
        name="ReportFormatter",
        model=settings.report_model,
        description="Generates a styled HTML report from analysis results.",
        instruction="""You are a professional report formatter for Product Name.

Take the analysis results from previous agents and produce a polished, well-structured report.

Use the generate_html_report tool to create the final HTML and PDF artifacts.

The report should:
- Have a clear executive summary at the top
- Organize findings into logical sections with headers
- Use bullet points for key takeaways
- Include data tables where appropriate
- End with conclusions and recommendations

Format the content as clean Markdown before passing to the report generator.
Write in the language specified by the research request.
""",
        tools=[generate_html_report],
        output_key="report_result",
    )


def build_chart_generator(settings: Any) -> LlmAgent:
    return LlmAgent(
        name="ChartGenerator",
        model=settings.report_model,
        description="Creates visual infographic summaries.",
        instruction="""You are a data visualization specialist for Product Name.

Create an infographic that visually summarizes the key findings from the analysis.

Use the generate_infographic tool with the most important data points extracted from
the previous agents' outputs.

Extract these fields from the analysis:
- company_name or subject name
- key stage/category
- relevant dates or timeframes
- key metrics (market size, growth rate, risk score, etc.)
- overall recommendation or assessment

If a field is not available, use reasonable defaults like "N/A" or "Under Analysis".
""",
        tools=[generate_infographic],
        output_key="chart_result",
    )
