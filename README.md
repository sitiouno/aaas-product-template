# [Product Name]

> An AaaS product built with the MVP Factory template.

## Quick Start

1. Clone this repo
2. `cp .env.example .env` and configure
3. `pip install -e .`
4. `PRODUCT_ENABLE_DEV_AUTH=true python -m product_app.webapp`
5. Open http://127.0.0.1:8000

## How to Add Your Own Agents

1. Create a file in `product_app/research/my_agent.py`
2. Subclass `ResearchStyleBase` from `product_app/research/base.py`
3. Implement `build_pipeline()`, `get_stages()`, `get_section_titles()`
4. Add `STYLE = MyStyle()` at the bottom
5. The registry auto-discovers it!

See `product_app/research/hello_world.py` for a complete example.

## Architecture

- **FastAPI** web application with bilingual UI (EN/ES)
- **Google ADK** agent pipeline with auto-discovery
- **Cloud Run** deployment with GitHub Actions CI/CD
- **Cloud SQL** PostgreSQL database
- **Stripe** credit-based billing
- **Magic Link** authentication (email OTP)
- **SSE** real-time progress streaming
- **MCP** server for AI-to-AI integration

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Customization Guide](docs/CUSTOMIZATION.md)
- [Infrastructure Setup](docs/INFRASTRUCTURE.md)
- [Maintenance](docs/MAINTENANCE.md)

Built by [MVP Factory Studio](https://mvpfactory.studio)
