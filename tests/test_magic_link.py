# tests/test_magic_link.py
from product_app.magic_link import generate_magic_token, verify_magic_token


def test_generate_and_verify_magic_token():
    secret = "test-secret-key"
    token = generate_magic_token("user@test.com", secret, expiry_minutes=15)
    assert token is not None
    email = verify_magic_token(token, secret)
    assert email == "user@test.com"


def test_expired_token():
    secret = "test-secret-key"
    token = generate_magic_token("user@test.com", secret, expiry_minutes=-1)
    result = verify_magic_token(token, secret)
    assert result is None


def test_invalid_token():
    result = verify_magic_token("garbage-token", "test-secret")
    assert result is None


def test_wrong_secret():
    token = generate_magic_token("user@test.com", "secret-1", expiry_minutes=15)
    result = verify_magic_token(token, "secret-2")
    assert result is None


def test_email_case_insensitive():
    token = generate_magic_token("User@Test.COM", "secret", expiry_minutes=15)
    email = verify_magic_token(token, "secret")
    assert email == "user@test.com"
