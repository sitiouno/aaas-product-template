"""Persistence helpers for user management, access control, credits, and run tracking."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import case, func, select

from .database import session_scope
from .models import (
    AccessRequest,
    AnalysisArtifact,
    AnalysisEvent,
    AnalysisRun,
    AnalysisSection,
    ApiKey,
    CreditTransaction,
    DeploymentStyle,
    RunStatus,
    User,
    utcnow,
)


# ── User management ─────────────────────────────────────────────────


def ensure_user(session, email: str, full_name: str = None) -> User:
    """Get or create user by email. New users start as 'pending'."""
    user = session.query(User).filter(func.lower(User.email) == email.lower()).first()
    if user:
        user.last_login_at = utcnow()
        return user
    user = User(email=email.lower(), full_name=full_name, status="pending")
    session.add(user)
    session.flush()
    return user


# ── Access requests ──────────────────────────────────────────────────


def create_access_request(session, email, full_name, company=None, message=None) -> str:
    """Create access request. Returns request ID. Deduplicates pending requests."""
    existing = session.query(AccessRequest).filter(
        func.lower(AccessRequest.email) == email.lower(),
        AccessRequest.status == "pending",
    ).first()
    if existing:
        return existing.id
    req = AccessRequest(
        email=email.lower(),
        full_name=full_name,
        company=company,
        message=message,
    )
    session.add(req)
    session.flush()
    return req.id


def list_access_requests(session, status="pending"):
    """List access requests filtered by status."""
    return (
        session.query(AccessRequest)
        .filter_by(status=status)
        .order_by(AccessRequest.created_at.desc())
        .all()
    )


def approve_access_request(session, request_id, reviewed_by_user_id, initial_credits=0):
    """Approve an access request. Creates or updates user. Optionally grants credits."""
    req = session.get(AccessRequest, request_id)
    req.status = "approved"
    req.reviewed_by = reviewed_by_user_id
    req.reviewed_at = utcnow()
    req.initial_credits = initial_credits

    # Check for existing user (re-request after rejection, or admin-created)
    user = session.query(User).filter(func.lower(User.email) == req.email.lower()).first()
    if user:
        user.status = "approved"
        user.full_name = user.full_name or req.full_name
    else:
        user = User(email=req.email, full_name=req.full_name, status="approved")
        session.add(user)
    session.flush()

    if initial_credits > 0:
        record_credit_transaction(
            session,
            user.id,
            amount=initial_credits,
            source_type="admin_grant",
            description="Initial grant on approval",
        )
    return req


def reject_access_request(session, request_id, reviewed_by_user_id):
    """Reject an access request."""
    req = session.get(AccessRequest, request_id)
    req.status = "rejected"
    req.reviewed_by = reviewed_by_user_id
    req.reviewed_at = utcnow()
    return req


# ── Platform settings ───────────────────────────────────────────────


def get_platform_setting(session, key: str, default: str | None = None) -> str | None:
    """Get a platform setting value, falling back to default."""
    from .models import PlatformSetting
    setting = session.get(PlatformSetting, key)
    return setting.value if setting else default


def set_platform_setting(session, key: str, value: str, updated_by: str | None = None) -> None:
    """Create or update a platform setting."""
    from .models import PlatformSetting
    setting = session.get(PlatformSetting, key)
    if setting:
        setting.value = value
        setting.updated_by = updated_by
    else:
        session.add(PlatformSetting(key=key, value=value, updated_by=updated_by))
    session.flush()


# ── Auto-registration ───────────────────────────────────────────────


def auto_register_user(session, email: str, full_name: str, initial_credits: int = 0) -> User:
    """Create a new approved user with optional initial credits. For open registration."""
    user = User(
        email=email.lower(),
        full_name=full_name,
        status="approved",
        onboarding_completed=False,
    )
    session.add(user)
    session.flush()

    if initial_credits > 0:
        record_credit_transaction(
            session,
            user.id,
            amount=initial_credits,
            source_type="signup_bonus",
            description=f"Welcome bonus: {initial_credits} credits",
        )
    return user


# ── Credits ──────────────────────────────────────────────────────────


def get_credit_balance(session, user_id: str) -> int:
    """Get the current credit balance for a user."""
    result = session.query(
        func.coalesce(func.sum(CreditTransaction.amount), 0)
    ).filter(
        CreditTransaction.user_id == user_id
    ).scalar()
    return int(result)


def record_credit_transaction(
    session,
    user_id,
    amount,
    source_type,
    run_id=None,
    api_key_id=None,
    estimated_cost_usd=None,
    description=None,
    external_reference=None,
) -> CreditTransaction:
    """Record a credit transaction. Idempotent when external_reference is provided."""
    if external_reference:
        existing = (
            session.query(CreditTransaction)
            .filter_by(source_type=source_type, external_reference=external_reference)
            .first()
        )
        if existing:
            return existing

    balance = get_credit_balance(session, user_id)
    tx = CreditTransaction(
        user_id=user_id,
        run_id=run_id,
        api_key_id=api_key_id,
        amount=amount,
        balance_after=balance + amount,
        source_type=source_type,
        estimated_cost_usd=estimated_cost_usd,
        description=description,
        external_reference=external_reference,
    )
    session.add(tx)
    session.flush()
    return tx


# ── Usage analytics ──────────────────────────────────────────────────


def get_daily_usage(session, user_id, days=30):
    """Credit consumption grouped by day."""
    since = utcnow() - timedelta(days=days)
    rows = (
        session.query(
            func.date(CreditTransaction.created_at).label("day"),
            func.sum(
                case(
                    (CreditTransaction.amount < 0, -CreditTransaction.amount),
                    else_=0,
                )
            ).label("credits_consumed"),
            func.sum(
                func.coalesce(CreditTransaction.estimated_cost_usd, 0)
            ).label("estimated_cost"),
            func.count(CreditTransaction.run_id.distinct()).label("run_count"),
        )
        .filter(
            CreditTransaction.user_id == user_id,
            CreditTransaction.created_at >= since,
        )
        .group_by(func.date(CreditTransaction.created_at))
        .order_by(func.date(CreditTransaction.created_at).desc())
        .all()
    )
    return [
        {
            "day": str(r.day),
            "credits": int(r.credits_consumed),
            "cost_usd": round(float(r.estimated_cost), 4),
            "runs": int(r.run_count),
        }
        for r in rows
    ]


def get_usage_by_api_key(session, user_id):
    """Consumption grouped by API key."""
    rows = (
        session.query(
            ApiKey.id,
            ApiKey.label,
            ApiKey.key_prefix,
            func.sum(
                case(
                    (CreditTransaction.amount < 0, -CreditTransaction.amount),
                    else_=0,
                )
            ).label("credits_consumed"),
            func.sum(
                func.coalesce(CreditTransaction.estimated_cost_usd, 0)
            ).label("estimated_cost"),
            func.count(CreditTransaction.run_id.distinct()).label("run_count"),
        )
        .outerjoin(CreditTransaction, CreditTransaction.api_key_id == ApiKey.id)
        .filter(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
        .group_by(ApiKey.id, ApiKey.label, ApiKey.key_prefix)
        .all()
    )
    return [
        {
            "api_key_id": r.id,
            "label": r.label,
            "prefix": r.key_prefix,
            "credits": int(r.credits_consumed or 0),
            "cost_usd": round(float(r.estimated_cost or 0), 4),
            "runs": int(r.run_count or 0),
        }
        for r in rows
    ]


# ── Bootstrap ────────────────────────────────────────────────────────


def bootstrap_defaults(session, settings):
    """Create admin user and seed Stripe settings from env vars."""
    import os
    admin_email = getattr(settings, "admin_email", None) or os.getenv("PRODUCT_ADMIN_EMAIL", "")
    if admin_email:
        admin_email = admin_email.strip().lower()
    if admin_email:
        user = session.query(User).filter(func.lower(User.email) == admin_email).first()
        if not user:
            user = User(email=admin_email, is_admin=True, status="approved")
            session.add(user)
            session.flush()
        else:
            if not user.is_admin:
                user.is_admin = True
            if user.status != "approved":
                user.status = "approved"

    # Seed Stripe keys from env vars into platform_settings (only if not already set).
    # This ensures keys survive Cloud Run redeploys that drop --update-secrets.
    _stripe_env_keys = [
        ("stripe_secret_key_test", "STRIPE_SECRET_KEY_TEST"),
        ("stripe_secret_key_live", "STRIPE_SECRET_KEY_LIVE"),
        ("stripe_publishable_key_test", "STRIPE_PUBLISHABLE_KEY_TEST"),
        ("stripe_publishable_key_live", "STRIPE_PUBLISHABLE_KEY_LIVE"),
        ("stripe_webhook_secret_test", "STRIPE_WEBHOOK_SECRET_TEST"),
        ("stripe_webhook_secret_live", "STRIPE_WEBHOOK_SECRET_LIVE"),
        ("stripe_credit_price_id_test", "STRIPE_CREDIT_PRICE_ID_TEST"),
        ("stripe_credit_price_id_live", "STRIPE_CREDIT_PRICE_ID_LIVE"),
    ]
    for db_key, env_key in _stripe_env_keys:
        env_val = os.getenv(env_key, "").strip()
        if env_val and not get_platform_setting(session, db_key):
            set_platform_setting(session, db_key, env_val)


# ── Run management ───────────────────────────────────────────────────


def create_run_record(
    session,
    job_id: str,
    prompt: str,
    *,
    user_id: str,
    research_style: str = DeploymentStyle.DEPLOY_PRODUCT.value,
    language: str = "en",
    webhook_url: str | None = None,
    api_key_id: str | None = None,
) -> AnalysisRun:
    """Create or retrieve an analysis run record."""
    run = session.scalar(select(AnalysisRun).where(AnalysisRun.public_job_id == job_id))
    if run is not None:
        return run

    run = AnalysisRun(
        public_job_id=job_id,
        user_id=user_id,
        prompt=prompt,
        research_style=research_style,
        language=language,
        status=RunStatus.QUEUED.value,
        progress_pct=0,
        webhook_url=webhook_url,
        api_key_id=api_key_id,
    )
    session.add(run)
    session.flush()
    return run


def persist_run_event(
    job_id: str,
    event_type: str,
    snapshot: dict[str, Any],
    message: str | None = None,
) -> None:
    """Update run state from an event snapshot and record the event."""
    with session_scope() as session:
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.public_job_id == job_id))
        if run is None:
            return

        status_value = snapshot.get("status") or run.status
        run.status = status_value
        run.progress_pct = int(snapshot.get("progress_pct") or snapshot.get("progress_percent") or 0)
        run.error_message = snapshot.get("error") or None

        if snapshot.get("language"):
            run.language = snapshot["language"]
        if snapshot.get("research_style"):
            run.research_style = snapshot["research_style"]

        if run.status == RunStatus.RUNNING.value and run.started_at is None:
            run.started_at = utcnow()
        if run.status in {RunStatus.COMPLETED.value, RunStatus.FAILED.value}:
            run.completed_at = run.completed_at or utcnow()
            # Update credits_consumed from actual credit transactions
            if run.credits_consumed == 0:
                consumed = session.query(
                    func.coalesce(func.sum(CreditTransaction.amount), 0)
                ).filter(
                    CreditTransaction.external_reference == f"run:{run.public_job_id}",
                    CreditTransaction.source_type == "run_debit",
                ).scalar()
                if consumed:
                    run.credits_consumed = abs(int(consumed))

        event_author = "system"
        event_message = message or "Run state updated."
        if event_type == "log" and snapshot.get("logs"):
            latest_log = snapshot["logs"][-1]
            event_author = latest_log.get("author") or "system"
            event_message = latest_log.get("message") or event_message

        session.add(
            AnalysisEvent(
                run_id=run.id,
                event_type=event_type,
                author=event_author,
                message=event_message,
            )
        )

        if run.status == RunStatus.COMPLETED.value:
            _replace_sections(session, run, snapshot.get("sections", []))
            _replace_artifacts(session, run, snapshot.get("artifacts", []))


def _replace_sections(session, run: AnalysisRun, sections: list[dict[str, Any]]) -> None:
    """Replace all sections for a run."""
    session.query(AnalysisSection).filter(AnalysisSection.run_id == run.id).delete()
    for index, section in enumerate(sections):
        session.add(
            AnalysisSection(
                run_id=run.id,
                section_id=str(section.get("id") or f"section_{index}"),
                title=str(section.get("title") or f"Section {index + 1}"),
                body_text=str(section.get("text") or ""),
                body_html=section.get("html"),
                display_order=index,
            )
        )


def _replace_artifacts(session, run: AnalysisRun, artifacts: list[dict[str, Any]]) -> None:
    """Replace all artifacts for a run, storing file content in DB for durability."""
    from .config import load_settings

    session.query(AnalysisArtifact).filter(AnalysisArtifact.run_id == run.id).delete()
    mime_by_kind = {
        "image": "image/*",
        "report_html": "text/html",
        "report_pdf": "application/pdf",
        "file": "application/octet-stream",
    }
    settings = load_settings()
    for artifact in artifacts:
        file_name = str(artifact.get("name") or "artifact")
        # Read file content from disk so artifacts survive container restarts
        content: bytes | None = None
        try:
            local_path = settings.output_dir / file_name
            if local_path.exists():
                content = local_path.read_bytes()
        except OSError:
            content = None
        session.add(
            AnalysisArtifact(
                run_id=run.id,
                name=file_name,
                storage_path=str(artifact.get("path") or artifact.get("name") or "artifact"),
                public_url=str(artifact.get("url") or ""),
                artifact_kind=str(artifact.get("kind") or "file"),
                mime_type=artifact.get("mime_type") or mime_by_kind.get(
                    str(artifact.get("kind") or "file")
                ),
                size_bytes=artifact.get("size_bytes"),
                content=content,
                is_public=bool(artifact.get("is_public", False)),
                requires_payment=bool(artifact.get("requires_payment", True)),
            )
        )


# ── Deployed products ────────────────────────────────────────────────


def create_deployed_product(
    session,
    user_id: str,
    run_id: str,
    product_name: str,
    product_slug: str,
    *,
    repo_full_name: str | None = None,
    repo_url: str | None = None,
    cloud_run_url: str | None = None,
    custom_domain: str | None = None,
    template_repo: str | None = None,
    agent_config_json: str | None = None,
) -> "DeployedProduct":
    """Create a new deployed product record."""
    from .models import DeployedProduct
    product = DeployedProduct(
        user_id=user_id,
        run_id=run_id,
        product_name=product_name,
        product_slug=product_slug,
        repo_full_name=repo_full_name,
        repo_url=repo_url,
        cloud_run_url=cloud_run_url,
        custom_domain=custom_domain,
        template_repo=template_repo,
        agent_config_json=agent_config_json,
    )
    session.add(product)
    session.flush()
    return product


def update_product_status(
    session,
    product_id: str,
    status: str,
    cloud_run_url: str | None = None,
) -> None:
    """Update a deployed product's status and optional Cloud Run URL."""
    from .models import DeployedProduct
    product = session.get(DeployedProduct, product_id)
    if product:
        product.status = status
        if cloud_run_url:
            product.cloud_run_url = cloud_run_url


