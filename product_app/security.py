"""Security helpers for auth, API keys, and request identity."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import select

from .config import load_settings
from .database import session_scope
from .models import ApiKey, utcnow


@dataclass(frozen=True)
class Identity:
    email: str
    user_id: str
    full_name: str | None = None
    scopes: str = ""
    is_admin: bool = False
    exp: float = 0
    api_key_id: str | None = None


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_ip(value: str) -> str:
    return hash_value(f"ip::{value}")


def normalize_scopes(value: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_parts = value.replace(",", " ").split()
    else:
        raw_parts = [str(part).strip() for part in value]
    return tuple(sorted({part for part in raw_parts if part}))


def generate_api_key_material() -> tuple[str, str, str]:
    prefix = f"qk_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(24)
    raw_key = f"{prefix}.{secret}"
    return prefix, secret, raw_key


def create_api_key(
    *,
    user_id: str,
    name: str,
    label: str | None = None,
    scopes: str | Iterable[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    settings = load_settings()
    resolved_scopes = normalize_scopes(scopes or settings.api_key_default_scope)
    prefix, secret, raw_key = generate_api_key_material()
    with session_scope() as session:
        record = ApiKey(
            user_id=user_id,
            name=name,
            label=label,
            key_prefix=prefix,
            secret_hash=hash_value(secret),
            scopes=" ".join(resolved_scopes),
            expires_at=expires_at,
        )
        session.add(record)
        session.flush()
        return record, raw_key


def authenticate_api_key(raw_key: str) -> Identity | None:
    try:
        prefix, secret = raw_key.split(".", 1)
    except ValueError:
        return None

    with session_scope() as session:
        record = session.scalar(select(ApiKey).where(ApiKey.key_prefix == prefix))
        if record is None:
            return None
        if record.revoked_at is not None:
            return None
        if record.expires_at is not None and record.expires_at <= utcnow():
            return None
        if record.secret_hash != hash_value(secret):
            return None

        record.last_used_at = utcnow()

        from .models import User
        user = session.scalar(select(User).where(User.id == record.user_id))
        return Identity(
            email=user.email if user else "",
            user_id=record.user_id,
            full_name=user.full_name if user else None,
            scopes=" ".join(normalize_scopes(record.scopes)),
            is_admin=user.is_admin if user else False,
            api_key_id=record.id,
        )


def revoke_api_key(api_key_id: str) -> None:
    with session_scope() as session:
        record = session.scalar(select(ApiKey).where(ApiKey.id == api_key_id))
        if record is not None and record.revoked_at is None:
            record.revoked_at = utcnow()


def create_session_token(identity: Identity, *, max_age_seconds: int = 60 * 60 * 24 * 7) -> str:
    settings = load_settings()
    exp = int((utcnow() + timedelta(seconds=max_age_seconds)).timestamp())
    payload = {
        "email": identity.email,
        "user_id": identity.user_id,
        "full_name": identity.full_name,
        "scopes": identity.scopes,
        "is_admin": identity.is_admin,
        "exp": exp,
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii")
    signature = hmac.new(
        settings.session_secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def parse_session_token(token: str) -> Identity | None:
    settings = load_settings()
    try:
        encoded, signature = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        settings.session_secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp") or 0) <= int(utcnow().timestamp()):
        return None

    return Identity(
        email=payload.get("email") or "",
        user_id=payload.get("user_id") or "",
        full_name=payload.get("full_name"),
        scopes=payload.get("scopes") or "",
        is_admin=bool(payload.get("is_admin")),
        exp=float(payload.get("exp") or 0),
    )


def verify_bearer_token(token: str) -> Identity:
    settings = load_settings()
    verification_error: Exception | None = None

    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token

        request = GoogleRequest()
        if settings.auth_firebase_project_id:
            payload = id_token.verify_firebase_token(token, request)
        else:
            audience = settings.auth_google_audience or settings.auth_google_client_id
            if not audience:
                raise RuntimeError(
                    "Missing GOOGLE_OAUTH_AUDIENCE or GOOGLE_OAUTH_CLIENT_ID for bearer auth."
                )
            payload = id_token.verify_oauth2_token(token, request, audience=audience)

        email = payload.get("email")
        if not email:
            raise RuntimeError("Verified token did not include an email address.")

        return Identity(
            email=email,
            user_id=str(payload.get("sub") or email),
            full_name=payload.get("name"),
            scopes="account:read runs:read runs:write",
        )
    except Exception as exc:  # pragma: no cover - network/crypto path
        verification_error = exc

    if settings.enable_dev_auth and token.startswith("dev:"):
        email = token[4:].strip()
        if not email:
            raise RuntimeError("Development bearer token must be formatted as dev:user@example.com")
        return Identity(
            email=email,
            user_id=email,
            full_name=email.split("@", 1)[0].replace(".", " ").title(),
            scopes="account:read runs:read runs:write",
        )

    raise RuntimeError(f"Unable to verify bearer token: {verification_error}")
