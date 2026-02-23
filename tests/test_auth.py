"""Unit tests for app.auth (JWT and password hashing)."""

import time
from unittest.mock import patch
from app.auth import hash_password, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        hashed = hash_password("correcthorse")
        assert verify_password("correcthorse", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correcthorse")
        assert verify_password("wronghorse", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt uses random salts, so two hashes of the same password differ."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2
        # But both verify
        assert verify_password("same", h1) is True
        assert verify_password("same", h2) is True


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token(42, "alice")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["username"] == "alice"

    def test_decode_invalid_token(self):
        result = decode_access_token("not.a.valid.token")
        assert result is None

    def test_decode_empty_string(self):
        result = decode_access_token("")
        assert result is None

    def test_token_contains_expiry(self):
        token = create_access_token(1, "bob")
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_expired_token_returns_none(self):
        """Simulate an expired token by patching the expiry to the past."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from app.config import settings

        expired_payload = {
            "sub": "1",
            "username": "expired_user",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        result = decode_access_token(token)
        assert result is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(1, "alice")
        # Flip a character in the token payload
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B") + "." + parts[2]
        result = decode_access_token(tampered)
        assert result is None
