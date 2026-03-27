from __future__ import annotations

import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from product_app.database import dispose_database, initialize_database, session_scope
from product_app.models import (
    DeploymentStyle,
    User,
)
from product_app.persistence import (
    bootstrap_defaults,
    create_run_record,
    persist_run_event,
    record_credit_transaction,
)


class WebAppTestBase(unittest.TestCase):
    """Common setup/teardown for webapp tests."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_env = {
            key: os.environ.get(key)
            for key in (
                "DATABASE_URL",
                "DATABASE_SQLITE_PATH",
                "DATABASE_AUTO_CREATE",
                "CLOUD_SQL_INSTANCE_CONNECTION_NAME",
                "PRODUCT_OUTPUT_DIR",
                "APP_SESSION_SECRET",
                "PRODUCT_ENABLE_DEV_AUTH",
                "ADMIN_EMAIL",
            )
        }
        os.environ["DATABASE_URL"] = ""
        os.environ["DATABASE_SQLITE_PATH"] = str(Path(self.tempdir.name) / "webapp.db")
        os.environ["DATABASE_AUTO_CREATE"] = "true"
        os.environ["CLOUD_SQL_INSTANCE_CONNECTION_NAME"] = ""
        os.environ["PRODUCT_OUTPUT_DIR"] = str(Path(self.tempdir.name) / "outputs")
        os.environ["APP_SESSION_SECRET"] = "test-session-secret"
        os.environ["PRODUCT_ENABLE_DEV_AUTH"] = "true"
        os.environ["ADMIN_EMAIL"] = "admin@test.quien"
        dispose_database()
        initialize_database()

        import product_app.webapp as webapp_module

        self.webapp = importlib.reload(webapp_module)
        self.webapp.jobs.clear()
        self.webapp._otp_store.clear()
        self.webapp.otp_email_rate_limiter.buckets.clear()
        self.webapp.otp_ip_rate_limiter.buckets.clear()
        # Manually bootstrap admin user (lifespan only runs with context manager)
        from product_app.config import load_settings as _load_settings
        _s = _load_settings()
        with session_scope() as sess:
            bootstrap_defaults(sess, _s)
        self.client = TestClient(self.webapp.app)

    def tearDown(self) -> None:
        self.client.close()
        self.webapp.jobs.clear()
        dispose_database()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def _dev_login(self, email: str = "testuser@test.quien", full_name: str = "Test User"):
        """Authenticate via dev-session and return the response."""
        return self.client.post(
            "/api/v1/auth/dev-session",
            json={"email": email, "full_name": full_name},
        )

    def _get_user_id(self, email: str) -> str:
        """Look up a user's ID by email."""
        with session_scope() as s:
            user = s.query(User).filter(User.email == email.lower()).first()
            return user.id


class WebAppHealthTest(WebAppTestBase):
    def test_healthz(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_api_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)


