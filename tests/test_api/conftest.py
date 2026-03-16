"""Shared fixtures for Django Ninja API tests."""

import pytest
from django.test import Client

from apps.accounts.auth import create_access_token
from apps.accounts.models import User
from apps.common.rate_limit import _request_log


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear rate limit state between tests."""
    _request_log.clear()
    yield
    _request_log.clear()


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def test_user(db):
    """Create a regular test user."""
    user = User.objects.create_user(username="testuser", password="testpass123")
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin test user."""
    user = User.objects.create_user(
        username="admin", password="adminpass123", is_staff=True
    )
    return user


@pytest.fixture
def auth_headers(test_user):
    """Authorization headers for the test user."""
    token = create_access_token(test_user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user):
    """Authorization headers for the admin user."""
    token = create_access_token(admin_user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def test_story(db):
    """Create a test story."""
    from apps.stories.models import Story

    return Story.objects.create(
        title="Test Horror Story",
        author="test_author",
        reddit_url="https://www.reddit.com/r/nosleep/comments/abc123/test_story",
        text_content="It was a dark and stormy night. The shadows crept closer.",
        narration_text="It was a dark and stormy night. The shadows crept closer.",
        content_hash="abc123hash",
        part_count=1,
    )
