"""Tests for voice notes API, voice preview, and settings Voice Library tab."""

import json
from unittest.mock import patch


def _auth_cookie(auth_headers: dict) -> dict:
    """Extract the token from auth headers and return it as a cookie dict."""
    token = auth_headers["Authorization"].replace("Bearer ", "")
    return {"auth_token": token}


class TestVoiceNotes:
    def test_get_voice_notes_empty(self, client, auth_headers, db_session):
        resp = client.get("/settings/voice-notes", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_put_voice_notes(self, client, auth_headers, db_session):
        # Use a real voice_id from the pool (Adam)
        resp = client.put("/settings/voice-notes", json={
            "pNInz6obpgDQGcFmaJgB": "Great horror narrator",
        }, headers=auth_headers)
        assert resp.status_code == 200
        notes = resp.json()["notes"]
        assert notes["pNInz6obpgDQGcFmaJgB"] == "Great horror narrator"

    def test_put_voice_notes_persists(self, client, auth_headers, db_session):
        client.put("/settings/voice-notes", json={
            "pNInz6obpgDQGcFmaJgB": "Deep and authoritative",
        }, headers=auth_headers)

        resp = client.get("/settings/voice-notes", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["pNInz6obpgDQGcFmaJgB"] == "Deep and authoritative"

    def test_put_voice_notes_merges(self, client, auth_headers, db_session):
        # Set first note
        client.put("/settings/voice-notes", json={
            "pNInz6obpgDQGcFmaJgB": "Adam note",
        }, headers=auth_headers)

        # Set second note — first should still exist
        resp = client.put("/settings/voice-notes", json={
            "21m00Tcm4TlvDq8ikWAM": "Rachel note",
        }, headers=auth_headers)
        notes = resp.json()["notes"]
        assert notes["pNInz6obpgDQGcFmaJgB"] == "Adam note"
        assert notes["21m00Tcm4TlvDq8ikWAM"] == "Rachel note"

    def test_put_empty_note_removes(self, client, auth_headers, db_session):
        # Set a note
        client.put("/settings/voice-notes", json={
            "pNInz6obpgDQGcFmaJgB": "Some note",
        }, headers=auth_headers)

        # Clear the note with empty string
        resp = client.put("/settings/voice-notes", json={
            "pNInz6obpgDQGcFmaJgB": "",
        }, headers=auth_headers)
        assert "pNInz6obpgDQGcFmaJgB" not in resp.json()["notes"]

    def test_put_ignores_invalid_voice_id(self, client, auth_headers, db_session):
        resp = client.put("/settings/voice-notes", json={
            "invalid_voice_id": "Should be ignored",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "invalid_voice_id" not in resp.json()["notes"]

    def test_put_ignores_non_string_notes(self, client, auth_headers, db_session):
        resp = client.put("/settings/voice-notes", json={
            "pNInz6obpgDQGcFmaJgB": 12345,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "pNInz6obpgDQGcFmaJgB" not in resp.json()["notes"]

    def test_voice_notes_requires_auth(self, client, db_session):
        resp = client.get("/settings/voice-notes")
        assert resp.status_code == 401

        resp = client.put("/settings/voice-notes", json={})
        assert resp.status_code == 401


class TestVoicePreview:
    @patch("app.routers.settings.generate_voice_preview")
    def test_returns_audio_file(self, mock_preview, client, auth_headers, tmp_path, db_session):
        # Create a fake mp3 file
        fake_mp3 = tmp_path / "preview.mp3"
        fake_mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
        mock_preview.return_value = str(fake_mp3)

        resp = client.get(
            "/settings/voice-preview/pNInz6obpgDQGcFmaJgB",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"
        mock_preview.assert_called_once_with("pNInz6obpgDQGcFmaJgB")

    def test_returns_404_for_invalid_voice(self, client, auth_headers, db_session):
        resp = client.get(
            "/settings/voice-preview/invalid_voice_id",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @patch("app.routers.settings.generate_voice_preview")
    def test_returns_502_on_elevenlabs_error(self, mock_preview, client, auth_headers, db_session):
        from app.services.elevenlabs import ElevenLabsError
        mock_preview.side_effect = ElevenLabsError("API failed", status_code=500)

        resp = client.get(
            "/settings/voice-preview/pNInz6obpgDQGcFmaJgB",
            headers=auth_headers,
        )
        assert resp.status_code == 502

    def test_requires_auth(self, client, db_session):
        resp = client.get("/settings/voice-preview/pNInz6obpgDQGcFmaJgB")
        assert resp.status_code == 401


class TestSettingsPageVoiceTab:
    def test_renders_voice_library_tab(self, client, auth_headers, db_session):
        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Voice Library" in resp.text
        assert "tab-voices" in resp.text
        assert "voicePoolData" in resp.text

    def test_voice_pool_json_includes_notes(self, client, auth_headers, db_session):
        # Set a note first
        client.put("/settings/voice-notes", json={
            "pNInz6obpgDQGcFmaJgB": "Best narrator voice",
        }, headers=auth_headers)

        resp = client.get("/settings/", headers=auth_headers, cookies=_auth_cookie(auth_headers))
        assert resp.status_code == 200
        assert "Best narrator voice" in resp.text
