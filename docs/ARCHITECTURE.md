# Architecture

## System Overview

Product Name is a FastAPI application that orchestrates Google ADK (Agent Development Kit) agent pipelines to provision complete AaaS (Agents as a Service) products. When a user describes a product, the system runs a 6-agent pipeline that creates a GitHub repo, database, Cloud Run service, Stripe billing, landing page, and documentation.

## High-Level Data Flow

```
                        ┌──────────────────────┐
                        │   PRODUCT_DOMAIN   │
                        │    (Cloud Run)        │
                        └─────────┬────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
     ┌────────▼────────┐  ┌──────▼───────┐  ┌───────▼────────┐
     │  FastAPI webapp  │  │  Static UI   │  │   MCP Server   │
     │  (webapp.py)     │  │  (app.js)    │  │  (mcp_server)  │
     └────────┬────────┘  └──────────────┘  └────────────────┘
              │
     ┌────────▼────────┐
     │  Service Layer   │  service.py — orchestrates pipeline execution
     │  (service.py)    │  persistence.py — all database CRUD
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  ADK Pipeline    │  research/deploy_product.py
     │  (6 agents)      │  Uses tools from tools_factory.py
     └────────┬────────┘
              │
    ┌─────────┼─────────┬──────────┬──────────┐
    │         │         │          │          │
┌───▼──┐ ┌───▼───┐ ┌───▼──┐ ┌────▼───┐ ┌───▼────┐
│GitHub│ │Cloud  │ │Cloud │ │Stripe  │ │Report  │
│ API  │ │ SQL   │ │ Run  │ │  API   │ │  Lab   │
└──────┘ └───────┘ └──────┘ └────────┘ └────────┘
```

## File Responsibilities

### Core Application

| File | Responsibility |
|------|---------------|
| `webapp.py` | FastAPI routes, middleware, SSE streaming, static file serving, OpenAPI schema |
| `config.py` | Loads all environment variables into a frozen `Settings` dataclass |
| `models.py` | SQLAlchemy ORM models for all database tables |
| `service.py` | Pipeline execution engine: creates runs, dispatches to ADK, handles progress |
| `persistence.py` | Database CRUD operations (create/read/update for all models) |
| `database.py` | SQLAlchemy engine, session factory, Cloud SQL connector |
| `site_renderer.py` | Server-rendered HTML for landing page, app shell, and public pages |

### Authentication & Billing

| File | Responsibility |
|------|---------------|
| `security.py` | Session tokens (HMAC-signed cookies), API key hashing/verification, Identity resolution |
| `magic_link.py` | OTP generation, email sending, verification flow |
| `otp_email.py` | Email template for magic link OTP codes |
| `stripe_billing.py` | Stripe checkout sessions, customer portal, webhook handling, credit fulfillment |
| `webhooks.py` | Stripe webhook endpoint and event processing |

### Agent Pipeline

| File | Responsibility |
|------|---------------|
| `research/base.py` | `ResearchStyleBase` abstract class and `StageDefinition` dataclass |
| `research/registry.py` | Auto-discovers style modules, maintains registry of available pipelines |
| `research/deploy_product.py` | The 6-agent `DeployProductStyle`: InputParser, WebDesigner, SEOOptimizer, InfraProvisioner, StripeBootstrapper, DocsGenerator |
| `research/health_check.py` | Health monitoring for deployed products |
| `tools_factory.py` | ADK tool functions: `create_github_repo`, `create_cloud_sql_database`, `deploy_cloud_run_service`, `map_domain`, `bootstrap_stripe_product`, `generate_pdf_guide`, `write_file_to_repo` |
| `tools.py` | Report rendering tools (Markdown to HTML, PDF generation) |

### Supporting

| File | Responsibility |
|------|---------------|
| `runner.py` | CLI entry point for running pipelines from the command line |
| `ops.py` | Operational utilities (database initialization) |
| `artifact_storage.py` | GCS artifact upload/download, local fallback |
| `email_validator.py` | Email format and domain validation (blocks disposable domains) |
| `email_templates.py` | HTML email templates for notifications |
| `report_email.py` | Sends completed report/deployment notifications via email |
| `mcp_server.py` | MCP (Model Context Protocol) server for AI-to-AI integration |

## Database Schema

The application uses SQLAlchemy 2.0 with mapped columns. All tables use UUID primary keys.

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User accounts | email, stripe_customer_id (test/live), is_admin, language |
| `api_keys` | API authentication | user_id, key_prefix, secret_hash, scopes, rate_limit_rpm |
| `credit_transactions` | Credit ledger | user_id, run_id, amount, balance_after, source_type |
| `analysis_runs` | Pipeline executions | user_id, prompt, research_style, status, progress_pct |
| `analysis_events` | Run progress log | run_id, event_type, stage_id, message |
| `analysis_sections` | Run output sections | run_id, section_id, title, body_text, body_html |
| `analysis_artifacts` | Generated files | run_id, name, storage_path, mime_type, content |
| `deployed_products` | Provisioned products | run_id, user_id, product_name, product_slug, repo_url, cloud_run_url |
| `access_requests` | Signup requests | email, full_name, company, status |
| `platform_settings` | Key-value config | key, value |

### Entity Relationships

```
User 1──* ApiKey
User 1──* CreditTransaction
User 1──* AnalysisRun
AnalysisRun 1──* AnalysisEvent
AnalysisRun 1──* AnalysisSection
AnalysisRun 1──* AnalysisArtifact
AnalysisRun 1──* CreditTransaction
AnalysisRun 1──1 DeployedProduct
```

## Request Flow

### Web Authentication Flow

1. User visits `/` → `site_renderer.render_landing()` returns HTML
2. User enters email → `POST /api/auth/magic-link/request` → OTP email sent
3. User enters OTP → `POST /api/auth/magic-link/verify` → session cookie set
4. Authenticated requests carry `quien_session` cookie → `parse_session_token()` resolves identity

### API Authentication Flow

1. User creates API key via dashboard → key returned once (prefix + secret)
2. API requests carry `Authorization: Bearer <key>` header
3. `authenticate_api_key()` hashes the secret and matches against `api_keys.secret_hash`

### Deployment Pipeline Flow

1. `POST /api/v1/runs` with `{ prompt, research_style: "deploy_product" }`
2. `service.py` checks credits, creates `AnalysisRun`, dispatches to background task
3. `deploy_product.py` builds ADK `SequentialAgent` with 6 child `LlmAgent`s
4. Each agent stage emits progress events via SSE
5. Tools in `tools_factory.py` call GitHub API, GCP APIs, Stripe API
6. On completion, `DeployedProduct` record is created with URLs
7. Credits are deducted from user balance

## Configuration Architecture

All configuration is loaded at startup via `config.py`:
- Environment variables (`.env` file for local, Secret Manager for production)
- Frozen `Settings` dataclass prevents runtime mutation
- Placeholder detection prevents accidental deployment with dummy values
- Stripe supports dual test/live mode with per-mode customer IDs and price IDs
