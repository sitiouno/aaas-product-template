"""tests/test_email_validator.py — Unit tests for the email validator module."""
from __future__ import annotations

import unittest

from product_app.email_validator import is_corporate_email


class TestIsCorporateEmail(unittest.TestCase):
    # ------------------------------------------------------------------
    # Corporate / valid cases
    # ------------------------------------------------------------------

    def test_corporate_email_passes(self) -> None:
        ok, reason = is_corporate_email("jean@sitiouno.com")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_corporate_subdomain_passes(self) -> None:
        ok, reason = is_corporate_email("user@mail.bigcorp.co")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_corporate_multi_part_domain_passes(self) -> None:
        ok, reason = is_corporate_email("alice@research.acme.org")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    # ------------------------------------------------------------------
    # Public consumer domains → "public_domain"
    # ------------------------------------------------------------------

    def test_gmail_rejected(self) -> None:
        ok, reason = is_corporate_email("user@gmail.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "public_domain")

    def test_yahoo_rejected(self) -> None:
        ok, reason = is_corporate_email("user@yahoo.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "public_domain")

    def test_hotmail_rejected(self) -> None:
        ok, reason = is_corporate_email("user@hotmail.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "public_domain")

    def test_outlook_rejected(self) -> None:
        ok, reason = is_corporate_email("user@outlook.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "public_domain")

    def test_protonmail_rejected(self) -> None:
        ok, reason = is_corporate_email("user@protonmail.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "public_domain")

    def test_icloud_rejected(self) -> None:
        ok, reason = is_corporate_email("user@icloud.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "public_domain")

    # ------------------------------------------------------------------
    # Disposable / temporary domains → "disposable_domain"
    # ------------------------------------------------------------------

    def test_mailinator_rejected(self) -> None:
        ok, reason = is_corporate_email("user@mailinator.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")

    def test_guerrillamail_rejected(self) -> None:
        ok, reason = is_corporate_email("user@guerrillamail.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")

    def test_temp_mail_org_rejected(self) -> None:
        ok, reason = is_corporate_email("user@temp-mail.org")
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")

    def test_yopmail_rejected(self) -> None:
        ok, reason = is_corporate_email("user@yopmail.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")

    def test_10minutemail_rejected(self) -> None:
        ok, reason = is_corporate_email("user@10minutemail.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")

    # ------------------------------------------------------------------
    # Invalid format / domain
    # ------------------------------------------------------------------

    def test_no_tld_rejected(self) -> None:
        """user@localhost has no dot in domain → invalid_domain."""
        ok, reason = is_corporate_email("user@localhost")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_domain")

    def test_empty_string_rejected(self) -> None:
        ok, reason = is_corporate_email("")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_format")

    def test_no_at_sign_rejected(self) -> None:
        ok, reason = is_corporate_email("notanemail")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_format")

    def test_missing_local_part_rejected(self) -> None:
        ok, reason = is_corporate_email("@domain.com")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_format")

    def test_missing_domain_rejected(self) -> None:
        ok, reason = is_corporate_email("user@")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_format")

    # ------------------------------------------------------------------
    # Admin bypass
    # ------------------------------------------------------------------

    def test_admin_bypass_gmail(self) -> None:
        """Admin email bypasses the public-domain check."""
        ok, reason = is_corporate_email(
            "admin@gmail.com",
            admin_email="admin@gmail.com",
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_admin_bypass_case_insensitive(self) -> None:
        ok, reason = is_corporate_email(
            "Admin@Gmail.COM",
            admin_email="admin@gmail.com",
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_non_admin_gmail_still_rejected(self) -> None:
        ok, reason = is_corporate_email(
            "other@gmail.com",
            admin_email="admin@gmail.com",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "public_domain")

    # ------------------------------------------------------------------
    # extra_blocked
    # ------------------------------------------------------------------

    def test_extra_blocked_domain_rejected(self) -> None:
        ok, reason = is_corporate_email(
            "user@sketchy-disposable.io",
            extra_blocked={"sketchy-disposable.io"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")

    def test_extra_blocked_case_insensitive(self) -> None:
        ok, reason = is_corporate_email(
            "user@Blocked.IO",
            extra_blocked={"blocked.io"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")

    def test_extra_blocked_does_not_affect_other_domains(self) -> None:
        ok, reason = is_corporate_email(
            "user@legitcorp.com",
            extra_blocked={"blocked.io"},
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_extra_blocked_frozenset(self) -> None:
        ok, reason = is_corporate_email(
            "user@frozenblocked.com",
            extra_blocked=frozenset({"frozenblocked.com"}),
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "disposable_domain")


if __name__ == "__main__":
    unittest.main()
