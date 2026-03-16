"""Shared fixtures for the Django test suite.

Provides:
- A Django test client with rate limiter auto-cleared
- User fixtures (regular + admin) using Django ORM
- Auth header fixtures for JWT-authenticated requests
- Sample story fixture
"""

import json

import pytest
from django.test import Client

from apps.accounts.auth import create_access_token
from apps.accounts.models import User
from apps.core.rate_limit import _request_log
from apps.stories.models import Story
from apps.stories.services.hashing import hash_content


@pytest.fixture()
def api_client():
    """Django test client with rate limiter cleared."""
    _request_log.clear()
    return Client()


@pytest.fixture()
def test_user(db):
    """Create a regular (non-admin) user and return it."""
    user = User.objects.create_user(username="testuser", password="testpass123")
    return user


@pytest.fixture()
def admin_user(db):
    """Create an admin user and return it."""
    user = User.objects.create_user(username="admin", password="adminpass")
    user.is_admin = True
    user.save()
    return user


@pytest.fixture()
def auth_headers(test_user):
    """Return Authorization headers dict for the test user."""
    token = create_access_token(test_user.id, test_user.username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(admin_user):
    """Return Authorization headers dict for the admin user."""
    token = create_access_token(admin_user.id, admin_user.username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_story(db):
    """Create a sample story in the test database."""
    text = "I moved into an old house last week. Strange things started happening immediately."
    return Story.objects.create(
        title="The Haunted House",
        reddit_url="https://www.reddit.com/r/nosleep/comments/abc123/the_haunted_house/",
        text_content=text,
        narration_text=text,
        content_hash=hash_content(text),
        part_count=1,
    )


def post_json(client, path, data, **extra):
    """Helper: POST JSON to a Django test client endpoint."""
    return client.post(
        path,
        data=json.dumps(data),
        content_type="application/json",
        **extra,
    )


def put_json(client, path, data, **extra):
    """Helper: PUT JSON to a Django test client endpoint."""
    return client.put(
        path,
        data=json.dumps(data),
        content_type="application/json",
        **extra,
    )
