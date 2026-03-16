"""Unit tests for apps.accounts.auth (JWT authentication)."""

import pytest

from apps.accounts.auth import create_access_token, decode_access_token


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
        from django.conf import settings

        expired_payload = {
            "sub": "1",
            "username": "expired_user",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        result = decode_access_token(token)
        assert result is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(1, "alice")
        # Flip a character in the token payload
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B") + "." + parts[2]
        result = decode_access_token(tampered)
        assert result is None


@pytest.mark.django_db
class TestPasswordHashing:
    """Test Django's password hashing via the User model."""

    def test_password_is_hashed(self):
        from apps.accounts.models import User
        user = User.objects.create_user(username="hashtest", password="mysecret")
        assert user.password != "mysecret"
        assert len(user.password) > 20

    def test_check_correct_password(self):
        from apps.accounts.models import User
        user = User.objects.create_user(username="checktest", password="correcthorse")
        assert user.check_password("correcthorse") is True

    def test_check_wrong_password(self):
        from apps.accounts.models import User
        user = User.objects.create_user(username="wrongtest", password="correcthorse")
        assert user.check_password("wronghorse") is False
