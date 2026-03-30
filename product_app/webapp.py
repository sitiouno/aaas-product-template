"""FastAPI web application for Product Name."""

from __future__ import annotations
from fastapi.openapi.utils import get_openapi

import asyncio
import html as html_module
import json
import logging
import os
import sys
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import uvicorn
from fastapi.security import APIKeyHeader
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse
from sqlalchemy import select, text, func

from .artifact_storage import download_artifact
from .config import load_settings
from .database import dispose_database, initialize_database, session_scope
from .models import (
    AccessRequest,
    AnalysisArtifact,
    AnalysisRun,
    ApiKey,
    CreditTransaction,
    DeployedProduct,
    LanguageCode,
    DeploymentStyle,
    User,
    utcnow,
)
from .persistence import (
    bootstrap_defaults,
    create_access_request,
    create_deployed_product,
    create_run_record,
    get_credit_balance,
    get_platform_setting,
    list_recent_runs,
    list_user_products,
    persist_run_event,
    record_credit_transaction,
    set_platform_setting,
    update_product_status,
)
from .security import (
    Identity,
    authenticate_api_key,
    create_api_key,
    create_session_token,
    parse_session_token,
    revoke_api_key,
)
from .site_renderer import (
    render_app_shell,
    render_landing,
)
from .tools import render_markdown_like_html

settings = load_settings()
PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
SESSION_COOKIE_NAME = "quien_session"
JOB_TTL_SECONDS = 60 * 60


class FullRunRequest(BaseModel):
    prompt: str = Field(min_length=8, max_length=4000)
    language: str | None = None
    research_style: str | None = None
    webhook_url: str | None = None


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] | None = None


class DevSessionRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    full_name: str | None = Field(default=None, max_length=160)
    language: str | None = None


class JobHandle:
    def __init__(
        self,
        *,
        job_id: str,
        prompt: str,
        user_id: str,
        research_style: str,
        language: LanguageCode,
        billable_credits: int,
        webhook_url: str | None = None,
        api_key_id: str | None = None,
    ) -> None:
        self.id = job_id
        self.prompt = prompt
        self.user_id = user_id
        self.research_style = research_style
        self.language = language
        self.billable_credits = billable_credits
        self.webhook_url = webhook_url
        self.api_key_id = api_key_id
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.snapshot: dict[str, Any] = _build_initial_snapshot(
            job_id, prompt, research_style, language,
        )
        self.task: asyncio.Task | None = None
        self.created_at = time.time()
        self.updated_at = time.time()


jobs: dict[str, JobHandle] = {}


@dataclass
class FixedWindowRateLimiter:
    window_seconds: int
    max_requests: int
    buckets: dict[str, deque[float]] = field(
        default_factory=lambda: defaultdict(deque))

    def allow(self, key: str) -> bool:
        now = time.time()
        bucket = self.buckets[key]
        while bucket and (now - bucket[0]) > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True


run_rate_limiter = FixedWindowRateLimiter(
    settings.run_rate_limit_window_seconds,
    settings.run_rate_limit_max_requests,
)
api_key_rate_limiter = FixedWindowRateLimiter(
    60, settings.api_key_rate_limit_per_minute)


def _language_from_value(
        value: str | None,
        fallback: str = "en") -> LanguageCode:
    normalized = (value or fallback).strip().lower()
    return LanguageCode.ES if normalized == "es" else LanguageCode.EN


def _research_style_from_value(value: str | None) -> DeploymentStyle:
    normalized = (value or DeploymentStyle.DEPLOY_PRODUCT.value).strip().lower()
    return DeploymentStyle(normalized)


def _resolve_language(
        request: Request, explicit: str | None = None) -> LanguageCode:
    if explicit:
        return _language_from_value(explicit)
    cookie_value = request.cookies.get("quien_lang")
    if cookie_value:
        return _language_from_value(cookie_value)
    if request.headers.get("Accept-Language", "").lower().startswith("es"):
        return LanguageCode.ES
    return _language_from_value(settings.default_language)


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "unknown") or "unknown"


def _validate_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=422,
                            detail="A valid email address is required.")
    return email


def _validate_email_bool(value: str) -> bool:
    """Return True if the email looks valid, False otherwise."""
    email = value.strip().lower()
    return "@" in email and "." in email.rsplit("@", 1)[-1]


def _set_language_cookie(response: Response, language: LanguageCode) -> None:
    response.set_cookie(
        key="quien_lang",
        value=language.value,
        max_age=60 * 60 * 24 * 365,
        secure=settings.public_base_url.startswith("https://"),
        httponly=False,
        samesite="lax",
        path="/",
    )


def _set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=settings.public_base_url.startswith("https://"),
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def _identity_from_request(request: Request) -> Identity | None:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        identity = parse_session_token(session_token)
        if identity is not None:
            return identity

    api_key = request.headers.get("X-API-Key")
    if api_key:
        identity = authenticate_api_key(api_key)
        if identity is None:
            raise HTTPException(status_code=401, detail="Invalid API key.")
        if not api_key_rate_limiter.allow(identity.api_key_id or api_key[:12]):
            raise HTTPException(
                status_code=429,
                detail="API key rate limit exceeded.")
        return identity

    return None


def _require_identity(request: Request) -> Identity:
    identity = _identity_from_request(request)
    if identity is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return identity


def _require_admin(request: Request) -> Identity:
    identity = _require_identity(request)
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    return identity


def _running_job_count() -> int:
    return sum(1 for job in jobs.values() if job.snapshot.get(
        "status") in {"queued", "running"})


def _cleanup_finished_jobs() -> None:
    now = time.time()
    is_done = {"completed", "failed"}
    expired = [
        job_id for job_id, job in jobs.items()
        if job.snapshot.get("status") in is_done
        if (now - job.updated_at) > JOB_TTL_SECONDS]
    for job_id in expired:
        jobs.pop(job_id, None)


def _run_snapshot(user_id: str, job_id: str) -> dict[str, Any] | None:
    with session_scope() as session:
        run = session.scalar(
            select(AnalysisRun).where(
                AnalysisRun.user_id == user_id,
                AnalysisRun.public_job_id == job_id,
            )
        )
        if run is None:
            return None
        run.events
        run.sections
        run.artifacts
        return _normalize_snapshot_artifacts(
            run.public_job_id, _snapshot_from_db(run))


def _account_payload(identity: Identity) -> dict[str, Any]:
    with session_scope() as session:
        user = session.scalar(
            select(User).where(User.id == identity.user_id)
        )
        if user is None:
            return {
                "authenticated": True,
                "email": identity.email,
                "full_name": identity.full_name,
                "is_admin": identity.is_admin,
                "credits": 0,
                "api_keys": [],
            }

        balance = get_credit_balance(session, user.id)

        keys = session.scalars(
            select(ApiKey).where(
                ApiKey.user_id == user.id,
                ApiKey.revoked_at.is_(None),
            )
        ).all()

        total_runs = session.scalar(
            select(func.count(AnalysisRun.id)).where(
                AnalysisRun.user_id == user.id,
                AnalysisRun.status != "failed",
            )
        ) or 0

        failed_runs = session.scalar(
            select(func.count(AnalysisRun.id)).where(
                AnalysisRun.user_id == user.id,
                AnalysisRun.status == "failed",
            )
        ) or 0

        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(days=1)
        daily_runs = session.scalar(
            select(func.count(AnalysisRun.id)).where(
                AnalysisRun.user_id == user.id,
                AnalysisRun.created_at >= twenty_four_hours_ago,
                AnalysisRun.status != "failed",
            )
        ) or 0

        payload = {
            "authenticated": True,
            "email": user.email,
            "full_name": user.full_name,
            "is_admin": user.is_admin,
            "credits": balance,
            "total_runs": total_runs,
            "failed_runs": failed_runs,
            "daily_runs": daily_runs,
            "api_keys": [
                {
                    "id": key.id,
                    "name": key.name,
                    "prefix": key.key_prefix,
                    "scopes": key.scopes.split(),
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                }
                for key in keys
            ],
        }
        payload["onboarding_completed"] = user.onboarding_completed
        payload["email_notifications"] = user.email_notifications
        return payload


