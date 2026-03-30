"""Unified email sender: Factory relay API first, local SMTP fallback.

Products deployed by MVP Factory get an email API key that authenticates
against the Factory's /api/v1/email/send endpoint.  If that is configured
the email is relayed through Factory's SMTP (100 free/month, then credits).

If the product owner configures their own SMTP credentials, those are used
directly instead.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def email_available(settings) -> bool:
    """Return True if at least one email transport is configured."""
    if settings.smtp_host and settings.smtp_user:
        return True
    if settings.factory_email_api_url and settings.factory_email_api_key:
        return True
    return False


async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
    settings,
) -> None:
    """Send an email via the best available transport.

    Priority:
      1. Local SMTP (product owner's own credentials)
      2. Factory email relay API
    """
    # 1. Local SMTP takes priority (product owner configured their own)
    if settings.smtp_host and settings.smtp_user:
        await _send_via_smtp(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_name=from_name,
            from_email=from_email,
            settings=settings,
        )
        return

    # 2. Factory email relay API
    if settings.factory_email_api_url and settings.factory_email_api_key:
        await _send_via_factory_api(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_name=from_name,
            from_email=from_email,
            settings=settings,
        )
        return

    raise RuntimeError("No email transport configured")


async def _send_via_smtp(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None,
    from_name: str | None,
    from_email: str | None,
    settings,
) -> None:
    import aiosmtplib
    from email.message import EmailMessage

    addr = from_email or settings.magic_link_from_email or settings.smtp_user
    display = from_name or ""

    msg = EmailMessage()
    msg["From"] = f"{display} <{addr}>" if display else addr
    msg["To"] = to
    msg["Subject"] = subject
    if text_body:
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content(html_body, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=True,
    )


async def _send_via_factory_api(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None,
    from_name: str | None,
    from_email: str | None,
    settings,
) -> None:
    import httpx

    payload = {
        "api_key": settings.factory_email_api_key,
        "to": to,
        "subject": subject,
        "html_body": html_body,
    }
    if text_body:
        payload["text_body"] = text_body
    if from_name:
        payload["from_name"] = from_name
    if from_email:
        payload["from_email"] = from_email

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.factory_email_api_url,
            json=payload,
            timeout=30,
        )

    if resp.status_code == 402:
        logger.error("Factory email relay: credits exhausted")
        raise RuntimeError("Email relay credits exhausted. Contact your admin.")
    if resp.status_code != 200:
        logger.error(
            "Factory email relay failed: %s %s", resp.status_code, resp.text
        )
        raise RuntimeError(f"Email relay error: {resp.status_code}")
