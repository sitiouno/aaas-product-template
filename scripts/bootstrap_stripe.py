"""Bootstrap Stripe products, prices, and webhook settings for Product Name."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class CatalogItem:
    key: str
    name: str
    description: str
    amount_cents: int
    mode: str
    interval: str | None = None


CATALOG: tuple[CatalogItem, ...] = (
    CatalogItem(
        key="credit",
        name="Product Name Credits",
        description="Prepaid credits for AI research runs. $1 per credit.",
        amount_cents=100,  # $1.00 per unit
        mode="payment",
    ),
)


def _stripe_module(secret_key: str):
    import stripe

    stripe.api_key = secret_key
    stripe.max_network_retries = 2
    return stripe


def _find_product(stripe, key: str):
    for product in stripe.Product.list(limit=100, active=True).auto_paging_iter():
        raw_meta = getattr(product, "metadata", None)
        metadata = raw_meta.to_dict() if hasattr(raw_meta, "to_dict") else (raw_meta or {})
        if metadata.get("research_lab_key") == key:
            return product
    return None


def _ensure_product(stripe, item: CatalogItem):
    product = _find_product(stripe, item.key)
    if product:
        return product
    return stripe.Product.create(
        name=item.name,
        description=item.description,
        metadata={"research_lab_key": item.key, "app": "research-lab-studio"},
    )


def _find_price(stripe, product_id: str, item: CatalogItem):
    for price in stripe.Price.list(product=product_id, active=True, limit=100).auto_paging_iter():
        recurring = getattr(price, "recurring", None)
        recurring_interval = getattr(recurring, "interval", None) if recurring else None
        matches_amount = int(getattr(price, "unit_amount", 0) or 0) == item.amount_cents
        matches_currency = str(getattr(price, "currency", "")) == "usd"
        matches_interval = recurring_interval == item.interval
        if matches_amount and matches_currency and matches_interval:
            return price
    return None


def _ensure_price(stripe, product_id: str, item: CatalogItem):
    price = _find_price(stripe, product_id, item)
    if price:
        return price

    payload = {
        "product": product_id,
        "currency": "usd",
        "unit_amount": item.amount_cents,
        "metadata": {"research_lab_key": item.key, "app": "research-lab-studio"},
    }
    if item.mode == "subscription":
        payload["recurring"] = {"interval": item.interval}
    return stripe.Price.create(**payload)


def _ensure_webhook_endpoint(stripe, webhook_url: str):
    enabled_events = [
        "checkout.session.completed",
        "invoice.paid",
        "invoice.payment_failed",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "charge.refunded",
    ]
    for endpoint in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
        if str(getattr(endpoint, "url", "")) == webhook_url:
            return endpoint, None

    endpoint = stripe.WebhookEndpoint.create(
        url=webhook_url,
        enabled_events=enabled_events,
        metadata={"app": "research-lab-studio"},
    )
    secret = getattr(endpoint, "secret", None)
    return endpoint, secret


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
        help="Public base URL used to derive the Stripe webhook endpoint.",
    )
    parser.add_argument(
        "--webhook-url",
        default="",
        help="Explicit Stripe webhook URL. Overrides --base-url when provided.",
    )
    args = parser.parse_args()

    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise SystemExit("STRIPE_SECRET_KEY is required before bootstrapping Stripe.")

    stripe = _stripe_module(secret_key)
    account = stripe.Account.retrieve()
    webhook_url = args.webhook_url.strip() or (
        f"{args.base_url}/api/v1/stripe/webhook" if args.base_url else ""
    )

    resolved_prices: dict[str, str] = {}
    for item in CATALOG:
        product = _ensure_product(stripe, item)
        price = _ensure_price(stripe, product.id, item)
        resolved_prices[item.key] = str(price.id)

    webhook_secret = None
    if webhook_url:
        _, webhook_secret = _ensure_webhook_endpoint(stripe, webhook_url)

    print("# Stripe bootstrap complete")
    print(f"# Account: {account.id}")
    print(f"# Mode: {'live' if secret_key.startswith('sk_live_') else 'test'}")
    print("")
    print("STRIPE_CREDIT_PRICE_ID=" + resolved_prices["credit"])
    if webhook_secret:
        print("STRIPE_WEBHOOK_SECRET=" + webhook_secret)
    elif webhook_url:
        print("# Existing webhook endpoint reused; fetch its signing secret from Stripe Dashboard or MCP.")
    print("# Set STRIPE_PUBLISHABLE_KEY from Stripe Developers > API keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
