"""Shared fixtures for the test suite.

Provides:
- An in-memory SQLite database that's created fresh per test function
- A FastAPI TestClient with the test DB wired in
- Helper fixtures for creating users and generating auth tokens
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models.story import User, Story, PlaybackState
from app.auth import hash_password, create_access_token
from app.rate_limit import _request_log


@pytest.fixture()
def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with the test database injected."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    _request_log.clear()  # reset rate limiter between tests
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session):
    """Create a regular (non-admin) user and return it."""
    user = User(
        username="testuser",
        password_hash=hash_password("testpass123"),
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session):
    """Create an admin user and return it."""
    user = User(
        username="admin",
        password_hash=hash_password("adminpass"),
        is_admin=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user):
    """Return Authorization headers for the test user."""
    token = create_access_token(test_user.id, test_user.username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(admin_user):
    """Return Authorization headers for the admin user."""
    token = create_access_token(admin_user.id, admin_user.username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_story(db_session):
    """Create a sample story in the test database."""
    story = Story(
        title="The Haunted House",
        reddit_url="https://www.reddit.com/r/nosleep/comments/abc123/the_haunted_house/",
        text_content="I moved into an old house last week. Strange things started happening immediately.",
        narration_text="I moved into an old house last week. Strange things started happening immediately.",
        content_hash="abc123def456",
        part_count=1,
    )
    db_session.add(story)
    db_session.commit()
    db_session.refresh(story)
    return story
