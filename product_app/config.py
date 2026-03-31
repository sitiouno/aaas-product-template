"""Runtime configuration for Product Name."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _looks_like_placeholder(value: str | None) -> bool:
    if value is None:
        return True

    normalized = value.strip().lower()
    if not normalized:
        return True

    placeholder_markers = (
        "replace_with",
        "your_",
        "your-",
        "example",
        "changeme",
        "set_me",
        "<",
    )
    return normalized.startswith(placeholder_markers)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalized_language(value: str | None, *, default: str = "en") -> str:
    normalized = (value or default).strip().lower()
    return normalized if normalized in {"en", "es"} else default


def _is_local_base_url(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized.startswith("http://127.0.0.1") or normalized.startswith("http://localhost")


@dataclass(frozen=True)
class Settings:
    app_name: str
    user_id: str
    session_id: str
    public_base_url: str
    output_dir: Path
    gcs_bucket: str | None
    gcs_prefix: str
    database_url: str | None
    sqlite_db_path: Path
    cloud_sql_instance_connection_name: str | None
    cloud_sql_ip_type: str
    database_name: str
    database_user: str | None
    database_password: str | None
    database_pool_size: int
    database_max_overflow: int
    auto_create_database: bool
    default_user_email: str
    default_language: str
    run_rate_limit_window_seconds: int
    run_rate_limit_max_requests: int
    max_concurrent_runs: int
    preview_model: str
    coordinator_model: str
    search_model: str
    reasoning_model: str
    report_model: str
    infographic_enabled: bool
    enable_dev_auth: bool
    session_secret: str
    auth_google_audience: str | None
    # Magic Link
    magic_link_secret: str
    magic_link_expiry_minutes: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    magic_link_from_email: str
    # Factory email relay (used when local SMTP is not configured)
    factory_email_api_url: str
    factory_email_api_key: str
    # Webhook
    webhook_signing_secret: str
    webhook_retry_max: int
    # Admin
    admin_email: str
    website_name: str
    website_tagline_en: str
    website_tagline_es: str
    company_legal_name: str
    company_country: str
    support_email: str
    full_run_credit_cost: int
    api_key_default_scope: str
    api_key_rate_limit_per_minute: int
    # Open registration
    default_initial_credits: int
    extra_blocked_email_domains: frozenset[str]
    # Stripe (test/live pairs)
    stripe_secret_key_test: str
    stripe_secret_key_live: str
    stripe_publishable_key_test: str
    stripe_publishable_key_live: str
    stripe_webhook_secret_test: str
    stripe_webhook_secret_live: str
    stripe_credit_price_id: str
    stripe_credit_price_id_test: str
    stripe_credit_price_id_live: str
    # Product identity
    product_name: str = "My Product"
    product_description: str = ""
    product_description_es: str = ""
    product_domain: str = ""
    product_cta_en: str = "Get Started"
    product_cta_es: str = "Comenzar"
    unlock_protected: bool = False


def load_settings() -> Settings:
    package_dir = Path(__file__).resolve().parent
    default_output_dir = package_dir / "outputs"
    default_sqlite_db_path = package_dir / "app.db"
    output_dir = Path(
        os.getenv("PRODUCT_OUTPUT_DIR", str(default_output_dir))
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_db_path = Path(
        os.getenv("DATABASE_SQLITE_PATH", str(default_sqlite_db_path))
    ).resolve()
    sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)

    public_base_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    enable_dev_auth = _as_bool(os.getenv("PRODUCT_ENABLE_DEV_AUTH"), default=False)
    session_secret = _clean_optional(os.getenv("APP_SESSION_SECRET"))
    if session_secret is None:
        if enable_dev_auth and _is_local_base_url(public_base_url):
            session_secret = "dev-session-secret-change-me"  # nosec B105
        else:
            raise RuntimeError(
                "APP_SESSION_SECRET is required outside local development. "
                "Set APP_SESSION_SECRET or configure it from Secret Manager."
            )
    elif _looks_like_placeholder(session_secret) and not (
        enable_dev_auth and _is_local_base_url(public_base_url)
    ):
        raise RuntimeError(
            "APP_SESSION_SECRET looks like a placeholder. "
            "Set a strong secret before running shared or production environments."
        )

    return Settings(
        app_name=os.getenv("PRODUCT_APP_NAME", "product_app"),
        user_id=os.getenv("PRODUCT_USER_ID", "local_user"),
        session_id=os.getenv("PRODUCT_SESSION_ID", "local_session"),
        public_base_url=public_base_url,
        output_dir=output_dir,
        gcs_bucket=_clean_optional(os.getenv("PRODUCT_GCS_BUCKET")),
        gcs_prefix=os.getenv("PRODUCT_GCS_PREFIX", "artifacts").strip("/"),
        database_url=_clean_optional(os.getenv("DATABASE_URL")),
        sqlite_db_path=sqlite_db_path,
        cloud_sql_instance_connection_name=_clean_optional(
            os.getenv("CLOUD_SQL_INSTANCE_CONNECTION_NAME")
        ),
        cloud_sql_ip_type=os.getenv("CLOUD_SQL_IP_TYPE", "public").lower(),
        database_name=os.getenv("DATABASE_NAME", "product_app"),
        database_user=_clean_optional(os.getenv("DATABASE_USER")),
        database_password=_clean_optional(os.getenv("DATABASE_PASSWORD")),
        database_pool_size=max(int(os.getenv("DATABASE_POOL_SIZE", "5")), 1),
        database_max_overflow=max(int(os.getenv("DATABASE_MAX_OVERFLOW", "5")), 0),
        auto_create_database=_as_bool(os.getenv("DATABASE_AUTO_CREATE"), default=True),
        default_user_email=os.getenv(
            "PRODUCT_DEFAULT_USER_EMAIL",
            "owner@PRODUCT_DOMAIN",
        ),
        default_language=_normalized_language(os.getenv("PRODUCT_DEFAULT_LANGUAGE")),
        run_rate_limit_window_seconds=max(
            int(os.getenv("RUN_RATE_LIMIT_WINDOW_SECONDS", "300")),
            1,
        ),
        run_rate_limit_max_requests=max(
            int(os.getenv("RUN_RATE_LIMIT_MAX_REQUESTS", "6")),
            1,
        ),
        max_concurrent_runs=max(int(os.getenv("MAX_CONCURRENT_RUNS", "2")), 1),
        preview_model=os.getenv(
            "PRODUCT_PREVIEW_MODEL",
            "gemini-3-flash-preview",
        ),
        coordinator_model=os.getenv(
            "PRODUCT_COORDINATOR_MODEL",
            "gemini-3-flash-preview",
        ),
        search_model=os.getenv(
            "PRODUCT_SEARCH_MODEL",
            "gemini-3.1-pro-preview",
        ),
        reasoning_model=os.getenv(
            "PRODUCT_REASONING_MODEL",
            "gemini-3.1-pro-preview",
        ),
        report_model=os.getenv(
            "PRODUCT_REPORT_MODEL",
            "gemini-3-flash-preview",
        ),
        infographic_enabled=_as_bool(
            os.getenv("PRODUCT_ENABLE_INFOGRAPHIC"),
            default=True,
        ),
        enable_dev_auth=enable_dev_auth,
        session_secret=session_secret,
        auth_google_audience=_clean_optional(os.getenv("GOOGLE_OAUTH_AUDIENCE")),
        magic_link_secret=os.getenv("MAGIC_LINK_SECRET", ""),
        magic_link_expiry_minutes=max(
            int(os.getenv("MAGIC_LINK_EXPIRY_MINUTES", "15")), 1
        ),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        magic_link_from_email=os.getenv(
            "MAGIC_LINK_FROM_EMAIL", "noreply@PRODUCT_DOMAIN"
        ),
        factory_email_api_url=os.getenv("FACTORY_EMAIL_API_URL", ""),
        factory_email_api_key=os.getenv("FACTORY_EMAIL_API_KEY", ""),
        webhook_signing_secret=os.getenv("WEBHOOK_SIGNING_SECRET", ""),
        webhook_retry_max=max(int(os.getenv("WEBHOOK_RETRY_MAX", "3")), 1),
        admin_email=os.getenv(
            "ADMIN_EMAIL",
            os.getenv("PRODUCT_ADMIN_EMAIL", "jean@sitiouno.com"),
        ),
        website_name=os.getenv("WEBSITE_NAME", "Product Name"),
        website_tagline_en=os.getenv(
            "WEBSITE_TAGLINE_EN",
            "Deploy AI-powered MVPs in minutes.",
        ),
        website_tagline_es=os.getenv(
            "WEBSITE_TAGLINE_ES",
            "Despliega MVPs con IA en minutos.",
        ),
        company_legal_name=os.getenv("COMPANY_LEGAL_NAME", "Product Name"),
        company_country=os.getenv("COMPANY_COUNTRY", "US"),
        support_email=os.getenv("SUPPORT_EMAIL", "support@PRODUCT_DOMAIN"),
        full_run_credit_cost=max(int(os.getenv("FULL_RUN_CREDIT_COST", "1")), 1),
        api_key_default_scope=os.getenv(
            "API_KEY_DEFAULT_SCOPE",
            "runs:read runs:write account:read",
        ),
        api_key_rate_limit_per_minute=max(
            int(os.getenv("API_KEY_RATE_LIMIT_PER_MINUTE", "60")),
            1,
        ),
        default_initial_credits=max(int(os.getenv("DEFAULT_INITIAL_CREDITS", "10")), 0),
        extra_blocked_email_domains=frozenset(
            d.strip().lower() for d in os.getenv("EXTRA_BLOCKED_EMAIL_DOMAINS", "").split(",") if d.strip()
        ),
        stripe_secret_key_test=os.getenv("STRIPE_SECRET_KEY_TEST", "") or os.getenv("STRIPE_SECRET_KEY", ""),
        stripe_secret_key_live=os.getenv("STRIPE_SECRET_KEY_LIVE", ""),
        stripe_publishable_key_test=os.getenv("STRIPE_PUBLISHABLE_KEY_TEST", ""),
        stripe_publishable_key_live=os.getenv("STRIPE_PUBLISHABLE_KEY_LIVE", ""),
        stripe_webhook_secret_test=os.getenv("STRIPE_WEBHOOK_SECRET_TEST", ""),
        stripe_webhook_secret_live=os.getenv("STRIPE_WEBHOOK_SECRET_LIVE", ""),
        stripe_credit_price_id=os.getenv("STRIPE_CREDIT_PRICE_ID", ""),
        stripe_credit_price_id_test=os.getenv("STRIPE_CREDIT_PRICE_ID_TEST", ""),
        stripe_credit_price_id_live=os.getenv("STRIPE_CREDIT_PRICE_ID_LIVE", ""),
        product_name=os.getenv("PRODUCT_NAME", "My Product"),
        product_description=os.getenv("PRODUCT_DESCRIPTION", ""),
        product_description_es=os.getenv("PRODUCT_DESCRIPTION_ES", ""),
        product_cta_en=os.getenv("PRODUCT_CTA_EN", "Get Started"),
        product_cta_es=os.getenv("PRODUCT_CTA_ES", "Comenzar"),
        product_domain=os.getenv("PRODUCT_DOMAIN", ""),
        unlock_protected=_as_bool(os.getenv("UNLOCK_PROTECTED"), default=False),
    )


def validate_google_credentials() -> None:
    if not _looks_like_placeholder(os.getenv("GOOGLE_API_KEY")):
        return

    use_vertex = _as_bool(os.getenv("GOOGLE_GENAI_USE_VERTEXAI"), default=False)
    has_vertex_project = bool(os.getenv("GOOGLE_CLOUD_PROJECT"))
    has_vertex_location = bool(os.getenv("GOOGLE_CLOUD_LOCATION"))

    if use_vertex and has_vertex_project and has_vertex_location:
        return

    raise RuntimeError(
        "Google credentials are missing. Set GOOGLE_API_KEY, or configure "
        "GOOGLE_GENAI_USE_VERTEXAI=true with GOOGLE_CLOUD_PROJECT and "
        "GOOGLE_CLOUD_LOCATION."
    )
