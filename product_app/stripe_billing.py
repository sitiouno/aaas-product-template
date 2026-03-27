"""Stripe billing integration — checkout sessions, webhooks, and invoice management."""
from __future__ import annotations

import logging
from typing import Any

from .models import User
from .persistence import get_platform_setting, record_credit_transaction

logger = logging.getLogger(__name__)


# ── Key management ───────────────────────────────────────────────────


def _setting_or(session, key: str, fallback: str) -> str:
    """Return a platform setting value, falling back to *fallback*."""
    return get_platform_setting(session, key, default="") or fallback


def get_stripe_keys(session) -> tuple[str, str, str]:
    """Return (secret_key, publishable_key, webhook_secret) based on active Stripe mode."""
    from .config import load_settings

    settings = load_settings()
    mode = get_platform_setting(session, "stripe_mode", default="test")

    if mode == "live":
        sk = _setting_or(session, "stripe_secret_key_live", settings.stripe_secret_key_live)
        pk = _setting_or(session, "stripe_publishable_key_live", settings.stripe_publishable_key_live)
        wh = _setting_or(session, "stripe_webhook_secret_live", settings.stripe_webhook_secret_live)
    else:
        sk = _setting_or(session, "stripe_secret_key_test", settings.stripe_secret_key_test)
        pk = _setting_or(session, "stripe_publishable_key_test", settings.stripe_publishable_key_test)
        wh = _setting_or(session, "stripe_webhook_secret_test", settings.stripe_webhook_secret_test)

    logger.info(
        "get_stripe_keys: mode=%s, sk=%s, pk=%s, wh=%s",
        mode, bool(sk), bool(pk), bool(wh),
    )
    return (sk, pk, wh)


# ── Stripe client ────────────────────────────────────────────────────


def _get_stripe_client(secret_key: str):
    """Thread-safe Stripe client instance."""
    import stripe

    return stripe.StripeClient(secret_key, max_network_retries=2)


# ── Customer management ──────────────────────────────────────────────


def get_or_create_stripe_customer(
    user: User, session, *, secret_key: str, stripe_mode: str = "test",
) -> str:
    """Return existing Stripe customer ID for the current mode, or create one.

    Each user stores separate customer IDs for test and live modes so switching
    modes never requires deleting or re-validating customers.
    """
    attr = f"stripe_customer_id_{stripe_mode}"
    existing = getattr(user, attr, None)
    if existing:
        return existing

    # Migrate: check legacy stripe_customer_id field
    if user.stripe_customer_id:
        try:
            client = _get_stripe_client(secret_key)
            client.customers.retrieve(user.stripe_customer_id)
            setattr(user, attr, user.stripe_customer_id)
            session.flush()
            return user.stripe_customer_id
        except Exception:
            logger.info(
                "Legacy stripe_customer_id %s invalid for %s mode",
                user.stripe_customer_id, stripe_mode,
            )

    client = _get_stripe_client(secret_key)
    customer = client.customers.create(
        params={
            "email": user.email,
            "name": user.full_name or user.email,
            "metadata": {"user_id": user.id},
        }
    )
    setattr(user, attr, customer.id)
    user.stripe_customer_id = customer.id  # keep legacy field in sync
    session.flush()
    return customer.id


# ── Checkout ─────────────────────────────────────────────────────────


def create_checkout_session(
    *,
    user: User,
    quantity: int,
    price_id: str,
    success_url: str,
    cancel_url: str,
    secret_key: str,
    stripe_mode: str = "test",
    session,
) -> dict[str, str]:
    """Create a Stripe Checkout Session and return its URL and ID."""
    customer_id = get_or_create_stripe_customer(
        user, session, secret_key=secret_key, stripe_mode=stripe_mode,
    )
    client = _get_stripe_client(secret_key)

    checkout = client.checkout.sessions.create(
        params={
            "mode": "payment",
            "customer": customer_id,
            "client_reference_id": user.id,
            "line_items": [{"price": price_id, "quantity": quantity}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "user_id": user.id,
                "user_email": user.email,
                "credits": str(quantity),
            },
        }
    )
    return {"checkout_url": checkout.url, "session_id": checkout.id}


