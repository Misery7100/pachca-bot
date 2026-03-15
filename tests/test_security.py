"""Tests for signature verification and auth helpers."""

import hashlib
import hmac

from pachca_bot.security import verify_bearer_token, verify_github_signature


class TestGitHubSignature:
    def _sign(self, body: bytes, secret: str) -> str:
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_valid_signature(self):
        body = b'{"action":"opened"}'
        secret = "test-secret"
        sig = self._sign(body, secret)
        assert verify_github_signature(sig, body, secret) is True

    def test_invalid_signature(self):
        body = b'{"action":"opened"}'
        assert verify_github_signature("sha256=bad", body, "test-secret") is False

    def test_empty_header(self):
        assert verify_github_signature("", b"body", "secret") is False

    def test_empty_secret(self):
        assert verify_github_signature("sha256=abc", b"body", "") is False


class TestBearerToken:
    def test_valid(self):
        assert verify_bearer_token("Bearer my-token", "my-token") is True

    def test_wrong_token(self):
        assert verify_bearer_token("Bearer wrong", "my-token") is False

    def test_no_bearer_prefix(self):
        assert verify_bearer_token("my-token", "my-token") is False

    def test_empty(self):
        assert verify_bearer_token("", "secret") is False

    def test_empty_secret(self):
        assert verify_bearer_token("Bearer tok", "") is False
