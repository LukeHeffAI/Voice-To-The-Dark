"""Tests for tasks API endpoints."""

import json

import pytest

from apps.tasks.models import BackgroundTask, TaskStatus, TaskType


pytestmark = pytest.mark.django_db


@pytest.fixture
def task_for_user(test_user, test_story):
    """Create a background task for the test user."""
    return BackgroundTask.objects.create(
        user=test_user,
        story=test_story,
        task_type=TaskType.GENERATE_SCRIPT,
        status=TaskStatus.PROCESSING,
        progress_current=3,
        progress_total=10,
        progress_message="Generating segment 3/10",
    )


@pytest.fixture
def other_user(db):
    """Create a different user."""
    from apps.accounts.models import User
    return User.objects.create_user(username="otheruser", password="otherpass123")


@pytest.fixture
def other_user_headers(other_user):
    """Auth headers for the other user."""
    from apps.accounts.auth import create_access_token
    token = create_access_token(other_user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class TestGetTaskStatus:
    def test_get_task_status(self, client, auth_headers, task_for_user):
        resp = client.get(f"/api/tasks/status/{task_for_user.id}", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task_for_user.id
        assert data["status"] == "processing"
        assert data["progress_current"] == 3
        assert data["progress_total"] == 10
        assert data["progress_message"] == "Generating segment 3/10"

    def test_get_task_status_not_found(self, client, auth_headers):
        resp = client.get("/api/tasks/status/9999", **auth_headers)
        assert resp.status_code == 404

    def test_get_task_status_user_isolation(self, client, other_user_headers, task_for_user):
        """Users can only see their own tasks."""
        resp = client.get(f"/api/tasks/status/{task_for_user.id}", **other_user_headers)
        assert resp.status_code == 404

    def test_get_task_status_unauthenticated(self, client, task_for_user):
        resp = client.get(f"/api/tasks/status/{task_for_user.id}")
        assert resp.status_code == 401

    def test_get_completed_task_with_result(self, client, auth_headers, test_user, test_story):
        task = BackgroundTask.objects.create(
            user=test_user,
            story=test_story,
            task_type=TaskType.GENERATE_SCRIPT,
            status=TaskStatus.COMPLETE,
            result_data={"message": "Script generated!", "characters": ["Narrator"]},
        )
        resp = client.get(f"/api/tasks/status/{task.id}", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["result_data"]["message"] == "Script generated!"

    def test_get_failed_task_with_error(self, client, auth_headers, test_user, test_story):
        task = BackgroundTask.objects.create(
            user=test_user,
            story=test_story,
            task_type=TaskType.GENERATE_NARRATION,
            status=TaskStatus.FAILED,
            error_message="ElevenLabs API error",
        )
        resp = client.get(f"/api/tasks/status/{task.id}", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "ElevenLabs API error"


class TestGetStoryTasks:
    def test_get_active_tasks(self, client, auth_headers, task_for_user, test_story):
        resp = client.get(f"/api/tasks/story/{test_story.id}", **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["task_id"] == task_for_user.id

    def test_excludes_completed_tasks(self, client, auth_headers, test_user, test_story):
        BackgroundTask.objects.create(
            user=test_user,
            story=test_story,
            task_type=TaskType.GENERATE_SCRIPT,
            status=TaskStatus.COMPLETE,
        )
        resp = client.get(f"/api/tasks/story/{test_story.id}", **auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_excludes_failed_tasks(self, client, auth_headers, test_user, test_story):
        BackgroundTask.objects.create(
            user=test_user,
            story=test_story,
            task_type=TaskType.GENERATE_SCRIPT,
            status=TaskStatus.FAILED,
        )
        resp = client.get(f"/api/tasks/story/{test_story.id}", **auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_isolation(self, client, other_user_headers, task_for_user, test_story):
        resp = client.get(f"/api/tasks/story/{test_story.id}", **other_user_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0
