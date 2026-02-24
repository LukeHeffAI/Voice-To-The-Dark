"""Smoke tests for the HTML page endpoints (player router)."""

from app.models.story import Story


class TestStoryListPage:
    def test_renders_empty(self, client, db_session):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Voice To The Dark" in resp.text


class TestSubmitPage:
    def test_renders(self, client, db_session):
        resp = client.get("/submit")
        assert resp.status_code == 200
        assert "Submit" in resp.text


class TestStoryDetailPage:
    def test_renders_with_story(self, client, sample_story, db_session):
        resp = client.get(f"/story/{sample_story.id}")
        assert resp.status_code == 200
        assert sample_story.title in resp.text

    def test_404_for_missing_story(self, client, db_session):
        resp = client.get("/story/9999")
        assert resp.status_code == 404

    def test_renders_when_narration_text_is_none(self, client, db_session):
        """Regression test for the template None-length bug."""
        story = Story(
            title="Null Narration Story",
            reddit_url="https://www.reddit.com/r/nosleep/comments/null/test/",
            text_content="Some raw text here.",
            narration_text=None,
            content_hash="nullhash123",
            part_count=1,
        )
        db_session.add(story)
        db_session.commit()
        db_session.refresh(story)

        resp = client.get(f"/story/{story.id}")
        assert resp.status_code == 200
        assert "0 characters" in resp.text
