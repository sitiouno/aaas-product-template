# Customization Guide

## Adding a New Agent Pipeline Style

The system uses a style registry that auto-discovers pipeline modules. To add a new pipeline:

### Step 1: Create the Style Module

Create a new file in `product_app/research/`:

```python
# product_app/research/my_custom_style.py
"""My Custom Style — description of what this pipeline does."""

from __future__ import annotations
from typing import Any
from .base import ResearchStyleBase, StageDefinition


class MyCustomStyle(ResearchStyleBase):
    """Description of this pipeline."""

    key = "my_custom_style"               # Unique identifier (used in API)
    name_en = "My Custom Pipeline"        # Display name (English)
    name_es = "Mi Pipeline Personalizado" # Display name (Spanish)
    description_en = "Does something useful with AI agents."
    description_es = "Hace algo util con agentes de IA."
    credit_cost = 3                       # Credits consumed per run
    agent_count = 4                       # Number of agents in pipeline
    estimated_duration_minutes = (2, 5)   # (min, max) estimate

    _STAGES = [
        StageDefinition(
            id="stage_one",
            agent_name="FirstAgent",
            title="First Stage",
            description="What the first agent does.",
            output_key="first_output",
        ),
        StageDefinition(
            id="stage_two",
            agent_name="SecondAgent",
            title="Second Stage",
            description="What the second agent does.",
            output_key="second_output",
        ),
        # ... more stages
    ]

    def get_stages(self) -> list[StageDefinition]:
        return list(self._STAGES)

    def get_section_titles(self) -> dict[str, str]:
        return {stage.output_key: stage.title for stage in self._STAGES}

    def build_pipeline(self, settings: Any) -> Any:
        """Build the ADK agent pipeline."""
        from google.adk.agents import LlmAgent, SequentialAgent

        agent_one = LlmAgent(
            name="FirstAgent",
            model="gemini-3-flash-preview",
            instruction="Your prompt here...",
            output_key="first_output",
        )

        agent_two = LlmAgent(
            name="SecondAgent",
            model="gemini-3-flash-preview",
            instruction="Your prompt here...",
            output_key="second_output",
        )

        return SequentialAgent(
            name="my_custom_pipeline",
            sub_agents=[agent_one, agent_two],
        )


# IMPORTANT: The registry auto-discovers this variable
STYLE = MyCustomStyle()
```

### Step 2: Verify Auto-Discovery

The registry in `product_app/research/registry.py` scans all `.py` files in the `research/` directory for a module-level `STYLE` variable. No manual registration is needed.

Restart the application and verify:

```bash
# Check capabilities endpoint
curl http://127.0.0.1:8000/api/v1/research/capabilities
```

Your new style should appear in the response.

### Step 3: Test the Style

Create a test file:

```python
# tests/test_my_custom_style.py
from product_app.research.my_custom_style import MyCustomStyle

def test_style_attributes():
    style = MyCustomStyle()
    assert style.key == "my_custom_style"
    assert len(style.get_stages()) == style.agent_count

def test_build_pipeline():
    style = MyCustomStyle()
    pipeline = style.build_pipeline(settings=None)
    assert pipeline is not None
```

## Changing Branding

### Website Name and Tagline

Set these environment variables:

```bash
WEBSITE_NAME="Your Product Name"
WEBSITE_TAGLINE_EN="Your English tagline."
WEBSITE_TAGLINE_ES="Tu eslogan en espanol."
COMPANY_LEGAL_NAME="Your Company LLC"
SUPPORT_EMAIL="support@yourdomain.com"
```

### Landing Page Content

The landing page is server-rendered in `product_app/site_renderer.py`. The `render_landing()` function generates the full HTML. Key customization points:

- Hero section: headline, subheadline, CTA
- Feature cards: title + description pairs
- Pricing section: credit packs and descriptions
- Footer: company info, legal links

All text uses the `_t(language, english, spanish)` helper for bilingual support.

### Styles

CSS is in `product_app/static/app.css`. The default is a dark theme. Override CSS variables at the top of the file to change colors:

```css
:root {
    --bg-primary: #0a0a0a;
    --text-primary: #e0e0e0;
    --accent: #4fc3f7;
}
```

## Adding API Endpoints

### Step 1: Define the Route

Add routes in `product_app/webapp.py`. Follow the existing pattern:

```python
@app.get("/api/v1/my-endpoint")
async def my_endpoint(request: Request):
    identity = _require_auth(request)  # Enforce authentication
    # Your logic here
    return JSONResponse({"result": "ok"})
```

### Step 2: Add Database Operations

If your endpoint needs database access, add CRUD functions in `product_app/persistence.py`:

```python
async def get_my_data(session, user_id: str):
    result = await session.execute(
        select(MyModel).where(MyModel.user_id == user_id)
    )
    return result.scalars().all()
```

### Step 3: Update OpenAPI Docs

The OpenAPI schema is auto-generated by FastAPI. Add Pydantic models for request/response bodies:

```python
class MyRequest(BaseModel):
    field: str = Field(..., description="Description of field")

class MyResponse(BaseModel):
    result: str
```

## Configuring Environment Variables

All configuration is centralized in `product_app/config.py`. To add a new setting:

1. Add the field to the `Settings` dataclass:

```python
@dataclass(frozen=True)
class Settings:
    # ... existing fields ...
    my_new_setting: str
```

2. Load it in `load_settings()`:

```python
return Settings(
    # ... existing fields ...
    my_new_setting=os.getenv("MY_NEW_SETTING", "default_value"),
)
```

3. Add to `.env.example`:

```bash
MY_NEW_SETTING=default_value
```

4. For production, add the secret to GCP Secret Manager and reference it in the Cloud Run service configuration.

## Adding ADK Tools

Tools are functions that ADK agents can call. Define them in `product_app/tools_factory.py`:

```python
def my_custom_tool(
    param1: str,
    param2: int,
    tool_context: ToolContext,
) -> dict:
    """Description of what this tool does.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        dict with results.
    """
    # Your implementation
    return {"status": "success", "data": result}
```

Then reference the tool in your agent's `tools` list in `build_pipeline()`:

```python
from ..tools_factory import my_custom_tool

agent = LlmAgent(
    name="MyAgent",
    model="gemini-3-flash-preview",
    instruction="...",
    tools=[my_custom_tool],
)
```
