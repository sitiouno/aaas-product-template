"""Send OTP verification code via email."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def send_otp_email(email: str, code: str, *, settings) -> None:
    """Send a styled OTP email via SMTP."""
    import aiosmtplib
    from email.message import EmailMessage

    html = f"""\
<div style="font-family:Inter,sans-serif;max-width:460px;margin:0 auto;padding:32px;background:#0a0a12;color:#e0e0e0;border-radius:12px;">
  <h2 style="color:#38bdf8;margin:0 0 8px;">Product Name</h2>
  <p style="margin:0 0 24px;color:#8b92a8;font-size:14px;">Your verification code</p>
  <div style="background:#12121e;border:1px solid #1e1e3a;border-radius:8px;padding:24px;text-align:center;margin-bottom:24px;">
    <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#ffffff;">{code}</span>
  </div>
  <p style="color:#8b92a8;font-size:13px;margin:0;">This code expires in 10 minutes. If you didn't request this, ignore this email.</p>
</div>"""

    msg = EmailMessage()
    from_email = settings.magic_link_from_email or settings.smtp_user
    msg["From"] = f"Product Name <{from_email}>"
    msg["To"] = email
    msg["Subject"] = f"Product Name - Your code: {code}"
    msg.set_content(f"Your Product Name verification code is: {code}\n\nExpires in 10 minutes.")
    msg.add_alternative(html, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=True,
    )
