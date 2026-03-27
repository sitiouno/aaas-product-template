from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from product_app.webhooks import sign_payload, build_webhook_payload


class WebhookSigningTest(unittest.TestCase):
    def test_sign_payload_produces_valid_hmac(self) -> None:
        body = json.dumps({"event": "run.completed", "job_id": "abc123"})
        secret = "test-webhook-secret"

        signature = sign_payload(body, secret)

        expected = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(signature, expected)

    def test_build_webhook_payload(self) -> None:
        payload = build_webhook_payload(
            event="run.completed",
            job_id="job-1",
            research_style="deploy_product",
            status="completed",
            credits_consumed=3,
            language="en",
            artifacts=[{"name": "report.html", "mime_type": "text/html", "url": "/api/v1/runs/job-1/artifacts/report.html"}],
        )

        self.assertEqual(payload["event"], "run.completed")
        self.assertEqual(payload["job_id"], "job-1")
        self.assertEqual(payload["research_style"], "deploy_product")
        self.assertIn("completed_at", payload)

    def test_sign_payload_deterministic(self) -> None:
        body = '{"test": true}'
        secret = "secret"
        sig1 = sign_payload(body, secret)
        sig2 = sign_payload(body, secret)
        self.assertEqual(sig1, sig2)


if __name__ == "__main__":
    unittest.main()
