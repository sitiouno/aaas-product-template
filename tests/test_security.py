from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from product_app.database import dispose_database, initialize_database
from product_app.security import (
    authenticate_api_key,
    create_api_key,
    create_session_token,
    parse_session_token,
)


class SecurityHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_env = {key: os.environ.get(key) for key in (
            "DATABASE_URL",
            "DATABASE_SQLITE_PATH",
            "DATABASE_AUTO_CREATE",
            "CLOUD_SQL_INSTANCE_CONNECTION_NAME",
            "APP_SESSION_SECRET",
        )}
        os.environ["DATABASE_URL"] = ""
        os.environ["DATABASE_SQLITE_PATH"] = str(Path(self.tempdir.name) / "security.db")
        os.environ["DATABASE_AUTO_CREATE"] = "true"
        os.environ["CLOUD_SQL_INSTANCE_CONNECTION_NAME"] = ""
        os.environ["APP_SESSION_SECRET"] = "test-secret"
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

    def test_api_key_round_trip(self) -> None:
        from product_app.database import session_scope
        from product_app.models import User

        with session_scope() as s:
            user = User(email="apitest@test.com", full_name="API Test", status="approved", is_admin=False)
            s.add(user)
            s.flush()
            user_id = user.id

        record, raw_key = create_api_key(
            user_id=user_id,
            name="CI key",
        )

        identity = authenticate_api_key(raw_key)

        self.assertIsNotNone(identity)
        self.assertEqual(identity.user_id, user_id)
        self.assertEqual(identity.email, "apitest@test.com")
        self.assertEqual(record.key_prefix, raw_key.split(".", 1)[0])

    def test_session_token_round_trip(self) -> None:
        from product_app.security import Identity

        token = create_session_token(
            Identity(
                email="owner@test.quien",
                user_id="user-1",
                full_name="Owner",
                scopes="runs:read runs:write",
            )
        )

        identity = parse_session_token(token)

        self.assertIsNotNone(identity)
        self.assertEqual(identity.email, "owner@test.quien")
        self.assertEqual(identity.user_id, "user-1")


if __name__ == "__main__":
    unittest.main()
