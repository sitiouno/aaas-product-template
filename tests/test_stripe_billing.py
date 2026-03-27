from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from product_app.database import dispose_database, initialize_database, session_scope
from product_app.models import User
from product_app.persistence import get_credit_balance, record_credit_transaction


class StripeBillingTestBase(unittest.TestCase):
    """Shared setUp / tearDown for Stripe billing tests."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_env = {key: os.environ.get(key) for key in (
            "DATABASE_URL",
            "DATABASE_SQLITE_PATH",
            "DATABASE_AUTO_CREATE",
            "CLOUD_SQL_INSTANCE_CONNECTION_NAME",
            "PRODUCT_DEFAULT_ORG_NAME",
            "PRODUCT_DEFAULT_USER_EMAIL",
            "PRODUCT_ADMIN_EMAIL",
        )}
        os.environ["DATABASE_URL"] = ""
        os.environ["DATABASE_SQLITE_PATH"] = str(Path(self.tempdir.name) / "test.db")
        os.environ["DATABASE_AUTO_CREATE"] = "true"
        os.environ["CLOUD_SQL_INSTANCE_CONNECTION_NAME"] = ""
        os.environ["PRODUCT_DEFAULT_ORG_NAME"] = "Quien Test"
        os.environ["PRODUCT_DEFAULT_USER_EMAIL"] = "owner@test.quien"
        os.environ.pop("PRODUCT_ADMIN_EMAIL", None)
        dispose_database()
        initialize_database()

    def tearDown(self) -> None:
        dispose_database()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()


class HandleCheckoutCompletedTest(StripeBillingTestBase):
    def test_credits_user_on_checkout(self) -> None:
        from product_app.stripe_billing import handle_checkout_completed

        with session_scope() as s:
            user = User(email="buyer@test.com", status="approved", stripe_customer_id="cus_test1")
            s.add(user)
            s.flush()
            user_id = user.id

            event_data = {
                "id": "cs_test_session_001",
                "client_reference_id": user_id,
                "metadata": {"credits": "25", "user_id": user_id, "user_email": "buyer@test.com"},
                "amount_total": 2500,
            }
            handle_checkout_completed(event_data, s)

            balance = get_credit_balance(s, user_id)
            self.assertEqual(balance, 25)

    def test_idempotent_double_checkout(self) -> None:
        from product_app.stripe_billing import handle_checkout_completed

        with session_scope() as s:
            user = User(email="idem@test.com", status="approved", stripe_customer_id="cus_test2")
            s.add(user)
            s.flush()
            user_id = user.id

            event_data = {
                "id": "cs_test_session_002",
                "client_reference_id": user_id,
                "metadata": {"credits": "10", "user_id": user_id, "user_email": "idem@test.com"},
                "amount_total": 1000,
            }
            handle_checkout_completed(event_data, s)
            handle_checkout_completed(event_data, s)

            balance = get_credit_balance(s, user_id)
            self.assertEqual(balance, 10)  # not 20


class HandleChargeRefundedTest(StripeBillingTestBase):
    def test_refund_deducts_credits(self) -> None:
        from product_app.stripe_billing import handle_charge_refunded

        with session_scope() as s:
            user = User(email="refund@test.com", status="approved", stripe_customer_id="cus_refund1")
            s.add(user)
            s.flush()
            user_id = user.id

            # Give user 50 credits
            record_credit_transaction(s, user_id, amount=50, source_type="admin_grant")

            event_data = {
                "id": "ch_test_charge_001",
                "customer": "cus_refund1",
                "amount_refunded": 3000,  # $30 -> 30 credits
            }
            handle_charge_refunded(event_data, s)

            balance = get_credit_balance(s, user_id)
            self.assertEqual(balance, 20)  # 50 - 30

    def test_refund_unknown_customer(self) -> None:
        from product_app.stripe_billing import handle_charge_refunded

        with session_scope() as s:
            event_data = {
                "id": "ch_test_charge_999",
                "customer": "cus_nonexistent",
                "amount_refunded": 1000,
            }
            # Should not crash
            handle_charge_refunded(event_data, s)


class GetStripeKeysTest(StripeBillingTestBase):
    def test_returns_test_keys_by_default(self) -> None:
        from product_app.stripe_billing import get_stripe_keys

        with session_scope() as s:
            secret, publishable, webhook = get_stripe_keys(s)
            # Just verify it returns strings without crashing
            self.assertIsInstance(secret, str)
            self.assertIsInstance(publishable, str)
            self.assertIsInstance(webhook, str)


if __name__ == "__main__":
    unittest.main()
