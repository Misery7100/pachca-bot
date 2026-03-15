"""GitHub webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac


def verify_signature(signature_header: str, body: bytes, secret: str) -> bool:
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
