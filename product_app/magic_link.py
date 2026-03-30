"""Magic Link token generation, verification, and email delivery."""
import base64
import hashlib
import hmac
import json
import time
import logging

logger = logging.getLogger(__name__)


def generate_magic_token(email: str, secret: str, expiry_minutes: int = 15) -> str:
    """Generate HMAC-signed magic link token."""
    payload = {
        "email": email.lower().strip(),
        "exp": int(time.time()) + (expiry_minutes * 60),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_magic_token(token: str, secret: str) -> str | None:
    """Verify magic link token. Returns email or None."""
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("email")
    except Exception:
        logger.debug("Magic token verification failed", exc_info=True)
        return None


def generate_registration_token(email: str, secret: str, expiry_minutes: int = 15) -> str:
    """Generate HMAC-signed registration token (stateless, multi-instance safe)."""
    payload = {
        "email": email.lower().strip(),
        "purpose": "registration",
        "exp": int(time.time()) + (expiry_minutes * 60),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_registration_token(token: str, secret: str) -> str | None:
    """Verify registration token. Returns email or None."""
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("purpose") != "registration":
            return None
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("email")
    except Exception:
        logger.debug("Registration token verification failed", exc_info=True)
        return None


async def send_magic_link_email(email: str, magic_url: str, is_new_user: bool, settings):
    """Send branded magic link email."""
    from .email_templates import render_magic_link_email
    from .email_sender import send_email

    product_name = getattr(settings, "website_name", "") or "Product"
    subject = f"Welcome to {product_name}" if is_new_user else f"Sign in to {product_name}"
    html_body = render_magic_link_email(email, magic_url, is_new_user)

    await send_email(
        to=email,
        subject=subject,
        html_body=html_body,
        text_body="Open this link to sign in: " + magic_url,
        from_name=product_name,
        settings=settings,
    )