class WebAppAuthTest(WebAppTestBase):
    def test_dev_session_creates_user_and_authenticates(self) -> None:
        response = self._dev_login("devuser@test.quien", "Dev User")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["email"], "devuser@test.quien")

    def test_dev_session_disabled_returns_404(self) -> None:
        self.webapp.settings = self.webapp.settings.__class__(
            **{**self.webapp.settings.__dict__, "enable_dev_auth": False}
        )
        # Need to patch settings at module level
        with patch.object(self.webapp, "settings", self.webapp.settings):
            response = self.client.post(
                "/api/v1/auth/dev-session",
                json={"email": "nope@test.quien"},
            )
            self.assertEqual(response.status_code, 404)

    def test_logout_clears_cookie(self) -> None:
        self._dev_login()
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, 200)

    def test_magic_link_rejects_public_email(self) -> None:
        client = TestClient(self.webapp.app)
        resp = client.post("/api/v1/auth/magic-link", json={"email": "user@gmail.com"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "corporate_email_required")

    def test_magic_link_accepts_corporate_email(self) -> None:
        from product_app.config import load_settings as _load_settings
        mock_settings = _load_settings()
        mock_settings = mock_settings.__class__(**{**mock_settings.__dict__, "smtp_host": "smtp.test.com"})
        client = TestClient(self.webapp.app)
        with patch("product_app.webapp.load_settings", return_value=mock_settings), \
             patch("product_app.otp_email.send_otp_email", new_callable=AsyncMock):
            resp = client.post("/api/v1/auth/magic-link", json={"email": "new@bigcorp.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["message"], "otp_sent")

    def test_verify_otp_new_user_returns_registration_token(self) -> None:
        email = "brand-new@megacorp.com"
        self.webapp._otp_store[email] = ("123456", time.time() + 600)
        client = TestClient(self.webapp.app)
        resp = client.post("/api/v1/auth/verify-otp", json={"email": email, "code": "123456"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["action"], "complete_registration")
        self.assertIn("registration_token", data)

    def test_complete_registration_creates_user(self) -> None:
        email = "fresh@newcorp.com"
        from product_app.magic_link import generate_registration_token
        from product_app.config import load_settings as _ls
        token = generate_registration_token(email, _ls().magic_link_secret)
        client = TestClient(self.webapp.app)
        resp = client.post("/api/v1/auth/complete-registration", json={
            "registration_token": token,
            "full_name": "Fresh User",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["action"], "registered")
        self.assertTrue(data.get("is_new_user"))
        with session_scope() as s:
            user = s.query(User).filter(User.email == email).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.status, "approved")

    def test_verify_magic_link_invalid_token_returns_401(self) -> None:
        response = self.client.post(
            "/api/v1/auth/verify",
            json={"token": "invalid.token"},
        )
        self.assertEqual(response.status_code, 401)


class WebAppAccountTest(WebAppTestBase):
    def test_account_requires_auth(self) -> None:
        response = self.client.get("/api/v1/account")
        self.assertEqual(response.status_code, 401)

    def test_account_returns_user_data(self) -> None:
        self._dev_login("acct@test.quien", "Acct User")
        response = self.client.get("/api/v1/account")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["email"], "acct@test.quien")
        self.assertIn("credits", payload)
        self.assertIn("api_keys", payload)

    def test_patch_account_onboarding_completed(self) -> None:
        with session_scope() as s:
            user = User(email="onboard@corp.com", full_name="Onboard", status="approved")
            s.add(user)
            s.flush()
            user_id = user.id
        from product_app.security import Identity, create_session_token
        token = create_session_token(Identity(email="onboard@corp.com", user_id=user_id, is_admin=False))
        client = TestClient(self.webapp.app)
        resp = client.patch(
            "/api/v1/account",
            json={"onboarding_completed": True},
            cookies={"quien_session": token},
        )
        self.assertEqual(resp.status_code, 200)
        with session_scope() as s:
            user = s.get(User, user_id)
            self.assertTrue(user.onboarding_completed)


class WebAppAccessRequestTest(WebAppTestBase):
    def test_request_access(self) -> None:
        response = self.client.post(
            "/api/v1/access/request",
            json={
                "email": "requester@test.quien",
                "full_name": "Requester",
                "company": "Test Co",
                "message": "Please let me in",
            },
        )
        self.assertEqual(response.status_code, 202)
        self.assertIn("request_id", response.json())

    def test_access_status(self) -> None:
        self.client.post(
            "/api/v1/access/request",
            json={"email": "statuscheck@test.quien", "full_name": "Check"},
        )
        response = self.client.get(
            "/api/v1/access/status",
            params={"email": "statuscheck@test.quien"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")

    def test_access_status_not_found(self) -> None:
        response = self.client.get(
            "/api/v1/access/status",
            params={"email": "nonexistent@test.quien"},
        )
        self.assertEqual(response.status_code, 404)


class WebAppRunTest(WebAppTestBase):
    def test_create_run_requires_auth(self) -> None:
        response = self.client.post(
            "/api/v1/runs",
            json={"prompt": "Analyze https://example.com as a potential investment."},
        )
        self.assertEqual(response.status_code, 401)

    def test_create_run_requires_credits(self) -> None:
        self._dev_login("nocredits@test.quien", "No Credits")
        response = self.client.post(
            "/api/v1/runs",
            json={"prompt": "Analyze https://example.com as a potential investment."},
        )
        self.assertEqual(response.status_code, 402)

    def test_create_run_with_credits(self) -> None:
        self._dev_login("credited@test.quien", "Credited User")
        user_id = self._get_user_id("credited@test.quien")
        with session_scope() as s:
            record_credit_transaction(
                s, user_id, amount=5, source_type="admin_grant",
                description="Test credits", external_reference="test-grant-1",
            )

        with patch.object(self.webapp, "_run_job", new=AsyncMock(return_value=None)):
            response = self.client.post(
                "/api/v1/runs",
                json={"prompt": "Analyze https://example.com as a potential investment."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("job_id", response.json())

    def test_get_run_not_found(self) -> None:
        self._dev_login()
        response = self.client.get("/api/v1/runs/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_recent_runs_requires_auth(self) -> None:
        response = self.client.get("/api/runs")
        self.assertEqual(response.status_code, 401)

    def test_recent_runs_returns_list(self) -> None:
        self._dev_login("runslist@test.quien")
        user_id = self._get_user_id("runslist@test.quien")
        with session_scope() as s:
            create_run_record(
                s, "run-list-1", "Test prompt for listing",
                user_id=user_id,
                research_style=DeploymentStyle.DEPLOY_PRODUCT.value,
            )
        response = self.client.get("/api/runs")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()["runs"], list)


class WebAppRunArtifactTest(WebAppTestBase):
    def test_run_read_without_auth_from_db(self) -> None:
        """Runs stored in DB can be read without auth (for public/completed)."""
        user_id = self._ensure_user("artifact@test.quien")
        with session_scope() as s:
            create_run_record(
                s, "pub-job", "Analyze https://example.com",
                user_id=user_id,
            )
        persist_run_event(
            "pub-job", "finished",
            {
                "status": "completed",
                "language": "en",
                "research_style": "deploy_product",
                "progress_pct": 100,
                "stages": [],
                "logs": [],
                "sections": [
                    {"id": "s1", "title": "Summary", "text": "Test output"}
                ],
                "artifacts": [
                    {
                        "name": "preview.html",
                        "path": "preview.html",
                        "url": "/artifacts/preview.html",
                        "kind": "report_html",
                        "requires_payment": False,
                    }
                ],
                "final_text": "Test output",
                "error": None,
            },
            "Complete",
        )
        response = self.client.get("/api/v1/runs/pub-job")
        # Runs require authentication since security update
        self.assertEqual(response.status_code, 401)

    def test_artifact_download_without_auth(self) -> None:
        user_id = self._ensure_user("artdl@test.quien")
        with session_scope() as s:
            create_run_record(
                s, "art-job", "Analyze https://example.com",
                user_id=user_id,
            )
        persist_run_event(
            "art-job", "finished",
            {
                "status": "completed",
                "language": "en",
                "research_style": "deploy_product",
                "progress_pct": 100,
                "stages": [],
                "logs": [],
                "sections": [],
                "artifacts": [
                    {
                        "name": "test-artifact.html",
                        "path": "test-artifact.html",
                        "url": "/artifacts/test-artifact.html",
                        "kind": "report_html",
                        "mime_type": "text/html",
                        "requires_payment": False,
                    }
                ],
                "final_text": "",
                "error": None,
            },
            "Done",
        )
        output_dir = Path(os.environ["PRODUCT_OUTPUT_DIR"])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "test-artifact.html").write_text(
            "<html><body>content</body></html>", encoding="utf-8"
        )
        response = self.client.get("/api/v1/runs/art-job/artifacts/test-artifact.html")
        # Artifacts require authentication since security update
        self.assertEqual(response.status_code, 401)

    def _ensure_user(self, email: str) -> str:
        with session_scope() as s:
            user = User(email=email, status="approved")
            s.add(user)
            s.flush()
            return user.id


class WebAppNormalizeSnapshotTest(WebAppTestBase):
    def test_normalize_snapshot_artifacts_uses_api_routes(self) -> None:
        normalized = self.webapp._normalize_snapshot_artifacts(
            "job-123",
            {
                "artifacts": [
                    {
                        "name": "teaser memo.html",
                        "url": "/artifacts/teaser memo.html",
                    }
                ]
            },
        )
        self.assertEqual(
            normalized["artifacts"][0]["url"],
            "/api/v1/runs/job-123/artifacts/teaser%20memo.html",
        )


class WebAppAdminTest(WebAppTestBase):
    def test_admin_list_users_requires_admin(self) -> None:
        self._dev_login("regular@test.quien", "Regular User")
        response = self.client.get("/api/v1/admin/users")
        self.assertEqual(response.status_code, 403)

    def test_admin_list_users_as_admin(self) -> None:
        # Login as admin (bootstrapped via ADMIN_EMAIL env var)
        self._dev_login("admin@test.quien", "Admin User")
        response = self.client.get("/api/v1/admin/users")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        users = data["users"]
        self.assertIsInstance(users, list)
        emails = [u["email"] for u in users]
        self.assertIn("admin@test.quien", emails)

    def test_admin_grant_credits(self) -> None:
        self._dev_login("admin@test.quien", "Admin User")
        user_id = self._get_user_id("admin@test.quien")
        response = self.client.post(
            "/api/v1/admin/grant-credits",
            json={"user_id": user_id, "amount": 10, "description": "Test grant"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["granted"], 10)

    def test_admin_access_requests(self) -> None:
        # Submit an access request
        self.client.post(
            "/api/v1/access/request",
            json={"email": "pending@test.quien", "full_name": "Pending"},
        )
        # Login as admin and list
        self._dev_login("admin@test.quien", "Admin User")
        response = self.client.get("/api/v1/admin/access-requests")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        reqs = data["requests"]
        self.assertTrue(len(reqs) >= 1)
        pending_req = [r for r in reqs if r["email"] == "pending@test.quien"]
        self.assertEqual(len(pending_req), 1)

        # Approve it
        req_id = pending_req[0]["id"]
        approve_response = self.client.post(
            f"/api/v1/admin/access-requests/{req_id}/approve",
            json={"initial_credits": 5},
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["status"], "approved")


class WebAppUsageTest(WebAppTestBase):
    def test_usage_requires_auth(self) -> None:
        response = self.client.get("/api/v1/account/usage")
        self.assertEqual(response.status_code, 401)

    def test_usage_returns_data(self) -> None:
        self._dev_login("usage@test.quien", "Usage User")
        response = self.client.get("/api/v1/account/usage")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("daily", payload)
        self.assertIn("by_api_key", payload)


class WebAppApiKeyTest(WebAppTestBase):
    def test_api_key_create_requires_credits(self) -> None:
        self._dev_login("nokey@test.quien", "No Key User")
        response = self.client.post(
            "/api/v1/api-keys",
            json={"name": "Test Key"},
        )
        self.assertEqual(response.status_code, 403)

    def test_api_key_lifecycle(self) -> None:
        self._dev_login("keyuser@test.quien", "Key User")
        user_id = self._get_user_id("keyuser@test.quien")
        with session_scope() as s:
            record_credit_transaction(
                s, user_id, amount=10, source_type="admin_grant",
                description="Test credits",
            )

        create_resp = self.client.post(
            "/api/v1/api-keys",
            json={"name": "My API Key"},
        )
        self.assertEqual(create_resp.status_code, 200)
        key_data = create_resp.json()
        self.assertIn("api_key", key_data)
        self.assertIn("id", key_data)

        delete_resp = self.client.delete(f"/api/v1/api-keys/{key_data['id']}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json()["status"], "revoked")


class WebAppPublicConfigTest(WebAppTestBase):
    def test_public_config(self) -> None:
        response = self.client.get("/api/public-config")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("language", payload)
        self.assertIn("docs_url", payload)
        # Firebase config should no longer be present
        self.assertNotIn("firebase", payload)

    def test_research_capabilities(self) -> None:
        response = self.client.get("/api/v1/research/capabilities")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("styles", payload)
        style_keys = [s["key"] for s in payload["styles"]]
        self.assertIn("deploy_product", style_keys)


class WebAppBillingTest(WebAppTestBase):
    def test_billing_checkout_requires_auth(self):
        client = TestClient(self.webapp.app)
        resp = client.post("/api/v1/billing/checkout", json={"quantity": 10})
        self.assertEqual(resp.status_code, 401)

    def test_billing_checkout_validates_quantity(self):
        self._dev_login("billing@test.quien", "Billing User")
        resp = self.client.post("/api/v1/billing/checkout", json={"quantity": 0})
        self.assertEqual(resp.status_code, 400)
        resp2 = self.client.post("/api/v1/billing/checkout", json={"quantity": 10001})
        self.assertEqual(resp2.status_code, 400)

    def test_billing_checkout_no_stripe_returns_503(self):
        self._dev_login("billing2@test.quien", "Billing User 2")
        resp = self.client.post("/api/v1/billing/checkout", json={"credits": 5})
        # 503 if Stripe not configured, 200 with checkout_url if configured
        if resp.status_code == 200:
            self.assertIn("checkout_url", resp.json())
        else:
            self.assertEqual(resp.status_code, 503)

    def test_stripe_webhook_rejects_bad_signature(self):
        client = TestClient(self.webapp.app)
        resp = client.post("/api/v1/stripe/webhook", content=b"{}", headers={"stripe-signature": "bad"})
        # 500 if webhook_secret empty, 400 if verified
        self.assertIn(resp.status_code, [400, 500])

    def test_billing_invoices_requires_auth(self):
        client = TestClient(self.webapp.app)
        resp = client.get("/api/v1/billing/invoices")
        self.assertEqual(resp.status_code, 401)

    def test_billing_invoices_empty_for_new_user(self):
        self._dev_login("invoices@test.quien", "Invoice User")
        resp = self.client.get("/api/v1/billing/invoices")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_billing_portal_requires_auth(self):
        client = TestClient(self.webapp.app)
        resp = client.get("/api/v1/billing/portal")
        self.assertEqual(resp.status_code, 401)

    def test_billing_portal_no_customer_returns_404(self):
        self._dev_login("portal@test.quien", "Portal User")
        resp = self.client.get("/api/v1/billing/portal")
        self.assertEqual(resp.status_code, 404)


class WebAppAdminSettingsTest(WebAppTestBase):
    def test_admin_get_settings(self):
        self._dev_login("admin@test.quien", "Admin User")
        resp = self.client.get("/api/v1/admin/settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("default_initial_credits", data)
        self.assertIn("stripe_mode", data)
        self.assertIn("stripe_credit_price_id_test", data)
        self.assertIn("stripe_credit_price_id_live", data)

    def test_admin_patch_settings(self):
        self._dev_login("admin@test.quien", "Admin User")
        resp = self.client.patch(
            "/api/v1/admin/settings",
            json={"default_initial_credits": "25"},
        )
        self.assertEqual(resp.status_code, 200)
        # Verify it persisted
        resp2 = self.client.get("/api/v1/admin/settings")
        self.assertEqual(resp2.json()["default_initial_credits"], "25")

    def test_admin_patch_settings_validates_stripe_mode(self):
        self._dev_login("admin@test.quien", "Admin User")
        resp = self.client.patch(
            "/api/v1/admin/settings",
            json={"stripe_mode": "invalid"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_admin_patch_settings_validates_credits_number(self):
        self._dev_login("admin@test.quien", "Admin User")
        resp = self.client.patch(
            "/api/v1/admin/settings",
            json={"default_initial_credits": "not_a_number"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_admin_patch_settings_rejects_unknown_keys(self):
        self._dev_login("admin@test.quien", "Admin User")
        resp = self.client.patch(
            "/api/v1/admin/settings",
            json={"unknown_key": "value"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_cannot_access_settings(self):
        self._dev_login("regular@test.quien", "Regular User")
        resp = self.client.get("/api/v1/admin/settings")
        self.assertEqual(resp.status_code, 403)

    def test_admin_billing_summary(self):
        self._dev_login("admin@test.quien", "Admin User")
        resp = self.client.get("/api/v1/admin/billing/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_revenue_usd", data)
        self.assertIn("period_revenue_usd", data)
        self.assertIn("total_purchases", data)
        self.assertIn("period_purchases", data)
        self.assertIn("active_paying_users", data)
        self.assertIn("by_user", data)

    def test_admin_billing_summary_with_transactions(self):
        self._dev_login("admin@test.quien", "Admin User")
        admin_id = self._get_user_id("admin@test.quien")
        with session_scope() as s:
            record_credit_transaction(
                s, admin_id, amount=10, source_type="stripe_checkout",
                description="Test purchase", external_reference="cs_test_123",
            )
        resp = self.client.get("/api/v1/admin/billing/summary?period=all")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["total_revenue_usd"], 10.0)
        self.assertGreaterEqual(data["total_purchases"], 1)

    def test_admin_billing_transactions(self):
        self._dev_login("admin@test.quien", "Admin User")
        resp = self.client.get("/api/v1/admin/billing/transactions")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("transactions", data)
        self.assertIsInstance(data["transactions"], list)

    def test_non_admin_cannot_access_billing_summary(self):
        self._dev_login("regular@test.quien", "Regular User")
        resp = self.client.get("/api/v1/admin/billing/summary")
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_cannot_access_billing_transactions(self):
        self._dev_login("regular@test.quien", "Regular User")
        resp = self.client.get("/api/v1/admin/billing/transactions")
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
