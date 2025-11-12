"""Password hashing and verification helpers for WordBridge."""

from __future__ import annotations

import bcrypt


def hash_password(plaintext: str) -> str:
    """Return a bcrypt hash for the provided password."""
    if not plaintext:
        raise ValueError("Password must be provided.")

    password_bytes = plaintext.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plaintext: str, password_hash: str) -> bool:
    """Verify that the supplied plaintext password matches a stored hash."""
    if not password_hash:
        return False

    try:
        return bcrypt.checkpw(
            plaintext.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        # bcrypt raises ValueError when hashes are invalid or incorrectly formatted.
        return False


