"""Send OTP verification code via email."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def send_otp_email(email: str, code: str, *, settings) -> None:
    """Send a styled OTP email via the best available transport."""
    from .email_sender import send_email

    product_name = getattr(settings, "website_name", "") or "Product"

    html = f"""\
<div style="font-family:Inter,sans-serif;max-width:460px;margin:0 auto;padding:32px;background:#0a0a12;color:#e0e0e0;border-radius:12px;">
  <h2 style="color:#38bdf8;margin:0 0 8px;">{product_name}</h2>
  <p style="margin:0 0 24px;color:#8b92a8;font-size:14px;">Your verification code</p>
  <div style="background:#12121e;border:1px solid #1e1e3a;border-radius:8px;padding:24px;text-align:center;margin-bottom:24px;">
    <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#ffffff;">{code}</span>
  </div>
  <p style="color:#8b92a8;font-size:13px;margin:0;">This code expires in 10 minutes. If you didn't request this, ignore this email.</p>
</div>"""

    await send_email(
        to=email,
        subject=f"{product_name} - Your code: {code}",
        html_body=html,
        text_body=f"Your {product_name} verification code is: {code}\n\nExpires in 10 minutes.",
        from_name=product_name,
        settings=settings,
    )