def _snapshot_from_db(run: AnalysisRun) -> dict[str, Any]:
    ordered_sections = sorted(
        run.sections,
        key=lambda item: item.display_order)
    ordered_artifacts = sorted(run.artifacts, key=lambda item: item.created_at)
    ordered_events = sorted(run.events, key=lambda item: item.created_at)
    return {
        "job_id": run.public_job_id,
        "status": run.status,
        "prompt": run.prompt,
        "research_style": run.research_style,
        "language": run.language,
        "progress_pct": run.progress_pct,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": (
            int((run.completed_at - run.started_at).total_seconds())
            if run.started_at and run.completed_at else None
        ),
        "stages": [],
        "logs": [
            {
                "timestamp": event.created_at.strftime("%H:%M:%S"),
                "stage_id": event.stage_id or "system",
                "author": event.author,
                "message": event.message,
            }
            for event in ordered_events[-18:]
        ],
        "sections": [
            {
                "id": section.section_id,
                "title": section.title,
                "text": section.body_text,
                "html": render_markdown_like_html(section.body_text),
            }
            for section in ordered_sections
        ],
        "artifacts": [
            {
                "name": artifact.name,
                "path": artifact.storage_path,
                "url": _artifact_api_url(run.public_job_id, artifact.name),
                "kind": artifact.artifact_kind,
                "is_public": artifact.is_public,
                "requires_payment": artifact.requires_payment,
                "mime_type": artifact.mime_type,
            }
            for artifact in ordered_artifacts
        ],
        "final_text": "",
        "error": run.error_message,
    }


def _artifact_api_url(job_id: str, artifact_name: str) -> str:
    safe_name = quote(Path(artifact_name).name)
    return f"/api/v1/runs/{job_id}/artifacts/{safe_name}"


