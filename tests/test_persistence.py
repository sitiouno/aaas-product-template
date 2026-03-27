from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from product_app.database import dispose_database, initialize_database, session_scope
from product_app.models import (
    AccessRequest,
    AnalysisArtifact,
    AnalysisRun,
    AnalysisSection,
    ApiKey,
    CreditTransaction,
    User,
)


class PersistenceTest(unittest.TestCase):
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

    # ── Model-level tests (kept from previous) ──────────────────────

    def test_create_user_directly(self) -> None:
        """User is created without Organization."""
        with session_scope() as s:
            user = User(email="test@example.com", full_name="Test User", status="approved", is_admin=False)
            s.add(user)
            s.flush()
            assert user.id is not None
            assert user.email == "test@example.com"

    def test_create_access_request(self) -> None:
        """Pre-signup creates an access request."""
        with session_scope() as s:
            req = AccessRequest(email="new@example.com", full_name="New User", company="Acme Inc", message="Want API access")
            s.add(req)
            s.flush()
            assert req.status == "pending"

    def test_credit_transaction_with_api_key_tracking(self) -> None:
        """Credit transaction tracks which API key consumed credits."""
        with session_scope() as s:
            user = User(email="test@example.com", status="approved")
            s.add(user)
            s.flush()
            tx = CreditTransaction(user_id=user.id, amount=-2, balance_after=8, source_type="run_consumption", estimated_cost_usd=0.45, api_key_id=None)
            s.add(tx)
            s.flush()
            assert tx.estimated_cost_usd == 0.45

    def test_analysis_run_with_research_style(self) -> None:
        """AnalysisRun uses research_style instead of old mode/research_mode/research_intent."""
        with session_scope() as s:
            user = User(email="runner@example.com", status="approved")
            s.add(user)
            s.flush()
            run = AnalysisRun(
                public_job_id="job-test-1",
                user_id=user.id,
                prompt="Analyze https://example.com",
                research_style="deploy_product",
                status="queued",
            )
            s.add(run)
            s.flush()
            assert run.id is not None
            assert run.research_style == "deploy_product"
            assert run.webhook_url is None

    def test_api_key_with_user(self) -> None:
        """ApiKey belongs to user directly, not organization."""
        with session_scope() as s:
            user = User(email="dev@example.com", status="approved")
            s.add(user)
            s.flush()
            key = ApiKey(
                user_id=user.id,
                name="My Key",
                key_prefix="sk_test",
                secret_hash="abc123hash",
                scopes="read,write",
                label="Production key",
                rate_limit_rpm=120,
            )
            s.add(key)
            s.flush()
            assert key.label == "Production key"
            assert key.rate_limit_rpm == 120

    def test_analysis_section_body_html(self) -> None:
        """AnalysisSection has body_html column."""
        with session_scope() as s:
            user = User(email="sec@example.com", status="approved")
            s.add(user)
            s.flush()
            run = AnalysisRun(
                public_job_id="job-sec-1",
                user_id=user.id,
                prompt="Test",
                research_style="company_deep_dive",
                status="queued",
            )
            s.add(run)
            s.flush()
            section = AnalysisSection(
                run_id=run.id,
                section_id="intro",
                title="Introduction",
                body_text="Plain text",
                body_html="<p>HTML text</p>",
            )
            s.add(section)
            s.flush()
            assert section.body_html == "<p>HTML text</p>"

    def test_analysis_artifact_size_bytes(self) -> None:
        """AnalysisArtifact has size_bytes column."""
        with session_scope() as s:
            user = User(email="art@example.com", status="approved")
            s.add(user)
            s.flush()
            run = AnalysisRun(
                public_job_id="job-art-1",
                user_id=user.id,
                prompt="Test",
                research_style="osint_360",
                status="queued",
            )
            s.add(run)
            s.flush()
            artifact = AnalysisArtifact(
                run_id=run.id,
                name="report.pdf",
                storage_path="/outputs/report.pdf",
                public_url="/outputs/report.pdf",
                artifact_kind="report_pdf",
                size_bytes=102400,
            )
            s.add(artifact)
            s.flush()
            assert artifact.size_bytes == 102400

    def test_user_defaults(self) -> None:
        """User has correct defaults for status, is_admin, language."""
        with session_scope() as s:
            user = User(email="defaults@example.com")
            s.add(user)
            s.flush()
            assert user.status == "pending"
            assert user.is_admin is False
            assert user.language == "en"

    def test_access_request_review_flow(self) -> None:
        """AccessRequest can be reviewed by an admin user."""
        from product_app.models import utcnow
        with session_scope() as s:
            admin = User(email="admin@example.com", is_admin=True, status="approved")
            s.add(admin)
            s.flush()
            req = AccessRequest(
                email="applicant@example.com",
                full_name="Applicant",
                company="StartupCo",
                message="Please approve",
            )
            s.add(req)
            s.flush()
            assert req.status == "pending"
            req.status = "approved"
            req.reviewed_by = admin.id
            req.reviewed_at = utcnow()
            req.initial_credits = 10
            s.flush()
            assert req.status == "approved"
            assert req.reviewed_by == admin.id
            assert req.initial_credits == 10

    # ── Persistence function tests (Task 3) ─────────────────────────

    def test_get_credit_balance_for_user(self) -> None:
        from product_app.persistence import get_credit_balance, record_credit_transaction
        with session_scope() as s:
            user = User(email="t@t.com", status="approved")
            s.add(user)
            s.flush()
            record_credit_transaction(s, user.id, amount=10, source_type="admin_grant")
            balance = get_credit_balance(s, user.id)
            assert balance == 10

    def test_create_access_request_and_approve(self) -> None:
        from product_app.persistence import (
            approve_access_request,
            create_access_request,
            get_credit_balance,
        )
        with session_scope() as s:
            admin = User(email="admin@test.com", status="approved", is_admin=True)
            s.add(admin)
            s.flush()
            req_id = create_access_request(s, "new@test.com", "New User", "Acme", "Need access")
            req = approve_access_request(s, req_id, reviewed_by_user_id=admin.id, initial_credits=20)
            assert req.status == "approved"
            user = s.query(User).filter_by(email="new@test.com").one()
            assert user.status == "approved"
            balance = get_credit_balance(s, user.id)
            assert balance == 20

    def test_reject_access_request(self) -> None:
        from product_app.persistence import (
            create_access_request,
            reject_access_request,
        )
        with session_scope() as s:
            admin = User(email="admin@test.com", status="approved", is_admin=True)
            s.add(admin)
            s.flush()
            req_id = create_access_request(s, "bad@test.com", "Bad User")
            reject_access_request(s, req_id, admin.id)
            req = s.get(AccessRequest, req_id)
            assert req.status == "rejected"

    def test_dedup_pending_access_request(self) -> None:
        from product_app.persistence import create_access_request
        with session_scope() as s:
            id1 = create_access_request(s, "dup@test.com", "User 1")
            id2 = create_access_request(s, "dup@test.com", "User 1")
            assert id1 == id2  # Same pending request returned

    def test_ensure_user_creates_pending(self) -> None:
        from product_app.persistence import ensure_user
        with session_scope() as s:
            user = ensure_user(s, "new@test.com", "New User")
            assert user.status == "pending"

    def test_ensure_user_returns_existing(self) -> None:
        from product_app.persistence import ensure_user
        with session_scope() as s:
            user1 = ensure_user(s, "existing@test.com", "User")
            user2 = ensure_user(s, "existing@test.com")
            assert user1.id == user2.id

    def test_ensure_user_updates_last_login(self) -> None:
        from product_app.persistence import ensure_user
        with session_scope() as s:
            user1 = ensure_user(s, "login@test.com", "User")
            assert user1.last_login_at is None  # new user
            s.flush()
        with session_scope() as s:
            user2 = ensure_user(s, "login@test.com")
            assert user2.last_login_at is not None

    def test_bootstrap_defaults_creates_admin(self) -> None:
        from product_app.persistence import bootstrap_defaults
        from product_app.config import load_settings
        os.environ["PRODUCT_ADMIN_EMAIL"] = "boss@test.com"
        settings = load_settings()
        with session_scope() as s:
            bootstrap_defaults(s, settings)
            user = s.query(User).filter_by(email="boss@test.com").first()
            assert user is not None
            assert user.is_admin is True
            assert user.status == "approved"

    def test_bootstrap_defaults_no_admin_email(self) -> None:
        from product_app.persistence import bootstrap_defaults
        from product_app.config import load_settings
        os.environ.pop("PRODUCT_ADMIN_EMAIL", None)
        settings = load_settings()
        with session_scope() as s:
            bootstrap_defaults(s, settings)
            # Should not raise, just a no-op
            count = s.query(User).filter_by(is_admin=True).count()
            assert count == 0

    def test_record_credit_transaction_idempotent(self) -> None:
        from product_app.persistence import record_credit_transaction, get_credit_balance
        with session_scope() as s:
            user = User(email="idem@test.com", status="approved")
            s.add(user)
            s.flush()
            tx1 = record_credit_transaction(s, user.id, amount=5, source_type="admin_grant", external_reference="ref-1")
            tx2 = record_credit_transaction(s, user.id, amount=5, source_type="admin_grant", external_reference="ref-1")
            assert tx1.id == tx2.id
            balance = get_credit_balance(s, user.id)
            assert balance == 5  # not 10

    def test_create_run_record(self) -> None:
        from product_app.persistence import create_run_record
        with session_scope() as s:
            user = User(email="runner@test.com", status="approved")
            s.add(user)
            s.flush()
            run = create_run_record(
                s,
                job_id="job-123",
                prompt="Analyze Acme Corp",
                user_id=user.id,
                research_style="deploy_product",
            )
            assert run.public_job_id == "job-123"
            assert run.user_id == user.id
            assert run.research_style == "deploy_product"
            assert run.status == "queued"

    def test_list_recent_runs(self) -> None:
        from product_app.persistence import create_run_record, list_recent_runs
        with session_scope() as s:
            user = User(email="lister@test.com", status="approved")
            s.add(user)
            s.flush()
            create_run_record(s, "job-a", "Prompt A", user_id=user.id)
            create_run_record(s, "job-b", "Prompt B", user_id=user.id)
            runs = list_recent_runs(s, user_id=user.id, limit=10)
            assert len(runs) == 2
            assert runs[0]["job_id"] in ("job-a", "job-b")

    def test_list_recent_runs_filters_by_user(self) -> None:
        from product_app.persistence import create_run_record, list_recent_runs
        with session_scope() as s:
            u1 = User(email="u1@test.com", status="approved")
            u2 = User(email="u2@test.com", status="approved")
            s.add_all([u1, u2])
            s.flush()
            create_run_record(s, "job-u1", "Prompt", user_id=u1.id)
            create_run_record(s, "job-u2", "Prompt", user_id=u2.id)
            runs = list_recent_runs(s, user_id=u1.id)
            assert len(runs) == 1
            assert runs[0]["job_id"] == "job-u1"

    def test_get_daily_usage(self) -> None:
        from product_app.persistence import record_credit_transaction, get_daily_usage
        with session_scope() as s:
            user = User(email="usage@test.com", status="approved")
            s.add(user)
            s.flush()
            record_credit_transaction(s, user.id, amount=-3, source_type="run_consumption", estimated_cost_usd=0.10)
            rows = get_daily_usage(s, user.id)
            assert len(rows) >= 1
            assert rows[0]["credits"] >= 3

    def test_get_usage_by_api_key(self) -> None:
        from product_app.persistence import record_credit_transaction, get_usage_by_api_key
        with session_scope() as s:
            user = User(email="apiusage@test.com", status="approved")
            s.add(user)
            s.flush()
            key = ApiKey(
                user_id=user.id,
                name="Test Key",
                key_prefix="sk_test",
                secret_hash="hash123",
                scopes="read,write",
            )
            s.add(key)
            s.flush()
            record_credit_transaction(s, user.id, amount=-2, source_type="run_consumption", api_key_id=key.id, estimated_cost_usd=0.05)
            rows = get_usage_by_api_key(s, user.id)
            assert len(rows) == 1
            assert rows[0]["api_key_id"] == key.id
            assert rows[0]["credits"] >= 2

    def test_approve_access_request_existing_user(self) -> None:
        """Approving a request when the user already exists updates the user status."""
        from product_app.persistence import (
            approve_access_request,
            create_access_request,
        )
        with session_scope() as s:
            admin = User(email="admin@test.com", status="approved", is_admin=True)
            # Pre-existing user with pending status
            existing = User(email="pre@test.com", status="pending", full_name=None)
            s.add_all([admin, existing])
            s.flush()
            req_id = create_access_request(s, "pre@test.com", "Pre User", "Co")
            approve_access_request(s, req_id, reviewed_by_user_id=admin.id)
            s.flush()
            assert existing.status == "approved"
            assert existing.full_name == "Pre User"

    def test_user_has_stripe_and_onboarding_columns(self) -> None:
        with session_scope() as s:
            user = User(
                email="stripe@corp.com",
                full_name="Stripe User",
                status="approved",
                stripe_customer_id="cus_test123",
                onboarding_completed=False,
            )
            s.add(user)
            s.flush()
            assert user.stripe_customer_id == "cus_test123"
            assert user.onboarding_completed is False

    def test_platform_setting_crud(self) -> None:
        from product_app.models import PlatformSetting
        with session_scope() as s:
            setting = PlatformSetting(key="default_initial_credits", value="10")
            s.add(setting)
            s.flush()
            fetched = s.get(PlatformSetting, "default_initial_credits")
            assert fetched is not None
            assert fetched.value == "10"

    def test_get_platform_setting_default(self) -> None:
        from product_app.persistence import get_platform_setting
        with session_scope() as s:
            val = get_platform_setting(s, "nonexistent", default="42")
            self.assertEqual(val, "42")

    def test_set_and_get_platform_setting(self) -> None:
        from product_app.persistence import get_platform_setting, set_platform_setting
        with session_scope() as s:
            set_platform_setting(s, "default_initial_credits", "20")
        with session_scope() as s:
            val = get_platform_setting(s, "default_initial_credits")
            self.assertEqual(val, "20")

    def test_set_platform_setting_upsert(self) -> None:
        from product_app.persistence import get_platform_setting, set_platform_setting
        with session_scope() as s:
            set_platform_setting(s, "stripe_mode", "test")
        with session_scope() as s:
            set_platform_setting(s, "stripe_mode", "live")
        with session_scope() as s:
            val = get_platform_setting(s, "stripe_mode")
            self.assertEqual(val, "live")

    def test_auto_register_user(self) -> None:
        from product_app.persistence import auto_register_user, get_credit_balance
        with session_scope() as s:
            user = auto_register_user(s, email="new@corp.com", full_name="New User", initial_credits=10)
            self.assertEqual(user.status, "approved")
            self.assertEqual(user.onboarding_completed, False)
            balance = get_credit_balance(s, user.id)
            self.assertEqual(balance, 10)


if __name__ == "__main__":
    unittest.main()
