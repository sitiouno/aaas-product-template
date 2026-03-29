"""Tests for new Settings fields: product identity and protection env vars."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch


class TestProductNameDefault(unittest.TestCase):
    def test_product_name_defaults_to_my_product(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env.pop("PRODUCT_NAME", None)
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertEqual(settings.product_name, "My Product")

    def test_product_name_reads_from_env(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env["PRODUCT_NAME"] = "Acme Research"
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertEqual(settings.product_name, "Acme Research")


class TestUnlockProtected(unittest.TestCase):
    def test_unlock_protected_defaults_to_false(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env.pop("UNLOCK_PROTECTED", None)
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertFalse(settings.unlock_protected)

    def test_unlock_protected_reads_true_from_env(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env["UNLOCK_PROTECTED"] = "true"
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertTrue(settings.unlock_protected)


class TestProductDescription(unittest.TestCase):
    def test_product_description_defaults_to_empty(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env.pop("PRODUCT_DESCRIPTION", None)
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertEqual(settings.product_description, "")

    def test_product_description_reads_from_env(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env["PRODUCT_DESCRIPTION"] = "Weather service"
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertEqual(settings.product_description, "Weather service")


class TestProductDomain(unittest.TestCase):
    def test_product_domain_defaults_to_empty(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env.pop("PRODUCT_DOMAIN", None)
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertEqual(settings.product_domain, "")

    def test_product_domain_reads_from_env(self) -> None:
        env = {k: v for k, v in os.environ.items()}
        env["PRODUCT_DOMAIN"] = "weather.x53.ai"
        env.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
        env.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        with patch.dict(os.environ, env, clear=True):
            from product_app.config import load_settings
            settings = load_settings()
        self.assertEqual(settings.product_domain, "weather.x53.ai")


if __name__ == "__main__":
    unittest.main()