def _normalize_snapshot_artifacts(
        job_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(snapshot)
    artifacts = []
    for artifact in snapshot.get("artifacts", []):
        item = dict(artifact)
        artifact_name = str(item.get("name") or item.get("path") or "artifact")
        item["url"] = _artifact_api_url(job_id, artifact_name)
        artifacts.append(item)
    normalized["artifacts"] = artifacts
    return normalized


def _build_initial_snapshot(
    job_id: str,
    prompt: str,
    research_style: str,
    language: LanguageCode,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": "idle",
        "prompt": prompt,
        "research_style": research_style,
        "language": language.value,
        "progress_pct": 0,
        "stages": [],
        "logs": [],
        "sections": [],
        "artifacts": [],
        "final_text": "",
        "error": None,
    }


async def _publish_event(job: JobHandle, payload: dict[str, Any]) -> None:
    snapshot = _normalize_snapshot_artifacts(
        job.id, dict(payload.get("snapshot") or {}))
    snapshot["job_id"] = job.id
    payload = dict(payload)
    payload["snapshot"] = snapshot
    job.snapshot = snapshot
    job.updated_at = time.time()
    await job.queue.put(payload)


async def _run_job(job: JobHandle) -> None:
    async def callback(payload: dict[str, Any]) -> None:
        await _publish_event(job, payload)
        await asyncio.to_thread(
            persist_run_event,
            job.id,
            str(payload.get("type") or "update"),
            dict(payload.get("snapshot") or job.snapshot),
            payload.get("message"),
        )

    try:
        from .service import run_product_app
        result = await run_product_app(
            job.prompt,
            research_style=job.research_style,
            language=job.language,
            user_id=job.user_id,
            session_id=f"run_{job.id}",
            progress_callback=callback,
        )
        if result.status == "failed" and job.billable_credits > 0:
            with session_scope() as s:
                record_credit_transaction(
                    s,
                    job.user_id,
                    amount=job.billable_credits,
                    source_type="run_refund",
                    run_id=None,
                    api_key_id=job.api_key_id,
                    description=f"Automatic refund for failed run {job.id}.",
                    external_reference=f"refund:{job.id}",
                )
    except BaseException as exc:
        _log.exception("Run job %s failed", job.id)
        # Also print to stderr as fallback (logging may be misconfigured)
        print(f"[CRITICAL] Run job {job.id} failed: {exc!r}",
              file=sys.stderr, flush=True)
        # Notify SSE clients so they don't hang waiting for events
        error_msg = str(exc)[:260]
        try:
            await _publish_event(job, {
                "type": "error",
                "snapshot": {
                    **job.snapshot,
                    "status": "failed",
                    "error": error_msg,
                },
                "message": error_msg,
            })
        except Exception:  # nosec B110 — best-effort notification
            _log.debug("Could not publish error event for job %s", job.id)
        # Persist failure to DB so Reports view shows correct status
        try:
            await asyncio.to_thread(
                persist_run_event, job.id, "error",
                {**job.snapshot, "status": "failed", "error": error_msg},
                error_msg,
            )
        except Exception:  # nosec B110
            _log.debug("Could not persist error for job %s", job.id)
        result = None
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise

    # Email notification for completed runs
    if result is not None and result.status == "completed":
        try:
            with session_scope() as s:
                _notif_user = s.scalar(select(User).where(User.id == job.user_id))
                if _notif_user and _notif_user.email_notifications:
                    from .report_email import send_report_ready_email
                    from .tools import _get_report_title
                    _lang = job.language.value if hasattr(job.language, 'value') else str(job.language)
                    await send_report_ready_email(
                        email=_notif_user.email,
                        full_name=_notif_user.full_name,
                        report_title=_get_report_title(job.research_style, _lang),
                        job_id=job.id,
                        research_style=job.research_style,
                        language=_lang,
                        credits_consumed=job.billable_credits,
                        base_url=settings.public_base_url,
                        settings=settings,
                    )
        except Exception:
            _log.exception("Email notification for %s failed", job.id)

    # Webhook delivery
    if job.webhook_url and result is not None:
        try:
            from .webhooks import build_webhook_payload, deliver_webhook
            payload = build_webhook_payload(
                event="run.completed" if result.status == "completed" else "run.failed",
                job_id=job.id,
                research_style=job.research_style,
                status=result.status,
                credits_consumed=job.billable_credits if result.status == "completed" else 0,
                language=job.language.value if hasattr(job.language, 'value') else str(job.language),
                artifacts=[
                    {"name": a["name"], "mime_type": a.get("mime_type", ""), "url": a["url"]}
                    for a in result.artifacts
                ],
                error=result.error,
            )
            webhook_secret = settings.webhook_signing_secret if hasattr(settings, 'webhook_signing_secret') else "default-secret"
            await deliver_webhook(job.webhook_url, payload, webhook_secret)
        except Exception:
            _log.exception("Webhook delivery for %s failed", job.id)


def _bootstrap_with_settings():
    """Bootstrap defaults passing settings to the persistence layer."""
    try:
        with session_scope() as session:
            bootstrap_defaults(session, settings)
    except Exception:
        _log.warning(
            "Bootstrap defaults failed (schema migration may be pending)", exc_info=True,
        )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
    force=True,
)
_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(initialize_database)
    await asyncio.to_thread(_bootstrap_with_settings)
    try:
        yield
    finally:
        # Graceful shutdown: mark any in-flight jobs as failed in DB
        for job_id, job in list(jobs.items()):
            status = job.snapshot.get("status")
            if status in {"queued", "running"}:
                _log.warning("Shutdown: marking job %s as failed", job_id)
                try:
                    await _publish_event(job, {
                        "type": "error",
                        "snapshot": {
                            **job.snapshot,
                            "status": "failed",
                            "error": "Server restarted during processing.",
                        },
                        "message": "Server restarted during processing.",
                    })
                except Exception:  # nosec B110
                    pass
                try:
                    await asyncio.to_thread(
                        persist_run_event,
                        job_id,
                        "error",
                        {**job.snapshot, "status": "failed",
                         "error": "Server restarted during processing."},
                        "Server restarted during processing.",
                    )
                except Exception:  # nosec B110
                    _log.debug("Could not persist shutdown event for %s",
                               job_id)
                if job.task and not job.task.done():
                    job.task.cancel()
        await asyncio.to_thread(dispose_database)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(title="Product Name", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    product_name = settings.website_name or "Product"
    openapi_schema = get_openapi(
        title=f"{product_name} API",
        version="1.0.0",
        description=(
            f"{product_name} REST API. Authenticate with your API key "
            f"via the X-API-Key header. Visit the app to generate keys."
        ),
        routes=app.routes,
    )
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/docs/mcp", response_class=HTMLResponse, include_in_schema=False)
async def serve_mcp_guide() -> HTMLResponse:
    """Serve the MCP Guide markdown rendered as HTML."""
    guide_path = PACKAGE_DIR.parent / "docs" / "api_mcp_guide.md"
    if guide_path.exists():
        content = guide_path.read_text(encoding="utf-8")
        html_content = render_markdown_like_html(content)
        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>MCP Server Guide - Due Diligence Agent</title>
    <link rel="stylesheet" href="/static/app.css">
    <style>
        body {{ background-color: var(--ws-bg-dark, #0a0a0a); color: var(--ws-fg, #e0e0e0); margin: 0; padding: 2rem; font-family: sans-serif; line-height: 1.6; }}
        .mcp-container {{ max-width: 900px; margin: 0 auto; background: var(--ws-bg, #111); padding: 3rem; border-radius: 12px; border: 1px solid var(--ws-border, #333); box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
        h1, h2, h3, h4 {{ color: #ffffff; margin-top: 2rem; }}
        h1 {{ font-size: 2.5rem; margin-top: 0; border-bottom: 1px solid var(--ws-border, #333); padding-bottom: 1rem; }}
        pre {{ background: #000; padding: 1rem; border-radius: 6px; overflow-x: auto; border: 1px solid #333; }}
        code {{ font-family: monospace; color: #4dff4d; font-size: 0.9em; }}
        a {{ color: #4dff4d; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="mcp-container ws-panel">
        {html_content}
    </div>
</body>
</html>"""
        return HTMLResponse(page)
    return HTMLResponse("Guide not found.", status_code=404)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https: https://fastapi.tiangolo.com; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self';")
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    else:
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# ── Health ──────────────────────────────────────────────────────────


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    with session_scope() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    with session_scope() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok"}


# ── Public config ───────────────────────────────────────────────────


@app.get("/api/public-config")
async def public_config(request: Request) -> dict[str, Any]:
    language = _resolve_language(request)
    return {
        "language": language.value,
        "docs_url": f"{settings.public_base_url}/docs",
    }


@app.get("/api/v1/research/capabilities")
async def research_capabilities(request: Request) -> dict[str, Any]:
    from .service import get_registry

    language = _resolve_language(request)
    registry = get_registry()
    return {
        "styles": registry.capabilities(language.value),
        "service_type": "independent_research",
        "execution": ["on_demand", "api_driven"],
        "trading_execution": False,
    }


# ── Auth: Magic Link ────────────────────────────────────────────────


_otp_store: dict[str, tuple[str, float]] = {}  # email -> (code, expiry_timestamp)

# Rate limiter for OTP requests: 3 per email per hour, 10 per IP per hour
otp_email_rate_limiter = FixedWindowRateLimiter(3600, 3)
otp_ip_rate_limiter = FixedWindowRateLimiter(3600, 10)


def _generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    import secrets
    return f"{secrets.randbelow(1000000):06d}"


def _validate_user_for_login(s, email: str):
    """Check if user exists and is approved. Returns (user, error_response) tuple."""
    user = s.query(User).filter(func.lower(User.email) == email).first()
    if not user:
        from .models import AccessRequest as AccessRequestModel
        pending = s.query(AccessRequestModel).filter(
            func.lower(AccessRequestModel.email) == email,
        ).first()
        if pending:
            return None, JSONResponse({"error": "pending_review", "message": "Your access request is being reviewed. We'll notify you once approved."}, 403)
        return None, JSONResponse({"error": "not_registered", "message": "No account found. Please request access first."}, 403)
    if user.status == "suspended":
        return None, JSONResponse({"error": "suspended", "message": "Your account has been suspended. Contact support for assistance."}, 403)
    if user.status != "approved":
        return None, JSONResponse({"error": "pending_review", "message": "Your account is pending approval. We'll notify you once approved."}, 403)
    return user, None


@app.post("/api/v1/auth/magic-link")
async def request_magic_link(request: Request):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not _validate_email_bool(email):
        return JSONResponse({"error": "Invalid email"}, 400)

    # Rate limiting
    client_ip = (request.client.host if request.client else "unknown") or "unknown"
    if not otp_email_rate_limiter.allow(email):
        return JSONResponse({"error": "Too many requests. Please try again later."}, 429)
    if not otp_ip_rate_limiter.allow(client_ip):
        return JSONResponse({"error": "Too many requests. Please try again later."}, 429)

    # Check if user exists
    with session_scope() as s:
        user = s.query(User).filter(func.lower(User.email) == email).first()
        if user and user.status == "suspended":
            return JSONResponse({"error": "suspended", "message": "Your account has been suspended. Contact support for assistance."}, 403)

    # If user does not exist, validate corporate email
    if not user:
        from .email_validator import is_corporate_email
        is_corp, reason = is_corporate_email(
            email,
            admin_email=settings.admin_email,
            extra_blocked=settings.extra_blocked_email_domains or None,
        )
        if not is_corp:
            reason_messages = {
                "invalid_format": "Please provide a valid email address.",
                "invalid_domain": "Please provide a valid email address.",
                "public_domain": "Please use your corporate email address. Public email providers (Gmail, Yahoo, etc.) are not accepted.",
                "disposable_domain": "Disposable email addresses are not accepted. Please use your corporate email.",
            }
            return JSONResponse({
                "error": "corporate_email_required",
                "message": reason_messages.get(reason, "Please use a corporate email address."),
                "reason": reason,
            }, 400)

    settings_now = load_settings()
    from .email_sender import email_available
    if not email_available(settings_now):
        return JSONResponse({"error": "Email service is not configured. Contact support."}, 503)

    # Generate OTP and send via email
    code = _generate_otp()
    _otp_store[email] = (code, time.time() + 600)  # 10 min expiry
    try:
        from .otp_email import send_otp_email
        await send_otp_email(email, code, settings=settings_now)
    except Exception:
        _log.warning("OTP email send failed for %s", email, exc_info=True)
        del _otp_store[email]
        return JSONResponse({"error": "Email delivery failed. Please try again or contact support."}, 502)
    return JSONResponse({"message": "otp_sent", "method": "otp"})


@app.post("/api/v1/auth/verify-otp")
async def verify_otp(request: Request):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    code = body.get("code", "").strip()
    if not email or not code:
        return JSONResponse({"error": "Email and code are required."}, 400)
    stored = _otp_store.get(email)
    if not stored:
        return JSONResponse({"error": "No pending code. Please request a new one."}, 400)
    expected_code, expiry = stored
    if time.time() > expiry:
        _otp_store.pop(email, None)
        return JSONResponse({"error": "Code expired. Please request a new one."}, 400)
    if code != expected_code:
        return JSONResponse({"error": "Invalid code."}, 401)
    _otp_store.pop(email, None)

    with session_scope() as s:
        user = s.query(User).filter(func.lower(User.email) == email).first()

    if user and user.status == "approved":
        # Existing approved user — normal login
        session_identity = Identity(
            email=user.email,
            user_id=user.id,
            full_name=user.full_name or email.split("@")[0],
            is_admin=user.is_admin,
        )
        session_token = create_session_token(session_identity)
        account = _account_payload(session_identity)
        response = Response(
            content=json.dumps(account),
            media_type="application/json",
        )
        _set_session_cookie(response, session_token)
        return response
    elif user and user.status == "suspended":
        return JSONResponse({"error": "suspended", "message": "Your account has been suspended."}, 403)
    elif user:
        return JSONResponse({"error": "pending_review", "message": "Your account is pending approval."}, 403)
    else:
        # New user — issue signed registration token (stateless, multi-instance safe)
        from .magic_link import generate_registration_token
        reg_token = generate_registration_token(email, settings.magic_link_secret)
        return JSONResponse({"action": "complete_registration", "email": email, "registration_token": reg_token})


@app.post("/api/v1/auth/complete-registration")
async def complete_registration(request: Request):
    body = await request.json()
    reg_token = body.get("registration_token", "")
    full_name = body.get("full_name", "").strip()
    if not reg_token or not full_name:
        return JSONResponse({"error": "registration_token and full_name are required."}, 400)

    from .magic_link import verify_registration_token
    email = verify_registration_token(reg_token, settings.magic_link_secret)
    if not email:
        return JSONResponse({"error": "Invalid or expired registration token."}, 400)

    # Race condition check
    with session_scope() as s:
        existing = s.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            return JSONResponse({"error": "Account already exists. Please log in."}, 409)

    # Get initial credits from platform settings, fallback to config
    initial_credits = settings.default_initial_credits
    with session_scope() as s:
        from .models import PlatformSetting
        ps = s.query(PlatformSetting).filter(PlatformSetting.key == "default_initial_credits").first()
        if ps:
            try:
                initial_credits = int(ps.value)
            except (ValueError, TypeError):
                pass

    # Create user
    with session_scope() as s:
        from .persistence import auto_register_user
        user = auto_register_user(s, email, full_name, initial_credits=initial_credits)
        user_id = user.id
        user_email = user.email
        user_full_name = user.full_name
        user_is_admin = user.is_admin

    # Build identity and session OUTSIDE session_scope
    session_identity = Identity(
        email=user_email,
        user_id=user_id,
        full_name=user_full_name or full_name,
        is_admin=user_is_admin,
    )
    session_token = create_session_token(session_identity)
    account = _account_payload(session_identity)
    account["is_new_user"] = True
    account["action"] = "registered"
    response = Response(
        content=json.dumps(account),
        media_type="application/json",
    )
    _set_session_cookie(response, session_token)
    return response


@app.post("/api/v1/auth/verify")
async def verify_magic_link(request: Request):
    body = await request.json()
    token = body.get("token", "")
    settings_now = load_settings()
    from .magic_link import verify_magic_token
    email = verify_magic_token(token, settings_now.magic_link_secret)
    if not email:
        return JSONResponse({"error": "Invalid or expired token"}, 401)

    with session_scope() as s:
        user = s.query(User).filter(func.lower(User.email) == email).first()

    if user and user.status == "approved":
        with session_scope() as s:
            u = s.query(User).filter(func.lower(User.email) == email).first()
            u.last_login_at = utcnow()
        session_identity = Identity(
            email=user.email,
            user_id=user.id,
            full_name=user.full_name or email.split("@")[0],
            is_admin=user.is_admin,
        )
        session_token = create_session_token(session_identity)
        account = _account_payload(session_identity)
        response = Response(
            content=json.dumps(account),
            media_type="application/json",
        )
        _set_session_cookie(response, session_token)
        return response
    elif user and user.status == "suspended":
        return JSONResponse({"error": "suspended", "message": "Your account has been suspended."}, 403)
    elif user:
        return JSONResponse({"error": "Access not approved"}, 403)
    else:
        # New user — issue signed registration token (stateless, multi-instance safe)
        from .magic_link import generate_registration_token
        reg_token = generate_registration_token(email, settings.magic_link_secret)
        return JSONResponse({"action": "complete_registration", "email": email, "registration_token": reg_token})


# ── Auth: Dev session ───────────────────────────────────────────────


@app.post("/api/v1/auth/dev-session")
async def create_dev_session(payload: DevSessionRequest, request: Request):
    if not settings.enable_dev_auth:
        raise HTTPException(status_code=404,
                            detail="Development auth is disabled.")
    language = _resolve_language(request, payload.language)
    email = _validate_email(payload.email)
    with session_scope() as s:
        user = s.query(User).filter(func.lower(User.email) == email).first()
        if not user:
            # In dev mode, auto-create and approve the user
            user = User(
                email=email,
                full_name=payload.full_name,
                status="approved",
            )
            s.add(user)
            s.flush()
        elif user.status != "approved":
            user.status = "approved"
            s.flush()
        session_identity = Identity(
            email=user.email,
            user_id=user.id,
            full_name=user.full_name or payload.full_name,
            is_admin=user.is_admin,
        )
        session_token = create_session_token(session_identity)
    account = _account_payload(session_identity)
    response = Response(
        content=json.dumps(account),
        media_type="application/json",
    )
    _set_language_cookie(response, language)
    _set_session_cookie(response, session_token)
    return response


# ── Auth: Logout ────────────────────────────────────────────────────


@app.post("/api/v1/auth/logout")
async def logout() -> Response:
    response = Response(content=json.dumps(
        {"status": "ok"}), media_type="application/json")
    _clear_session_cookie(response)
    return response


# ── Account ─────────────────────────────────────────────────────────


@app.get("/api/v1/account")
async def account(request: Request) -> dict[str, Any]:
    identity = _require_identity(request)
    return _account_payload(identity)


@app.patch("/api/v1/account")
async def update_account(request: Request) -> dict[str, Any]:
    identity = _require_identity(request)
    body = await request.json()
    full_name = body.get("full_name")
    onboarding = body.get("onboarding_completed")
    email_notif = body.get("email_notifications")
    if full_name is not None or onboarding is True or email_notif is not None:
        with session_scope() as session:
            user = session.scalar(
                select(User).where(User.id == identity.user_id)
            )
            if user is None:
                raise HTTPException(status_code=404, detail="User not found.")
            if full_name is not None:
                user.full_name = full_name.strip() or None
            if onboarding is True:
                user.onboarding_completed = True
            if email_notif is not None:
                user.email_notifications = bool(email_notif)
    return _account_payload(identity)


# ── Billing ─────────────────────────────────────────────────────────


@app.post("/api/v1/billing/checkout")
async def billing_checkout(request: Request):
    identity = _require_identity(request)
    body = await request.json()
    quantity = int(body.get("credits") or body.get("quantity") or 0)
    if quantity < 1 or quantity > 10000:
        return JSONResponse({"error": "Quantity must be between 1 and 10,000."}, 400)

    from .stripe_billing import create_checkout_session, get_stripe_keys

    settings_now = load_settings()
    language = _resolve_language(request)

    with session_scope() as s:
        secret_key, pub_key, _ = get_stripe_keys(s)
        if not secret_key:
            mode = get_platform_setting(s, "stripe_mode", default="test")
            _log.warning(
                "Checkout failed: no secret_key. stripe_mode=%s, "
                "env_test=%s, env_live=%s",
                mode,
                bool(settings_now.stripe_secret_key_test),
                bool(settings_now.stripe_secret_key_live),
            )
            return JSONResponse({"error": "Payment system not configured."}, 503)
        user = s.scalar(select(User).where(User.id == identity.user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        mode = get_platform_setting(s, "stripe_mode", default="test")
        price_key = f"stripe_credit_price_id_{mode}"
        price_id = get_platform_setting(s, price_key, default="")
        if not price_id:
            fallback = getattr(settings_now, price_key, "")
            price_id = fallback
        if not price_id:
            return JSONResponse({"error": "Payment system not configured. Contact support."}, 503)
        base = settings_now.public_base_url
        result = create_checkout_session(
            user=user, quantity=quantity, price_id=price_id,
            success_url=f"{base}/{language.value}/app?billing=success&session_id={{CHECKOUT_SESSION_ID}}#billing",
            cancel_url=f"{base}/{language.value}/app?billing=canceled#billing",
            secret_key=secret_key, stripe_mode=mode, session=s,
        )
    return JSONResponse(result)


@app.get("/api/v1/billing/config")
async def billing_config(request: Request):
    _require_identity(request)
    with session_scope() as s:
        mode = get_platform_setting(s, "stripe_mode", default="test") or "test"
    return JSONResponse({"stripe_mode": mode})


@app.post("/api/v1/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    from .stripe_billing import get_stripe_keys, handle_checkout_completed, handle_charge_refunded
    with session_scope() as s:
        secret_key, _, webhook_secret = get_stripe_keys(s)
    if not webhook_secret:
        return JSONResponse({"error": "Webhook not configured."}, 500)
    import stripe
    stripe.api_key = secret_key
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        return JSONResponse({"error": "Invalid signature."}, 400)
    with session_scope() as s:
        obj = event["data"]["object"]
        data = obj.to_dict() if hasattr(obj, "to_dict") else obj
        if event["type"] == "checkout.session.completed":
            handle_checkout_completed(data, s)
        elif event["type"] == "charge.refunded":
            handle_charge_refunded(data, s)
    return JSONResponse({"status": "ok"})


@app.get("/api/v1/billing/invoices")
async def billing_invoices(request: Request):
    identity = _require_identity(request)
    with session_scope() as s:
        txns = (
            s.query(CreditTransaction)
            .filter(CreditTransaction.user_id == identity.user_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(50)
            .all()
        )
        invoices = [
            {
                "id": t.id,
                "credits": t.amount,
                "amount_cents": abs(t.amount) * 100,
                "status": "paid" if t.amount > 0 else "refund",
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "description": t.description,
                "source_type": t.source_type,
            }
            for t in txns
            if t.source_type in ("stripe_checkout", "stripe_refund")
        ]
    return JSONResponse(invoices)


@app.get("/api/v1/billing/portal")
async def billing_portal(request: Request):
    identity = _require_identity(request)
    from .stripe_billing import get_stripe_keys, create_portal_session
    settings_now = load_settings()
    language = _resolve_language(request)
    with session_scope() as s:
        user = s.scalar(select(User).where(User.id == identity.user_id))
        if not user:
            return JSONResponse({"error": "No billing account found."}, 404)
        secret_key, _, _ = get_stripe_keys(s)
        mode = get_platform_setting(s, "stripe_mode", default="test")
        cust_id = getattr(user, f"stripe_customer_id_{mode}", None) or user.stripe_customer_id
        if not secret_key or not cust_id:
            return JSONResponse({"error": "No billing account found."}, 404)
        return_url = f"{settings_now.public_base_url}/{language.value}/app#billing"
        portal_url = create_portal_session(
            cust_id, secret_key=secret_key, return_url=return_url,
        )
    return JSONResponse({"portal_url": portal_url})


# ── Access requests ─────────────────────────────────────────────────


@app.post("/api/v1/access/request", status_code=202)
async def request_access(request: Request):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not _validate_email_bool(email):
        return JSONResponse({"error": "Invalid email"}, 400)
    with session_scope() as s:
        req_id = create_access_request(
            s,
            email,
            body.get("full_name", ""),
            body.get("company"),
            body.get("message"),
        )
    return JSONResponse({"message": "Request submitted", "request_id": req_id}, 202)


@app.get("/api/v1/access/status")
async def access_status(request: Request, email: str):
    with session_scope() as s:
        req = (
            s.query(AccessRequest)
            .filter(func.lower(AccessRequest.email) == email.lower())
            .order_by(AccessRequest.created_at.desc())
            .first()
        )
        if not req:
            return JSONResponse({"status": "not_found"}, 404)
        return JSONResponse({"status": req.status})


# ── Usage ───────────────────────────────────────────────────────────


@app.get("/api/v1/account/usage")
async def account_usage(request: Request):
    identity = _identity_from_request(request)
    if not identity:
        return JSONResponse({"error": "Unauthorized"}, 401)
    with session_scope() as s:
        from .persistence import get_daily_usage, get_usage_by_api_key
        return JSONResponse({
            "daily": get_daily_usage(s, identity.user_id),
            "by_api_key": get_usage_by_api_key(s, identity.user_id),
        })


# ── Runs ────────────────────────────────────────────────────────────


@app.get("/api/v1/runs")
@app.get("/api/runs")
async def list_runs(
    request: Request,
    limit: int = 20,
    research_style: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    """List recent runs for the authenticated user."""
    identity = _require_identity(request)
    safe_limit = max(1, min(limit, 50))

    resolved_research_style = None
    if research_style:
        try:
            resolved_research_style = _research_style_from_value(
                research_style).value
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid research_style: {research_style}") from exc

    resolved_status = None
    if status:
        normalized_status = status.strip().lower()
        if normalized_status not in {
                "queued", "running", "completed", "failed"}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status: {status}")
        resolved_status = normalized_status

    with session_scope() as session:
        runs = list_recent_runs(
            session,
            user_id=identity.user_id,
            limit=safe_limit,
            status=resolved_status,
            research_style=resolved_research_style,
            query_text=q,
        )
    return {"runs": runs}


@app.delete("/api/v1/runs/{job_id}")
async def delete_run(job_id: str, request: Request) -> dict[str, str]:
    """Delete a failed or completed run."""
    identity = _require_identity(request)
    with session_scope() as session:
        run = session.scalar(
            select(AnalysisRun).where(
                AnalysisRun.public_job_id == job_id,
                AnalysisRun.user_id == identity.user_id,
            ))
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        if run.status in {"queued", "running"}:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete a run that is still in progress.")
        session.delete(run)
    return {"status": "deleted"}


@app.post("/api/v1/runs")
async def create_full_run(payload: FullRunRequest,
                          request: Request) -> dict[str, Any]:
    _cleanup_finished_jobs()
    language = _resolve_language(request, payload.language)
    identity = _require_identity(request)
    prompt = payload.prompt.strip()
    try:
        research_style = _research_style_from_value(payload.research_style)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid research_style: {payload.research_style}") from exc

    if not run_rate_limiter.allow(identity.user_id):
        raise HTTPException(
            status_code=429,
            detail="Too many run requests.")
    if _running_job_count() >= settings.max_concurrent_runs:
        raise HTTPException(status_code=429,
                            detail="The service is currently at capacity.")

    from .service import get_registry
    registry = get_registry()
    try:
        style = registry.get(research_style.value)
        credit_cost = style.credit_cost
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown research style: {research_style.value}")

    with session_scope() as s:
        balance = get_credit_balance(s, identity.user_id)
    if balance < credit_cost:
        raise HTTPException(
            status_code=402,
            detail="Not enough credits.")

    job_id = uuid.uuid4().hex[:12]
    job = JobHandle(
        job_id=job_id,
        prompt=prompt,
        user_id=identity.user_id,
        research_style=research_style.value,
        language=language,
        billable_credits=credit_cost,
        webhook_url=payload.webhook_url,
        api_key_id=identity.api_key_id,
    )
    job.snapshot["status"] = "queued"

    try:
        with session_scope() as s:
            create_run_record(
                s,
                job_id,
                prompt,
                user_id=identity.user_id,
                research_style=research_style.value,
                language=language.value,
                webhook_url=payload.webhook_url,
                api_key_id=identity.api_key_id,
            )
    except Exception as exc:
        _log.error("create_run_record failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error creating run: {exc}")

    try:
        with session_scope() as s:
            record_credit_transaction(
                s,
                identity.user_id,
                amount=-credit_cost,
                source_type="run_debit",
                api_key_id=identity.api_key_id,
                description=f"Consumed {credit_cost} credit(s) for run {job_id}.",
                external_reference=f"run:{job_id}",
            )
    except Exception as exc:
        _log.error("record_credit_transaction failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error recording credits: {exc}")

    jobs[job_id] = job
    await asyncio.to_thread(
        persist_run_event,
        job_id,
        "queued",
        dict(job.snapshot),
        "Full report queued.",
    )
    job.task = asyncio.create_task(_run_job(job))

    def _task_done_callback(task: asyncio.Task) -> None:
        if task.cancelled():
            _log.warning("Run task %s was cancelled", job_id)
        elif task.exception():
            _log.error("Run task %s raised: %s", job_id, task.exception())

    job.task.add_done_callback(_task_done_callback)
    return {"job_id": job_id, "snapshot": job.snapshot}


@app.get("/api/v1/runs/{job_id}")
async def get_run(job_id: str, request: Request) -> dict[str, Any]:
    identity = _identity_from_request(request)
    job = jobs.get(job_id)

    if identity is None:
        # Allow unauthenticated access ONLY to in-memory jobs (live preview)
        if job:
            return _normalize_snapshot_artifacts(job_id, job.snapshot)
        raise HTTPException(status_code=401, detail="Authentication required.")

    # Authenticated: check ownership
    if job and job.user_id == identity.user_id:
        return _normalize_snapshot_artifacts(job_id, job.snapshot)

    with session_scope() as session:
        run = session.scalar(
            select(AnalysisRun).where(
                AnalysisRun.public_job_id == job_id,
                AnalysisRun.user_id == identity.user_id,
            ))
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        run.events
        run.sections
        run.artifacts
        return _normalize_snapshot_artifacts(job_id, _snapshot_from_db(run))


@app.get("/api/v1/runs/{job_id}/stream")
async def stream_run(job_id: str, request: Request) -> EventSourceResponse:
    identity = _identity_from_request(request)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    if identity is not None and job.user_id != identity.user_id:
        raise HTTPException(status_code=404, detail="Run not found.")

    async def event_generator():
        yield {"data": json.dumps({"type": "snapshot", "snapshot": job.snapshot})}
        while True:
            try:
                payload = await asyncio.wait_for(job.queue.get(), timeout=25)
            except asyncio.TimeoutError:
                # Send heartbeat to keep Cloud Run proxy alive
                yield {"event": "ping", "data": ""}
                continue
            yield {"data": json.dumps(payload)}
            if payload.get("type") in {"finished", "error"}:
                break

    return EventSourceResponse(event_generator())


@app.get("/api/v1/runs/{job_id}/artifacts")
async def list_run_artifacts(job_id: str, request: Request) -> dict[str, Any]:
    snapshot = await get_run(job_id, request)
    return {"artifacts": snapshot.get("artifacts", [])}


@app.get("/api/v1/runs/{job_id}/artifacts/{artifact_name}")
async def get_run_artifact(job_id: str, artifact_name: str, request: Request):
    identity = _require_identity(request)
    safe_name = Path(artifact_name).name
    with session_scope() as session:
        query = (
            select(AnalysisArtifact)
            .join(AnalysisRun)
            .where(
                AnalysisRun.public_job_id == job_id,
                AnalysisRun.user_id == identity.user_id,
                AnalysisArtifact.name == safe_name,
            )
        )

        artifact = session.scalar(query)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found.")

        mime = artifact.mime_type or "application/octet-stream"

        # 1. Try local file (fast path, same container)
        local_path = settings.output_dir / Path(artifact.storage_path).name
        if local_path.exists():
            return FileResponse(local_path, media_type=mime)

        # 2. Try DB-stored content (survives container restarts)
        if artifact.content is not None:
            return Response(content=artifact.content, media_type=mime)

    # 3. Try GCS download
    downloaded = await asyncio.to_thread(download_artifact, safe_name)
    if downloaded is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    payload, mime_type = downloaded
    return Response(
        content=payload,
        media_type=mime_type or "application/octet-stream")


# ── Report viewer & export ───────────────────────────────────────────


@app.get("/api/v1/runs/{job_id}/report")
async def get_run_report(job_id: str, request: Request) -> Response:
    """Serve the full HTML report for a completed run."""
    snapshot = await get_run(job_id, request)
    sections = snapshot.get("sections", [])
    if not sections:
        raise HTTPException(status_code=404, detail="Report not yet available")

    from .tools import _get_report_title
    style_key = snapshot.get("research_style", "deploy_product")
    lang = snapshot.get("language", "en")
    report_title = _get_report_title(style_key, lang)

    visual_ids = {"graph_visualization", "evidence_board"}
    sections_html = ""
    for section in sections:
        if section.get("id") in visual_ids:
            continue
        title = section.get("title", "")
        html_body = section.get("html", section.get("text", ""))
        sections_html += (
            f"<section><h2>{title}</h2>{html_body}</section>"
        )

    esc_title = html_module.escape(report_title)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{esc_title}</title>
<style>
body {{ font-family: system-ui; max-width: 900px; margin: 0 auto; padding: 24px; background: #0a0a12; color: #e8eaf0; }}
h1 {{ color: #38bdf8; }} h2 {{ color: #818cf8; border-bottom: 1px solid rgba(129,140,248,0.2); padding-bottom: 8px; }}
section {{ margin-bottom: 32px; }} a {{ color: #38bdf8; }}
table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid rgba(56,189,248,0.15); padding: 8px; text-align: left; }}
</style></head>
<body><h1>{esc_title}</h1>{sections_html}</body></html>"""

    return Response(content=html, media_type="text/html")


@app.get("/api/v1/runs/{job_id}/export")
async def export_run(
    job_id: str, request: Request, format: str = "json",
) -> Response:
    """Export run results in multiple formats."""
    snapshot = await get_run(job_id, request)

    if format == "json":
        return JSONResponse(content=snapshot)
    elif format == "md":
        sections = snapshot.get("sections", [])
        md = "\n\n".join(
            f"## {s.get('title', '')}\n\n{s.get('text', '')}"
            for s in sections
        )
        return Response(
            content=md,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=report-{job_id}.md",
            },
        )
    elif format == "html":
        return RedirectResponse(url=f"/api/v1/runs/{job_id}/report")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


# ── API keys ────────────────────────────────────────────────────────


@app.post("/api/v1/api-keys")
async def create_api_key_route(
        payload: ApiKeyCreateRequest, request: Request) -> dict[str, Any]:
    identity = _require_identity(request)
    with session_scope() as s:
        if not identity.is_admin and get_credit_balance(s, identity.user_id) <= 0:
            raise HTTPException(
                status_code=403,
                detail="API access requires prepaid credits.")
    record, raw_key = await asyncio.to_thread(
        create_api_key,
        user_id=identity.user_id,
        name=payload.name,
        scopes=payload.scopes,
    )
    return {
        "id": record.id,
        "name": record.name,
        "prefix": record.key_prefix,
        "scopes": record.scopes.split(),
        "api_key": raw_key,
    }


@app.delete("/api/v1/api-keys/{api_key_id}")
async def delete_api_key_route(
        api_key_id: str, request: Request) -> dict[str, str]:
    identity = _require_identity(request)
    with session_scope() as session:
        record = session.scalar(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.user_id == identity.user_id,
            ))
        if record is None:
            raise HTTPException(status_code=404, detail="API key not found.")
    await asyncio.to_thread(revoke_api_key, api_key_id)
    return {"status": "revoked"}


# ── Admin routes ────────────────────────────────────────────────────


class AdminGrantRequest(BaseModel):
    user_id: str
    amount: int
    description: str | None = None


@app.get("/api/v1/admin/users")
async def admin_list_users(request: Request):
    _require_admin(request)
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(days=1)
    with session_scope() as s:
        users = s.query(User).order_by(User.created_at.desc()).all()
        result = []
        for u in users:
            total = s.scalar(
                select(func.count(AnalysisRun.id)).where(
                    AnalysisRun.user_id == u.id)) or 0
            daily = s.scalar(
                select(func.count(AnalysisRun.id)).where(
                    AnalysisRun.user_id == u.id,
                    AnalysisRun.created_at >= twenty_four_hours_ago)) or 0
            result.append({
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "is_admin": u.is_admin,
                "is_owner": u.email.lower() == settings.admin_email.lower(),
                "status": u.status,
                "credits": get_credit_balance(s, u.id),
                "total_runs": total,
                "daily_runs": daily,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            })
        return {"users": result}


@app.get("/api/v1/admin/access-requests")
async def admin_list_access_requests(request: Request, status: str = "pending"):
    _require_admin(request)
    with session_scope() as s:
        from .persistence import list_access_requests
        reqs = list_access_requests(s, status=status)
        return {"requests": [{
            "id": r.id,
            "email": r.email,
            "full_name": r.full_name,
            "company": r.company,
            "message": r.message,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        } for r in reqs]}


@app.post("/api/v1/admin/access-requests/{request_id}/approve")
async def admin_approve_access_request(request_id: str, request: Request):
    identity = _require_admin(request)
    body = await request.json()
    initial_credits = int(body.get("initial_credits", 0))
    with session_scope() as s:
        from .persistence import approve_access_request
        req = approve_access_request(s, request_id, identity.user_id, initial_credits)
        return JSONResponse({"status": "approved", "email": req.email})


@app.post("/api/v1/admin/access-requests/{request_id}/reject")
async def admin_reject_access_request(request_id: str, request: Request):
    identity = _require_admin(request)
    with session_scope() as s:
        from .persistence import reject_access_request
        req = reject_access_request(s, request_id, identity.user_id)
        return JSONResponse({"status": "rejected", "email": req.email})


@app.post("/api/v1/admin/grant-credits")
async def admin_grant_credits(
        payload: AdminGrantRequest, request: Request) -> dict[str, Any]:
    identity = _require_admin(request)
    with session_scope() as s:
        record_credit_transaction(
            s,
            payload.user_id,
            amount=payload.amount,
            source_type="admin_grant",
            description=payload.description or f"Granted by admin {identity.email}",
        )
    return {
        "status": "success",
        "granted": payload.amount,
        "user_id": payload.user_id,
    }


@app.post("/api/v1/admin/users/{user_id}/suspend")
async def admin_suspend_user(user_id: str, request: Request):
    _require_admin(request)
    with session_scope() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if user.email.lower() == settings.admin_email.lower():
            raise HTTPException(status_code=403, detail="Cannot suspend the owner account.")
        user.status = "suspended"
    return {"status": "suspended", "user_id": user_id}


@app.post("/api/v1/admin/users/{user_id}/reactivate")
async def admin_reactivate_user(user_id: str, request: Request):
    _require_admin(request)
    with session_scope() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        user.status = "approved"
    return {"status": "approved", "user_id": user_id}


@app.delete("/api/v1/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request):
    _require_admin(request)
    with session_scope() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if user.email.lower() == settings.admin_email.lower():
            raise HTTPException(status_code=403, detail="Cannot delete the owner account.")
        s.delete(user)
    return {"status": "deleted", "user_id": user_id}


# ── Admin settings & billing metrics ───────────────────────────────

_ADMIN_SETTINGS_DEFAULTS: dict[str, str] = {
    "default_initial_credits": "0",
    "stripe_mode": "test",
    "stripe_credit_price_id_test": "",
    "stripe_credit_price_id_live": "",
}

_ADMIN_SETTINGS_ALLOWED_KEYS = set(_ADMIN_SETTINGS_DEFAULTS.keys())


@app.get("/api/v1/admin/settings")
async def admin_get_settings(request: Request):
    _require_admin(request)
    with session_scope() as s:
        result: dict[str, str] = {}
        for key, default in _ADMIN_SETTINGS_DEFAULTS.items():
            result[key] = get_platform_setting(s, key, default=default) or default
    return JSONResponse(result)


@app.patch("/api/v1/admin/settings")
async def admin_patch_settings(request: Request):
    identity = _require_admin(request)
    body = await request.json()
    errors: list[str] = []
    for key in body:
        if key not in _ADMIN_SETTINGS_ALLOWED_KEYS:
            errors.append(f"Unknown setting: {key}")
    if "stripe_mode" in body and body["stripe_mode"] not in ("test", "live"):
        errors.append("stripe_mode must be 'test' or 'live'.")
    if "default_initial_credits" in body:
        try:
            int(body["default_initial_credits"])
        except (ValueError, TypeError):
            errors.append("default_initial_credits must be a number.")
    if errors:
        return JSONResponse({"errors": errors}, 400)
    with session_scope() as s:
        for key, value in body.items():
            if key in _ADMIN_SETTINGS_ALLOWED_KEYS:
                set_platform_setting(s, key, str(value), updated_by=identity.user_id)
    return JSONResponse({"status": "updated"})


@app.get("/api/v1/admin/billing/summary")
async def admin_billing_summary(request: Request):
    _require_admin(request)
    period = request.query_params.get("period", "month")
    now = datetime.now(timezone.utc)
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "all":
        cutoff = None
    else:  # month
        cutoff = now - timedelta(days=30)

    with session_scope() as s:
        base_q = select(CreditTransaction).where(
            CreditTransaction.source_type == "stripe_checkout",
        )
        # Total (all time)
        all_txns = s.scalars(base_q).all()
        total_revenue_usd = sum(t.amount * 1.0 for t in all_txns)
        total_purchases = len(all_txns)

        # Period
        if cutoff is not None:
            period_txns = [t for t in all_txns if t.created_at and t.created_at >= cutoff]
        else:
            period_txns = all_txns
        period_revenue_usd = sum(t.amount * 1.0 for t in period_txns)
        period_purchases = len(period_txns)

        # Active paying users (distinct user_ids in period)
        paying_user_ids = {t.user_id for t in period_txns}
        active_paying_users = len(paying_user_ids)

        # By user breakdown
        by_user: dict[str, dict[str, Any]] = {}
        for t in period_txns:
            entry = by_user.setdefault(t.user_id, {"user_id": t.user_id, "email": "", "total_usd": 0.0, "purchases": 0})
            entry["total_usd"] += t.amount * 1.0
            entry["purchases"] += 1
        # Resolve emails
        if by_user:
            users = s.scalars(select(User).where(User.id.in_(list(by_user.keys())))).all()
            email_map = {u.id: u.email for u in users}
            for uid, entry in by_user.items():
                entry["email"] = email_map.get(uid, "unknown")

    return JSONResponse({
        "total_revenue_usd": total_revenue_usd,
        "period_revenue_usd": period_revenue_usd,
        "total_purchases": total_purchases,
        "period_purchases": period_purchases,
        "active_paying_users": active_paying_users,
        "period": period,
        "by_user": list(by_user.values()),
    })


@app.get("/api/v1/admin/billing/transactions")
async def admin_billing_transactions(request: Request):
    _require_admin(request)
    limit_param = request.query_params.get("limit", "50")
    try:
        limit = min(int(limit_param), 500)
    except (ValueError, TypeError):
        limit = 50
    from_date = request.query_params.get("from")
    to_date = request.query_params.get("to")

    with session_scope() as s:
        q = select(CreditTransaction).where(
            CreditTransaction.source_type == "stripe_checkout",
        ).order_by(CreditTransaction.created_at.desc())

        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date)
                q = q.where(CreditTransaction.created_at >= from_dt)
            except ValueError:
                pass
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date)
                q = q.where(CreditTransaction.created_at <= to_dt)
            except ValueError:
                pass

        q = q.limit(limit)
        txns = s.scalars(q).all()

        # Resolve emails
        user_ids = list({t.user_id for t in txns})
        if user_ids:
            users = s.scalars(select(User).where(User.id.in_(user_ids))).all()
            email_map = {u.id: u.email for u in users}
        else:
            email_map = {}

        result = [
            {
                "id": t.id,
                "user_id": t.user_id,
                "email": email_map.get(t.user_id, "unknown"),
                "amount": t.amount,
                "description": t.description,
                "external_reference": t.external_reference,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ]
    return JSONResponse({"transactions": result})


# ── Products ───────────────────────────────────────────────────────


@app.get("/api/v1/products")
async def api_list_products(request: Request):
    """List all products deployed by the authenticated user."""
    identity = _require_identity(request)
    with session_scope() as session:
        products = list_user_products(session, identity.user_id)
        return [
            {
                "id": p.id,
                "product_name": p.product_name,
                "product_slug": p.product_slug,
                "repo_full_name": p.repo_full_name,
                "repo_url": p.repo_url,
                "cloud_run_url": p.cloud_run_url,
                "custom_domain": p.custom_domain,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in products
        ]


@app.get("/api/v1/products/{product_id}")
async def api_get_product(product_id: str, request: Request):
    """Get details of a specific deployed product."""
    identity = _require_identity(request)
    with session_scope() as session:
        product = session.get(DeployedProduct, product_id)
        if not product or product.user_id != identity.user_id:
            raise HTTPException(status_code=404, detail="Product not found")
        return {
            "id": product.id,
            "product_name": product.product_name,
            "product_slug": product.product_slug,
            "repo_full_name": product.repo_full_name,
            "repo_url": product.repo_url,
            "cloud_run_url": product.cloud_run_url,
            "custom_domain": product.custom_domain,
            "template_repo": product.template_repo,
            "agent_config_json": product.agent_config_json,
            "status": product.status,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        }


# ── SEO / static pages ─────────────────────────────────────────────


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt() -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/v1/",
            "Disallow: /artifacts/",
            f"Sitemap: {settings.public_base_url}/sitemap.xml",
        ]
    )


@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt() -> str:
    lines = [
        "# Product Name",
        "- Private AI research platform by Sitio Uno Inc.",
        "",
        "## Public pages",
        f"- {settings.public_base_url}/en",
        f"- {settings.public_base_url}/es",
    ]
    return "\n".join(lines)


@app.get("/sitemap.xml", response_class=PlainTextResponse)
async def sitemap_xml() -> str:
    pages = [
        "/",
        "/en",
        "/es",
    ]
    nodes = "".join(
        f"<url><loc>{settings.public_base_url}{path}</loc></url>"
        for path in pages
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{nodes}</urlset>'


def _marketing_user_summary(
        request: Request, language: LanguageCode) -> dict[str, Any] | None:
    identity = _identity_from_request(request)
    if identity is None:
        return None
    try:
        return _account_payload(identity)
    except HTTPException:
        return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    language = _resolve_language(request)
    html = render_landing(
        language.value,
        "/",
        _marketing_user_summary(
            request,
            language))
    response = HTMLResponse(html)
    _set_language_cookie(response, language)
    return response


@app.get("/{language}", response_class=HTMLResponse)
async def localized_landing(language: str, request: Request) -> HTMLResponse:
    if language not in {"en", "es"}:
        raise HTTPException(status_code=404, detail="Page not found.")
    lang = _language_from_value(language)
    html = render_landing(
        lang.value,
        f"/{language}",
        _marketing_user_summary(
            request,
            lang))
    response = HTMLResponse(html)
    _set_language_cookie(response, lang)
    return response


@app.get("/{language}/{page}", response_class=HTMLResponse)
async def catch_all_page(
        language: str,
        page: str,
        request: Request) -> Response:
    if language not in {"en", "es"} or page != "app":
        raise HTTPException(status_code=404, detail="Page not found.")
    lang = _language_from_value(language)
    identity = _identity_from_request(request)
    if identity is None:
        # Not authenticated — redirect to landing with auth modal trigger
        return RedirectResponse(
            url=f"/{language}?login=1", status_code=302)
    user_summary = _account_payload(identity)
    return HTMLResponse(
        render_app_shell(
            lang.value,
            f"/{language}/app",
            user_summary))


def main() -> None:
    uvicorn.run(
        "product_app.webapp:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
