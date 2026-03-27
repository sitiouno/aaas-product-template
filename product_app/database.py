"""Database engine and session management."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings, load_settings


class Base(DeclarativeBase):
    """Base declarative model."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_connector = None


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _build_engine(settings: Settings) -> Engine:
    if settings.database_url:
        connect_args: dict[str, object] = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        return create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            connect_args=connect_args,
        )

    if settings.cloud_sql_instance_connection_name:
        from google.cloud.sql.connector import Connector, IPTypes

        ip_type_lookup = {
            "private": IPTypes.PRIVATE,
            "psc": IPTypes.PSC,
            "public": IPTypes.PUBLIC,
        }
        ip_type = ip_type_lookup.get(
            settings.cloud_sql_ip_type,
            IPTypes.PUBLIC,
        )

        if not settings.database_user:
            raise RuntimeError(
                "DATABASE_USER is required when using CLOUD_SQL_INSTANCE_CONNECTION_NAME."
            )

        connector = Connector(refresh_strategy="lazy")

        def getconn():
            return connector.connect(
                settings.cloud_sql_instance_connection_name,
                "pg8000",
                user=settings.database_user,
                password=settings.database_password or None,
                db=settings.database_name,
                ip_type=ip_type,
                enable_iam_auth=not bool(settings.database_password),
            )

        global _connector
        _connector = connector
        return create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )

    return create_engine(
        _sqlite_url(settings.sqlite_db_path),
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        settings = load_settings()
        _engine = _build_engine(settings)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_database() -> None:
    from . import models  # noqa: F401

    settings = load_settings()
    if settings.auto_create_database:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        _apply_lightweight_schema_updates(engine)


def dispose_database() -> None:
    global _engine, _session_factory, _connector
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _session_factory = None
    if _connector is not None:
        _connector.close()
        _connector = None


def _apply_lightweight_schema_updates(engine: Engine) -> None:
    """Apply additive schema updates for existing databases without destructive migrations."""

    inspector = inspect(engine)
    table_columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in inspector.get_table_names()
    }
    statements: list[str] = []

    migrations = {
        "organizations": [
            ("default_language", "ALTER TABLE organizations ADD COLUMN default_language VARCHAR(2) NOT NULL DEFAULT 'en'"),
            ("stripe_customer_id", "ALTER TABLE organizations ADD COLUMN stripe_customer_id VARCHAR(255)"),
        ],
        "users": [
            ("preferred_language", "ALTER TABLE users ADD COLUMN preferred_language VARCHAR(2) NOT NULL DEFAULT 'en'"),
            ("last_login_at", "ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP"),
            ("is_admin", "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"),
            ("status", "ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'"),
            ("language", "ALTER TABLE users ADD COLUMN language VARCHAR(10) NOT NULL DEFAULT 'en'"),
            ("stripe_customer_id", "ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255)"),
            ("stripe_customer_id_test", "ALTER TABLE users ADD COLUMN stripe_customer_id_test VARCHAR(255)"),
            ("stripe_customer_id_live", "ALTER TABLE users ADD COLUMN stripe_customer_id_live VARCHAR(255)"),
            ("onboarding_completed", "ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE"),
            ("email_notifications", "ALTER TABLE users ADD COLUMN email_notifications BOOLEAN NOT NULL DEFAULT TRUE"),
        ],
        "subscription_plans": [
            ("seats_included", "ALTER TABLE subscription_plans ADD COLUMN seats_included INTEGER NOT NULL DEFAULT 1"),
            ("api_access", "ALTER TABLE subscription_plans ADD COLUMN api_access BOOLEAN NOT NULL DEFAULT FALSE"),
            ("stripe_price_id", "ALTER TABLE subscription_plans ADD COLUMN stripe_price_id VARCHAR(255)"),
        ],
        "analysis_runs": [
            ("mode", "ALTER TABLE analysis_runs ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'full'"),
            (
                "research_mode",
                "ALTER TABLE analysis_runs ADD COLUMN research_mode VARCHAR(40) NOT NULL DEFAULT 'deploy_product'",
            ),
            (
                "research_intent",
                "ALTER TABLE analysis_runs ADD COLUMN research_intent VARCHAR(80) NOT NULL DEFAULT 'general'",
            ),
            (
                "workflow_version",
                "ALTER TABLE analysis_runs ADD COLUMN workflow_version VARCHAR(40) NOT NULL DEFAULT 'v1'",
            ),
            ("language", "ALTER TABLE analysis_runs ADD COLUMN language VARCHAR(2) NOT NULL DEFAULT 'en'"),
            ("preview_redacted", "ALTER TABLE analysis_runs ADD COLUMN preview_redacted BOOLEAN NOT NULL DEFAULT FALSE"),
            ("billable_credits", "ALTER TABLE analysis_runs ADD COLUMN billable_credits INTEGER NOT NULL DEFAULT 0"),
            ("estimated_cost_cents", "ALTER TABLE analysis_runs ADD COLUMN estimated_cost_cents INTEGER NOT NULL DEFAULT 0"),
            ("idempotency_key", "ALTER TABLE analysis_runs ADD COLUMN idempotency_key VARCHAR(255)"),
            ("public_job_id", "ALTER TABLE analysis_runs ADD COLUMN public_job_id VARCHAR(32)"),
            ("prompt", "ALTER TABLE analysis_runs ADD COLUMN prompt TEXT NOT NULL DEFAULT ''"),
            ("progress_pct", "ALTER TABLE analysis_runs ADD COLUMN progress_pct INTEGER NOT NULL DEFAULT 0"),
            ("research_style", "ALTER TABLE analysis_runs ADD COLUMN research_style VARCHAR(50) NOT NULL DEFAULT 'deploy_product'"),
            ("credits_consumed", "ALTER TABLE analysis_runs ADD COLUMN credits_consumed INTEGER NOT NULL DEFAULT 0"),
            ("estimated_cost_usd", "ALTER TABLE analysis_runs ADD COLUMN estimated_cost_usd FLOAT"),
            ("webhook_url", "ALTER TABLE analysis_runs ADD COLUMN webhook_url VARCHAR(500)"),
            ("webhook_sent_at", "ALTER TABLE analysis_runs ADD COLUMN webhook_sent_at TIMESTAMP"),
            ("error_message", "ALTER TABLE analysis_runs ADD COLUMN error_message TEXT"),
            ("started_at", "ALTER TABLE analysis_runs ADD COLUMN started_at TIMESTAMP"),
            ("completed_at", "ALTER TABLE analysis_runs ADD COLUMN completed_at TIMESTAMP"),
            ("user_id", "ALTER TABLE analysis_runs ADD COLUMN user_id VARCHAR(36)"),
            ("api_key_id", "ALTER TABLE analysis_runs ADD COLUMN api_key_id VARCHAR(36)"),
        ],
        "access_requests": [
            ("full_name", "ALTER TABLE access_requests ADD COLUMN full_name VARCHAR(160)"),
            ("company", "ALTER TABLE access_requests ADD COLUMN company VARCHAR(255)"),
            ("message", "ALTER TABLE access_requests ADD COLUMN message TEXT"),
            ("status", "ALTER TABLE access_requests ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'"),
            ("reviewed_by", "ALTER TABLE access_requests ADD COLUMN reviewed_by VARCHAR(36)"),
            ("reviewed_at", "ALTER TABLE access_requests ADD COLUMN reviewed_at TIMESTAMP"),
            ("initial_credits", "ALTER TABLE access_requests ADD COLUMN initial_credits INTEGER"),
        ],
        "api_keys": [
            ("user_id", "ALTER TABLE api_keys ADD COLUMN user_id VARCHAR(36)"),
            ("name", "ALTER TABLE api_keys ADD COLUMN name VARCHAR(120) NOT NULL DEFAULT 'Default'"),
            ("key_prefix", "ALTER TABLE api_keys ADD COLUMN key_prefix VARCHAR(32)"),
            ("secret_hash", "ALTER TABLE api_keys ADD COLUMN secret_hash VARCHAR(128)"),
            ("scopes", "ALTER TABLE api_keys ADD COLUMN scopes VARCHAR(255) NOT NULL DEFAULT 'runs:write'"),
            ("label", "ALTER TABLE api_keys ADD COLUMN label VARCHAR(100)"),
            ("rate_limit_rpm", "ALTER TABLE api_keys ADD COLUMN rate_limit_rpm INTEGER NOT NULL DEFAULT 60"),
            ("last_used_at", "ALTER TABLE api_keys ADD COLUMN last_used_at TIMESTAMP"),
            ("expires_at", "ALTER TABLE api_keys ADD COLUMN expires_at TIMESTAMP"),
            ("revoked_at", "ALTER TABLE api_keys ADD COLUMN revoked_at TIMESTAMP"),
        ],
        "credit_transactions": [
            ("user_id", "ALTER TABLE credit_transactions ADD COLUMN user_id VARCHAR(36)"),
            ("run_id", "ALTER TABLE credit_transactions ADD COLUMN run_id VARCHAR(36)"),
            ("api_key_id", "ALTER TABLE credit_transactions ADD COLUMN api_key_id VARCHAR(36)"),
            ("source_type", "ALTER TABLE credit_transactions ADD COLUMN source_type VARCHAR(80) NOT NULL DEFAULT 'manual'"),
            ("amount", "ALTER TABLE credit_transactions ADD COLUMN amount INTEGER NOT NULL DEFAULT 0"),
            ("balance_after", "ALTER TABLE credit_transactions ADD COLUMN balance_after INTEGER NOT NULL DEFAULT 0"),
            ("estimated_cost_usd", "ALTER TABLE credit_transactions ADD COLUMN estimated_cost_usd FLOAT"),
            ("description", "ALTER TABLE credit_transactions ADD COLUMN description TEXT"),
            ("external_reference", "ALTER TABLE credit_transactions ADD COLUMN external_reference VARCHAR(255)"),
        ],
        "analysis_artifacts": [
            ("is_public", "ALTER TABLE analysis_artifacts ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT FALSE"),
            ("requires_payment", "ALTER TABLE analysis_artifacts ADD COLUMN requires_payment BOOLEAN NOT NULL DEFAULT TRUE"),
            ("size_bytes", "ALTER TABLE analysis_artifacts ADD COLUMN size_bytes INTEGER"),
            ("content", "ALTER TABLE analysis_artifacts ADD COLUMN content BYTEA"),
        ],
        "analysis_sections": [
            ("body_html", "ALTER TABLE analysis_sections ADD COLUMN body_html TEXT"),
            ("display_order", "ALTER TABLE analysis_sections ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0"),
        ],
        "analysis_events": [
            ("stage_id", "ALTER TABLE analysis_events ADD COLUMN stage_id VARCHAR(80)"),
            ("author", "ALTER TABLE analysis_events ADD COLUMN author VARCHAR(120) NOT NULL DEFAULT 'system'"),
        ],
    }

    for table_name, column_migrations in migrations.items():
        if table_name not in table_columns:
            continue
        existing_columns = table_columns[table_name]
        for column_name, sql in column_migrations:
            if column_name not in existing_columns:
                statements.append(sql)

    # Column alterations (always safe to re-run)
    column_alterations = [
        ("credit_transactions", "organization_id",
         "ALTER TABLE credit_transactions ALTER COLUMN organization_id DROP NOT NULL"),
        ("analysis_runs", "organization_id",
         "ALTER TABLE analysis_runs ALTER COLUMN organization_id DROP NOT NULL"),
        ("api_keys", "organization_id",
         "ALTER TABLE api_keys ALTER COLUMN organization_id DROP NOT NULL"),
        ("access_requests", "organization_id",
         "ALTER TABLE access_requests ALTER COLUMN organization_id DROP NOT NULL"),
        # Legacy column not in ORM model — needs a default so INSERTs don't fail
        ("users", "is_platform_admin",
         "ALTER TABLE users ALTER COLUMN is_platform_admin SET DEFAULT FALSE"),
    ]
    for table_name, col_name, sql in column_alterations:
        if table_name in table_columns and col_name in table_columns[table_name]:
            statements.append(sql)

    # Handle legacy column renames: drop old columns that have been superseded.
    # The original schema used 'progress_percent'; the current model uses 'progress_pct'.
    if "analysis_runs" in table_columns:
        ar_cols = table_columns["analysis_runs"]
        if "progress_percent" in ar_cols and "progress_pct" in ar_cols:
            statements.append(
                "ALTER TABLE analysis_runs DROP COLUMN progress_percent"
            )
        elif "progress_percent" in ar_cols and "progress_pct" not in ar_cols:
            statements.append(
                "ALTER TABLE analysis_runs RENAME COLUMN progress_percent TO progress_pct"
            )

    # Make any remaining legacy NOT-NULL columns safe by adding defaults.
    # These are columns from the original schema that the current ORM does not populate.
    _legacy_nullable = [
        ("analysis_runs", "company_name"),
        ("analysis_runs", "subscription_plan_id"),
    ]
    for table_name, col_name in _legacy_nullable:
        if table_name in table_columns and col_name in table_columns[table_name]:
            statements.append(
                f"ALTER TABLE {table_name} ALTER COLUMN {col_name} DROP NOT NULL"
            )

    # -- Table creation for new models --
    existing_tables = set(inspector.get_table_names())
    if "platform_settings" not in existing_tables:
        statements.append(
            "CREATE TABLE IF NOT EXISTS platform_settings ("
            "key VARCHAR(100) PRIMARY KEY, "
            "value TEXT NOT NULL, "
            "updated_at TIMESTAMP, "
            "updated_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL)"
        )

    if not statements:
        return

    import logging
    logger = logging.getLogger(__name__)
    with engine.begin() as connection:
        for statement in statements:
            savepoint = connection.begin_nested()
            try:
                connection.execute(text(statement))
                savepoint.commit()
                logger.info("Migration OK: %s", statement)
            except Exception as exc:
                savepoint.rollback()
                logger.warning("Migration skipped (may already be applied): %s — %s", statement, exc)

    # Unique index on stripe_customer_id (separate for SQLite compatibility)
    try:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
    except Exception:
        existing_indexes = set()
    if "ix_users_stripe_customer_id" not in existing_indexes:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON users(stripe_customer_id)"
            ))
