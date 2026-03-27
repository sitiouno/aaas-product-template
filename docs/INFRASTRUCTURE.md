# Infrastructure Guide

## GCP Project Setup

### Project Details

| Setting | Value |
|---------|-------|
| Project ID | `test-agents-ai-app` |
| Region | `us-central1` |
| Cloud Run service | `product-name-studio` |
| Cloud SQL instance | `quien-prod` |
| Database name | `product_app` |
| Artifact Registry | `us-central1-docker.pkg.dev/test-agents-ai-app/product-name` |

### Required APIs

Enable these GCP APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com
```

### Service Accounts

| Account | Purpose |
|---------|---------|
| `github-actions-deploy@test-agents-ai-app.iam.gserviceaccount.com` | CI/CD deployment via Workload Identity Federation |
| Cloud Run runtime SA | Application runtime (Cloud SQL client, Secret Manager accessor, GCS writer) |

### Workload Identity Federation

GitHub Actions authenticates to GCP using Workload Identity Federation (no long-lived keys):

- Pool: `github-actions-pool`
- Provider: `github-provider`
- Full provider path: `projects/418791284533/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider`

## Cloud SQL

### Instance Configuration

- Instance name: `quien-prod`
- Engine: PostgreSQL (latest stable)
- Region: `us-central1`
- Connection type: Cloud SQL Connector (via `cloud-sql-python-connector[pg8000]`)

### Creating the Database

The application auto-creates the database on startup if `DATABASE_AUTO_CREATE=true` (default). For manual creation:

```bash
gcloud sql databases create product_app --instance=quien-prod
```

### Connection from Cloud Run

Cloud Run connects to Cloud SQL using the Cloud SQL Connector library. Set:

```bash
CLOUD_SQL_INSTANCE_CONNECTION_NAME=test-agents-ai-app:us-central1:quien-prod
DATABASE_NAME=product_app
DATABASE_USER=<db_user>
DATABASE_PASSWORD=<db_password>
```

The connector handles SSL and IAM authentication automatically.

### Connection Pooling

Default pool settings (tunable via environment variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_POOL_SIZE` | 5 | SQLAlchemy pool size |
| `DATABASE_MAX_OVERFLOW` | 5 | Max connections above pool size |

### Local Development Database

By default, local development uses SQLite at `product_app/app.db`. To use a local PostgreSQL:

```bash
DATABASE_URL=postgresql+pg8000://user:pass@localhost:5432/product_app
```

## Cloud Run Deployment

### Manual Deployment

```bash
# Build and push
docker build -t us-central1-docker.pkg.dev/test-agents-ai-app/product-name/product-name-studio:latest .
docker push us-central1-docker.pkg.dev/test-agents-ai-app/product-name/product-name-studio:latest

# Deploy
gcloud run deploy product-name-studio \
  --image=us-central1-docker.pkg.dev/test-agents-ai-app/product-name/product-name-studio:latest \
  --region=us-central1 \
  --allow-unauthenticated \
  --port=8000 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --set-secrets=<secret-mappings>
```

### CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/deploy.yml`) runs on push to `main`:

1. **Gitleaks** — scans for leaked secrets in the repository
2. **Flake8** — checks for syntax errors and undefined names (`--select=F,E9,W6`)
3. **Bandit** — security vulnerability scanner (`-c .bandit.yml`)
4. **Docker build** — builds the container image
5. **Push to Artifact Registry** — pushes the image
6. **Deploy to Cloud Run** — deploys the new revision

### Environment Variables on Cloud Run

Secrets are stored in GCP Secret Manager and mounted as environment variables. Key secrets:

| Secret | Description |
|--------|-------------|
| `APP_SESSION_SECRET` | HMAC signing key for session cookies |
| `GOOGLE_API_KEY` | Gemini API key |
| `STRIPE_SECRET_KEY_TEST` | Stripe test mode key |
| `STRIPE_SECRET_KEY_LIVE` | Stripe live mode key |
| `STRIPE_WEBHOOK_SECRET_TEST` | Stripe webhook signing (test) |
| `STRIPE_WEBHOOK_SECRET_LIVE` | Stripe webhook signing (live) |
| `MAGIC_LINK_SECRET` | HMAC key for magic link OTP tokens |
| `SMTP_PASSWORD` | Email sending password |
| `GITHUB_TOKEN` | PAT for creating repos in the org |
| `DATABASE_PASSWORD` | Cloud SQL password |

### Health Check

Cloud Run uses the `/api/health` endpoint for liveness probes.

## Secret Manager

### Adding a New Secret

```bash
# Create the secret
echo -n "secret-value" | gcloud secrets create MY_SECRET --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding MY_SECRET \
  --member="serviceAccount:<runtime-sa>@test-agents-ai-app.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Mount in Cloud Run
gcloud run services update product-name-studio \
  --update-secrets=MY_ENV_VAR=MY_SECRET:latest
```

### Rotating a Secret

```bash
# Add new version
echo -n "new-secret-value" | gcloud secrets versions add MY_SECRET --data-file=-

# Deploy new revision to pick up the change
gcloud run services update product-name-studio --region=us-central1
```

## Domain Mapping

### DNS Configuration

Point your domain to Cloud Run:

```bash
gcloud run domain-mappings create \
  --service=product-name-studio \
  --domain=PRODUCT_DOMAIN \
  --region=us-central1
```

Then configure DNS records as instructed by the output (typically CNAME to `ghs.googlehosted.com`).

### SSL/TLS

Cloud Run provides automatic SSL certificate provisioning and renewal via Google-managed certificates.

## Stripe Configuration

### Test vs Live Mode

The application supports dual Stripe modes with separate credentials:

| Test Mode | Live Mode |
|-----------|-----------|
| `STRIPE_SECRET_KEY_TEST` | `STRIPE_SECRET_KEY_LIVE` |
| `STRIPE_PUBLISHABLE_KEY_TEST` | `STRIPE_PUBLISHABLE_KEY_LIVE` |
| `STRIPE_WEBHOOK_SECRET_TEST` | `STRIPE_WEBHOOK_SECRET_LIVE` |
| `STRIPE_CREDIT_PRICE_ID_TEST` | `STRIPE_CREDIT_PRICE_ID_LIVE` |

Users have separate `stripe_customer_id_test` and `stripe_customer_id_live` columns.

### Bootstrap Script

To create Stripe products, prices, and webhook endpoints:

```bash
python scripts/bootstrap_stripe.py --base-url https://PRODUCT_DOMAIN
```

### Webhook Endpoint

The Stripe webhook endpoint is at `/api/webhooks/stripe`. It handles:
- `checkout.session.completed` — fulfills credit purchases
- `customer.subscription.created` / `updated` / `deleted` — manages subscriptions

### Go-Live Checklist

See `docs/stripe_go_live_checklist.md` for the full Stripe production readiness checklist.

## Bootstrap Scripts

| Script | Purpose |
|--------|---------|
| `scripts/bootstrap_gcp.ps1` | Creates GCP resources (Cloud SQL, Artifact Registry, IAM) |
| `scripts/deploy_cloud_run.ps1` | Builds and deploys to Cloud Run |
| `scripts/bootstrap_stripe.py` | Creates Stripe products, prices, webhook endpoints |
| `scripts/install_mcp_toolbox.ps1` | Installs MCP Toolbox for Databases locally |
| `scripts/install_gcloud_mcp.ps1` | Installs Google Cloud MCP server locally |
| `scripts/install_stripe_mcp.ps1` | Installs Stripe MCP server locally |