# ── Webhook handlers ─────────────────────────────────────────────────


def handle_checkout_completed(event_data: dict, db_session) -> None:
    """Credit user after a successful checkout. Idempotent via external_reference."""
    session_id = event_data.get("id", "")
    user_id = event_data.get("client_reference_id")
    metadata = event_data.get("metadata") or {}
    credits = int(metadata.get("credits", 0))
    amount_total = event_data.get("amount_total", 0)

    if not user_id or credits <= 0:
        logger.warning("checkout.session.completed missing user_id or credits: %s", session_id)
        return

    user = db_session.get(User, user_id)
    if user is None:
        logger.error("checkout.session.completed: user %s not found", user_id)
        return

    record_credit_transaction(
        db_session,
        user_id=user.id,
        amount=credits,
        source_type="stripe_checkout",
        description=f"Stripe checkout: {credits} credits (${amount_total / 100:.2f})",
        external_reference=session_id,
    )
    logger.info("Credited %d credits to user %s via checkout %s", credits, user_id, session_id)


def handle_charge_refunded(event_data: dict, db_session) -> None:
    """Deduct credits when a charge is refunded. Idempotent via external_reference."""
    charge_id = event_data.get("id", "")
    customer_id = event_data.get("customer", "")
    amount_refunded = event_data.get("amount_refunded", 0)
    credits_to_deduct = amount_refunded // 100

    if credits_to_deduct <= 0:
        logger.info("charge.refunded with zero credits to deduct: %s", charge_id)
        return

    from sqlalchemy import or_
    user = (
        db_session.query(User)
        .filter(or_(
            User.stripe_customer_id == customer_id,
            User.stripe_customer_id_test == customer_id,
            User.stripe_customer_id_live == customer_id,
        ))
        .first()
    )
    if user is None:
        logger.warning("charge.refunded: no user with stripe_customer_id=%s", customer_id)
        return

    record_credit_transaction(
        db_session,
        user_id=user.id,
        amount=-credits_to_deduct,
        source_type="stripe_refund",
        description=f"Stripe refund: -{credits_to_deduct} credits (charge {charge_id})",
        external_reference=f"refund:{charge_id}",
    )
    logger.info("Deducted %d credits from user %s via refund %s", credits_to_deduct, user.id, charge_id)


# ── Invoice listing ──────────────────────────────────────────────────


def _extract_receipt_url(pi) -> str | None:
    """Extract receipt URL from a PaymentIntent, checking latest_charge as fallback."""
    url = getattr(pi, "receipt_url", None)
    if url:
        return url
    charge = getattr(pi, "latest_charge", None)
    if charge:
        return getattr(charge, "receipt_url", None)
    return None


def list_invoices(stripe_customer_id: str, *, secret_key: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch recent PaymentIntents for a customer from Stripe."""
    try:
        client = _get_stripe_client(secret_key)
        result = client.payment_intents.list(
            params={"customer": stripe_customer_id, "limit": limit}
        )
        return [
            {
                "id": pi.id,
                "amount": pi.amount,
                "currency": pi.currency,
                "status": pi.status,
                "created": pi.created,
                "receipt_url": _extract_receipt_url(pi),
            }
            for pi in result.data
        ]
    except Exception:
        logger.exception("Failed to list invoices for customer %s", stripe_customer_id)
        return []


# ── Billing portal ───────────────────────────────────────────────────


def create_portal_session(stripe_customer_id: str, *, secret_key: str, return_url: str) -> str:
    """Create a Stripe billing portal session and return its URL."""
    client = _get_stripe_client(secret_key)
    portal = client.billing_portal.sessions.create(
        params={
            "customer": stripe_customer_id,
            "return_url": return_url,
        }
    )
    return portal.url
