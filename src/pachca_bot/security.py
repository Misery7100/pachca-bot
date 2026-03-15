"""Webhook signature verification and authorization helpers."""

from __future__ import annotations

import hashlib
import hmac


def verify_github_signature(signature_header: str, body: bytes, secret: str) -> bool:
    """Verify GitHub HMAC-SHA256 webhook signature.

    GitHub sends ``X-Hub-Signature-256: sha256=<hex-digest>``.
    """
    if not signature_header or not secret:
        return False

    expected = (
        "sha256="
        + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(signature_header, expected)


def verify_bearer_token(authorization_header: str, secret: str) -> bool:
    """Verify ``Authorization: Bearer <token>`` header."""
    if not authorization_header or not secret:
        return False

    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False

    return hmac.compare_digest(parts[1], secret)