def list_user_products(session, user_id: str) -> list:
    """List all deployed products for a user, newest first."""
    from .models import DeployedProduct
    return (
        session.query(DeployedProduct)
        .filter(DeployedProduct.user_id == user_id)
        .order_by(DeployedProduct.created_at.desc())
        .all()
    )


def list_recent_runs(
    session,
    *,
    user_id: str | None = None,
    limit: int = 10,
    status: str | None = None,
    research_style: str | None = None,
    query_text: str | None = None,
) -> list[dict[str, Any]]:
    """List recent runs, optionally filtered by user and criteria."""
    query = select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    if user_id:
        query = query.where(AnalysisRun.user_id == user_id)
    if status is not None:
        query = query.where(AnalysisRun.status == status)
    if research_style is not None:
        query = query.where(AnalysisRun.research_style == research_style)
    if query_text:
        normalized_query = query_text.strip()
        if normalized_query:
            query = query.where(AnalysisRun.prompt.ilike(f"%{normalized_query}%"))

    runs = session.scalars(query.limit(limit)).all()
    return [
        {
            "job_id": run.public_job_id,
            "prompt": run.prompt,
            "research_style": run.research_style,
            "language": run.language,
            "status": run.status,
            "progress_pct": run.progress_pct,
            "report_types": sorted({artifact.artifact_kind for artifact in run.artifacts}),
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
        for run in runs
    ]
