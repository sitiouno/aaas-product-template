# Maintenance Guide

## Security Patch Register

Track all security-related changes here.

| Date | Description | Files Changed | Severity |
|------|-------------|---------------|----------|
| _template_ | _Description of the security patch_ | _file1.py, file2.py_ | _low/medium/high/critical_ |

## Dependency Update Procedure

### Checking for Updates

```bash
# List outdated packages
pip list --outdated

# Check for known vulnerabilities
pip install pip-audit
pip-audit
```

### Updating Dependencies

1. Update the version constraint in `pyproject.toml`
2. Install and test locally:
   ```bash
   pip install -e .
   pytest tests/ -v
   ```
3. Run security scans:
   ```bash
   bandit -c .bandit.yml -r product_app
   flake8 product_app --select=F,E9,W6
   ```
4. Commit and push — CI/CD will run the full pipeline
5. Monitor the deployed service for errors after deployment

### Key Dependencies and Update Considerations

| Package | Notes |
|---------|-------|
| `google-adk` | Agent framework. Test pipeline execution after updates. |
| `google-genai` | Gemini SDK. Model names may change across versions. |
| `fastapi` | Web framework. Check for breaking changes in middleware/routing. |
| `sqlalchemy` | ORM. Major version changes may require migration scripts. |
| `stripe` | Billing API. Check webhook event schema changes. |
| `reportlab` | PDF generation. Test PDF output after updates. |
| `PyGithub` | Repo provisioning. Test repo creation flow. |

## Database Migration Procedure

The application uses SQLAlchemy models with `Base.metadata.create_all()` for schema creation. For schema changes:

### Adding a New Column

1. Add the column to the model in `product_app/models.py`:
   ```python
   new_column: Mapped[str | None] = mapped_column(String(255))
   ```

2. Generate the ALTER TABLE SQL:
   ```sql
   ALTER TABLE table_name ADD COLUMN new_column VARCHAR(255);
   ```

3. Apply to Cloud SQL:
   ```bash
   gcloud sql connect quien-prod --user=<db_user> --database=product_app
   # Then run the ALTER TABLE statement
   ```

4. Deploy the updated code (the new column is now recognized by the ORM)

### Adding a New Table

1. Define the model in `product_app/models.py`
2. The table is created automatically on next startup (`create_all()` is idempotent for new tables)
3. No manual SQL needed for new tables

### Renaming or Removing Columns

This requires careful coordination:

1. Add the new column (if renaming)
2. Deploy code that reads from both old and new columns
3. Migrate data: `UPDATE table SET new_col = old_col WHERE new_col IS NULL`
4. Deploy code that only uses the new column
5. Drop the old column: `ALTER TABLE table DROP COLUMN old_col`

### Backing Up Before Migrations

```bash
# Create a backup
gcloud sql backups create --instance=quien-prod

# List backups
gcloud sql backups list --instance=quien-prod
```

## Rollback Procedure

### Cloud Run Rollback

Cloud Run keeps previous revisions. To rollback:

```bash
# List revisions
gcloud run revisions list --service=product-name-studio --region=us-central1

# Route traffic to previous revision
gcloud run services update-traffic product-name-studio \
  --to-revisions=<previous-revision-name>=100 \
  --region=us-central1
```

### Git Rollback

If a bad commit reaches main:

```bash
# Revert the commit (creates a new commit, does not rewrite history)
git revert <commit-hash>
git push origin main
# CI/CD deploys the reverted version automatically
```

### Database Rollback

If a migration went wrong:

1. Restore from backup:
   ```bash
   gcloud sql backups restore <backup-id> --restore-instance=quien-prod
   ```
2. Roll back the code to match the previous schema
3. Deploy the rolled-back code

## Monitoring

### Health Check

```bash
curl https://PRODUCT_DOMAIN/api/health
```

Expected response: `{"status": "ok"}` with HTTP 200.

### Logs

```bash
# Cloud Run logs
gcloud run services logs read product-name-studio --region=us-central1 --limit=100

# Filter by severity
gcloud run services logs read product-name-studio --region=us-central1 --log-filter="severity>=ERROR"
```

### Key Metrics to Monitor

| Metric | Where | Alert Threshold |
|--------|-------|-----------------|
| Request latency | Cloud Run metrics | P99 > 30s |
| Error rate | Cloud Run metrics | > 5% of requests |
| Instance count | Cloud Run metrics | Sustained max instances |
| Database connections | Cloud SQL metrics | > 80% of max connections |
| Credit balance anomalies | `credit_transactions` table | Negative balance |
| Failed deployments | `analysis_runs` where status=failed | > 3 consecutive failures |

## Pre-Commit Hooks

The project uses pre-commit for local quality checks:

```bash
pip install pre-commit
pre-commit install
```

Hooks run on every commit:
- **Gitleaks** — prevents committing secrets
- **Whitespace/YAML checks** — formatting consistency

## Operational Runbook

### Common Issues

**Pipeline hangs or times out:**
- Check Gemini API quotas in GCP console
- Verify `GOOGLE_API_KEY` is valid and not rate-limited
- Check Cloud Run instance memory (increase if OOM)

**Stripe webhook failures:**
- Verify webhook signing secret matches (`STRIPE_WEBHOOK_SECRET_TEST` / `_LIVE`)
- Check Stripe dashboard for failed webhook deliveries
- Ensure the webhook URL is publicly accessible

**GitHub repo creation fails:**
- Verify `GITHUB_TOKEN` has `repo` scope
- Check that `GITHUB_ORG` exists and the token has org access
- Verify `TEMPLATE_REPO_NAME` exists in the org

**Magic link emails not arriving:**
- Check SMTP credentials (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`)
- Verify `MAGIC_LINK_FROM_EMAIL` is authorized by the SMTP provider
- Check spam folders

**Database connection errors:**
- Verify Cloud SQL instance is running: `gcloud sql instances describe quien-prod`
- Check connection name matches: `CLOUD_SQL_INSTANCE_CONNECTION_NAME`
- Ensure the Cloud Run service account has `roles/cloudsql.client`
