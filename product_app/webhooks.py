"""Webhook delivery with HMAC-SHA256 signing and retry."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

RETRY_DELAYS = [1, 5, 30]  # seconds between retries


def sign_payload(body: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_webhook_payload(
    *,
    event: str,
    job_id: str,
    research_style: str,
    status: str,
    credits_consumed: int,
    language: str,
    artifacts: list[dict[str, str]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build the webhook event payload."""
    payload: dict[str, Any] = {
        "event": event,
        "job_id": job_id,
        "research_style": research_style,
        "status": status,
        "credits_consumed": credits_consumed,
        "language": language,
        "artifacts": artifacts or [],
        "report_url": f"/api/v1/runs/{job_id}/report",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if error:
        payload["error"] = error
    return payload


async def deliver_webhook(
    url: str,
    payload: dict[str, Any],
    secret: str,
    max_retries: int = 3,
) -> bool:
    """Deliver webhook with HMAC signing and exponential backoff retry.

    Returns True if delivery succeeded, False otherwise.
    """
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = sign_payload(body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
    }

    delays = RETRY_DELAYS[:max_retries]
    for attempt, delay in enumerate(delays, 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=body, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if 200 <= resp.status < 300:
                        logger.info("Webhook delivered to %s (attempt %d)", url, attempt)
                        return True
                    logger.warning(
                        "Webhook to %s returned %d (attempt %d/%d)",
                        url, resp.status, attempt, len(delays),
                    )
        except Exception as exc:
            logger.warning(
                "Webhook to %s failed (attempt %d/%d): %s",
                url, attempt, len(delays), exc,
            )

        if attempt < len(delays):
            await asyncio.sleep(delay)

    logger.error("Webhook delivery to %s failed after %d attempts", url, len(delays))
    return False
