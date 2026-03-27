"""Persistence models for runs, accounts, and access control."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid4())


# ── Enums ────────────────────────────────────────────────────────────

class LanguageCode(str, enum.Enum):
    EN = "en"
    ES = "es"


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DeploymentStyle(str, enum.Enum):
    DEPLOY_PRODUCT = "deploy_product"


# ── User ─────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(160))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    external_auth_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_customer_id_test: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_customer_id_live: Mapped[str | None] = mapped_column(String(255), unique=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


# ── Access Request ───────────────────────────────────────────────────

class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(160))
    company: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initial_credits: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── Platform Settings ────────────────────────────────────────────────

class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
    )


# ── API Key ──────────────────────────────────────────────────────────

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="api_keys")


# ── Credit Transaction ───────────────────────────────────────────────

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (UniqueConstraint("source_type", "external_reference"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("analysis_runs.id", ondelete="SET NULL"),
        index=True,
    )
    api_key_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="credit_transactions")
    run: Mapped["AnalysisRun | None"] = relationship(back_populates="credit_transactions")


# ── Analysis Run ─────────────────────────────────────────────────────

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        UniqueConstraint("public_job_id"),
        CheckConstraint("progress_pct >= 0 AND progress_pct <= 100"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    public_job_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    api_key_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    research_style: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credits_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    webhook_url: Mapped[str | None] = mapped_column(String(500))
    webhook_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    user: Mapped[User] = relationship(back_populates="runs")
    events: Mapped[list["AnalysisEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    sections: Mapped[list["AnalysisSection"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list["AnalysisArtifact"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    credit_transactions: Mapped[list[CreditTransaction]] = relationship(
        back_populates="run",
    )


# ── Analysis Event ───────────────────────────────────────────────────

class AnalysisEvent(Base):
    __tablename__ = "analysis_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    stage_id: Mapped[str | None] = mapped_column(String(80), index=True)
    author: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[AnalysisRun] = relationship(back_populates="events")


# ── Analysis Section ─────────────────────────────────────────────────

class AnalysisSection(Base):
    __tablename__ = "analysis_sections"
    __table_args__ = (UniqueConstraint("run_id", "section_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section_id: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[AnalysisRun] = relationship(back_populates="sections")


# ── Analysis Artifact ────────────────────────────────────────────────

class AnalysisArtifact(Base):
    __tablename__ = "analysis_artifacts"
    __table_args__ = (UniqueConstraint("run_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    public_url: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    mime_type: Mapped[str | None] = mapped_column(String(160))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_payment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[AnalysisRun] = relationship(back_populates="artifacts")


# ── Deployed Product ────────────────────────────────────────────────

class DeployedProduct(Base):
    __tablename__ = "deployed_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    repo_full_name: Mapped[str | None] = mapped_column(String(255))
    repo_url: Mapped[str | None] = mapped_column(String(512))
    cloud_run_url: Mapped[str | None] = mapped_column(String(512))
    custom_domain: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="created", nullable=False)
    template_repo: Mapped[str | None] = mapped_column(String(255))
    agent_config_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )
