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
    """Send branded magic link email via SMTP."""
    from .email_templates import render_magic_link_email
    import aiosmtplib
    from email.message import EmailMessage

    subject = "Welcome to Product Name" if is_new_user else "Sign in to Product Name"
    html_body = render_magic_link_email(email, magic_url, is_new_user)

    msg = EmailMessage()
    msg["From"] = settings.magic_link_from_email
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content("Open this link to sign in: " + magic_url)
    msg.add_alternative(html_body, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=True,
    )
