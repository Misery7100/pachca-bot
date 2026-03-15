"""Generic webhook Bearer token verification."""

from __future__ import annotations

import hmac


def verify_bearer_token(authorization_header: str, secret: str) -> bool:
    """Verify ``X-Authorization: Bearer <token>`` header."""
    if not authorization_header or not secret:
        return False

    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False

    return hmac.compare_digest(parts[1], secret)
