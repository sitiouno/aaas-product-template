"""pytest configuration — set minimum required env vars for tests."""
import os

os.environ.setdefault("APP_SESSION_SECRET", "test-session-secret")
os.environ.setdefault("PRODUCT_ENABLE_DEV_AUTH", "true")
