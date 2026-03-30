"""Send email notification when a research report completes."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def send_report_ready_email(
    *,
    email: str,
    full_name: str | None,
    report_title: str,
    job_id: str,
    research_style: str,
    language: str,
    credits_consumed: int,
    base_url: str,
    settings,
) -> None:
    """Send a branded email notifying the user their report is ready."""
    from .email_sender import email_available, send_email

    if not email_available(settings):
        logger.warning("Email not configured, skipping report notification for %s", email)
        return

    product_name = getattr(settings, "website_name", "") or "Product"
    report_url = f"{base_url}/{language}/app#report-viewer/{job_id}"
    greeting = full_name or email.split("@")[0]

    if language == "es":
        subject = f"Tu reporte esta listo — {report_title}"
        heading = "Tu reporte esta listo"
        body_text = f"Hola {greeting}, tu investigacion ha sido completada."
        credits_label = f"Creditos consumidos: {credits_consumed}"
        cta_text = "Ver Reporte"
        footer_text = "Recibiste este email porque tienes notificaciones activadas en tu cuenta."
        disable_text = "Desactivar notificaciones"
    else:
        subject = f"Your report is ready — {report_title}"
        heading = "Your report is ready"
        body_text = f"Hi {greeting}, your research has been completed."
        credits_label = f"Credits consumed: {credits_consumed}"
        cta_text = "View Report"
        footer_text = "You received this email because notifications are enabled in your account."
        disable_text = "Disable notifications"

    account_url = f"{base_url}/{language}/app#account"

    html = f"""\
<div style="font-family:Inter,system-ui,sans-serif;max-width:520px;margin:0 auto;padding:32px;background:#0a0a12;color:#e0e0e0;border-radius:12px;">
  <h2 style="color:#38bdf8;margin:0 0 8px;">{product_name}</h2>
  <p style="margin:0 0 24px;color:#8b92a8;font-size:14px;">{heading}</p>
  <div style="background:#12121e;border:1px solid #1e1e3a;border-radius:8px;padding:20px;margin-bottom:20px;">
    <p style="color:#ffffff;font-size:16px;margin:0 0 8px;font-weight:600;">{report_title}</p>
    <p style="color:#8b92a8;font-size:13px;margin:0 0 4px;">{body_text}</p>
    <p style="color:#8b92a8;font-size:13px;margin:0;">{credits_label}</p>
  </div>
  <a href="{report_url}" style="display:inline-block;background:#38bdf8;color:#0a0a12;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">{cta_text}</a>
  <p style="color:#5a6478;font-size:11px;margin:24px 0 0;">{footer_text} <a href="{account_url}" style="color:#5a6478;">{disable_text}</a></p>
</div>"""

    plain = f"{heading}\n\n{body_text}\n{credits_label}\n\n{cta_text}: {report_url}"

    await send_email(
        to=email,
        subject=subject,
        html_body=html,
        text_body=plain,
        from_name=product_name,
        settings=settings,
    )
    logger.info("Report notification sent to %s for job %s", email, job_id)
