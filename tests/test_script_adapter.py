"""Tests for the Claude script-generation adapter, focusing on JSON parsing
robustness and truncation recovery."""

import json
import types
import pytest
from unittest.mock import MagicMock, patch, call

from app.services.script_adapter import (
    generate_script,
    _adapt_section,
    _adapt_long_story,
    _split_for_adaptation,
    _TruncatedResponseError,
    MAX_OUTPUT_TOKENS,
)
from app.schemas.narration import NarrationScript


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_script_json(title="Test", extra_segments=0):
    """Return a valid NarrationScript JSON string."""
    segments = [
        {"type": "narration", "character": "narrator", "text": "It was dark.", "tone": "ominous"},
    ]
    for i in range(extra_segments):
        segments.append(
            {"type": "narration", "character": "narrator", "text": f"Line {i}.", "tone": "flat"}
        )
    return json.dumps({
        "title": title,
        "characters": {
            "narrator": {"voice_profile": "deep, steady, ominous"},
        },
        "segments": segments,
    })


def _mock_response(text, stop_reason="end_turn"):
    """Build a minimal mock of an Anthropic Messages response."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = stop_reason
    return resp


# ---------------------------------------------------------------------------
# MAX_OUTPUT_TOKENS increased
# ---------------------------------------------------------------------------

class TestTokenLimit:
    def test_max_output_tokens_is_at_least_16k(self):
        assert MAX_OUTPUT_TOKENS >= 16_384


# ---------------------------------------------------------------------------
# _adapt_section: truncation detection
# ---------------------------------------------------------------------------

class TestAdaptSectionTruncation:

    @patch("app.services.script_adapter.Anthropic")
    def test_raises_on_max_tokens_stop_reason(self, _mock_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            '{"title": "incomplete...', stop_reason="max_tokens"
        )
        with pytest.raises(_TruncatedResponseError):
            _adapt_section(client, "My Story", "Some text")

    @patch("app.services.script_adapter.Anthropic")
    def test_parses_valid_json_on_end_turn(self, _mock_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            _make_script_json("Good Story"), stop_reason="end_turn"
        )
        result = _adapt_section(client, "Good Story", "Some text")
        assert isinstance(result, NarrationScript)
        assert result.title == "Good Story"

    @patch("app.services.script_adapter.Anthropic")
    def test_strips_markdown_fences(self, _mock_cls):
        client = MagicMock()
        fenced = "```json\n" + _make_script_json("Fenced") + "\n```"
        client.messages.create.return_value = _mock_response(
            fenced, stop_reason="end_turn"
        )
        result = _adapt_section(client, "Fenced", "Some text")
        assert result.title == "Fenced"

    @patch("app.services.script_adapter.Anthropic")
    def test_raises_value_error_on_bad_json(self, _mock_cls):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            "this is not json at all", stop_reason="end_turn"
        )
        with pytest.raises(ValueError, match="Claude did not return valid JSON"):
            _adapt_section(client, "Bad", "text")


# ---------------------------------------------------------------------------
# generate_script: single-section truncation fallback
# ---------------------------------------------------------------------------

class TestGenerateScriptTruncationRecovery:

    @patch("app.services.script_adapter.Anthropic")
    def test_single_section_truncation_triggers_resplit(self, mock_cls):
        """When a single-section story truncates, generate_script should
        re-split into smaller pieces and process via _adapt_long_story."""
        client = MagicMock()
        mock_cls.return_value = client

        good_json = _make_script_json("Recovered")

        good = _mock_response(good_json, stop_reason="end_turn")

        # First call truncates; the re-split at max_chars=6000 will
        # produce 3 sections (each ~3000 chars), so we need 3 good
        # responses after the initial truncated one.
        client.messages.create.side_effect = [
            _mock_response("truncated...", stop_reason="max_tokens"),
            good, good, good,
        ]

        # Use text with paragraph breaks so _split_for_adaptation can
        # split at max_chars=6000.
        text = ("A" * 3000 + "\n\n" + "B" * 3000 + "\n\n" + "C" * 3000)
        result = generate_script("Recovered", text)

        assert isinstance(result, NarrationScript)
        # The first call should have been the truncated single-section attempt,
        # followed by calls for the re-split sections.
        assert client.messages.create.call_count >= 2

    @patch("app.services.script_adapter.Anthropic")
    def test_short_text_succeeds_without_split(self, mock_cls):
        """Short stories that fit in one section should work normally."""
        client = MagicMock()
        mock_cls.return_value = client
        client.messages.create.return_value = _mock_response(
            _make_script_json("Short"), stop_reason="end_turn"
        )

        result = generate_script("Short", "A short story.")
        assert result.title == "Short"
        assert client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# _adapt_long_story: per-section truncation recovery
# ---------------------------------------------------------------------------

class TestAdaptLongStoryTruncation:

    @patch("app.services.script_adapter.Anthropic")
    def test_splits_truncated_section_and_retries(self, _mock_cls):
        """If a section in a multi-section story truncates, it should be
        split and the halves retried."""
        client = MagicMock()

        good_json = _make_script_json("Multi")

        # Section 1 succeeds, section 2 truncates, then its halves succeed.
        client.messages.create.side_effect = [
            _mock_response(good_json, stop_reason="end_turn"),       # section 1
            _mock_response("trunc...", stop_reason="max_tokens"),    # section 2 — truncated
            _mock_response(good_json, stop_reason="end_turn"),       # section 2a
            _mock_response(good_json, stop_reason="end_turn"),       # section 2b
        ]

        sections = [
            "First section content.",
            "A" * 3000 + "\n\n" + "B" * 3000,  # long enough to split
        ]

        result = _adapt_long_story(client, "Multi", sections)
        assert isinstance(result, NarrationScript)
        # 1 (success) + 1 (truncated) + 2 (retried halves) = 4 calls
        assert client.messages.create.call_count == 4

    @patch("app.services.script_adapter.Anthropic")
    def test_safety_limit_prevents_infinite_splitting(self, _mock_cls):
        """If every attempt truncates, it should eventually hit the safety limit."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            "always truncated", stop_reason="max_tokens"
        )

        # Use text with lots of paragraph breaks so splitting always produces > 1 piece
        sections = ["Para one.\n\nPara two.\n\nPara three."]

        with pytest.raises(ValueError, match="too many sections"):
            _adapt_long_story(client, "Infinite", sections)


# ---------------------------------------------------------------------------
# _split_for_adaptation
# ---------------------------------------------------------------------------

class TestSplitForAdaptation:

    def test_short_text_returns_single_section(self):
        assert _split_for_adaptation("Hello world", max_chars=100) == ["Hello world"]

    def test_splits_on_paragraph_boundaries(self):
        text = "Para one.\n\nPara two.\n\nPara three."
        sections = _split_for_adaptation(text, max_chars=20)
        assert len(sections) >= 2
        # All original content should be preserved
        rejoined = "\n\n".join(sections)
        assert "Para one." in rejoined
        assert "Para three." in rejoined

    def test_respects_max_chars(self):
        text = "\n\n".join(f"Paragraph {i} content here." for i in range(20))
        sections = _split_for_adaptation(text, max_chars=100)
        for section in sections:
            # Each section should be at or below the limit (individual
            # paragraphs that exceed the limit are kept as-is).
            assert len(section) <= 100 or "\n\n" not in section

    def test_single_giant_paragraph_returns_as_is(self):
        """A single paragraph exceeding max_chars can't be split further."""
        giant = "A" * 50000
        sections = _split_for_adaptation(giant, max_chars=10000)
        assert sections == [giant]

    def test_splits_on_part_boundaries_first(self):
        """Multi-part stories are split on part delimiters before character limits."""
        text = "Part one content.\n\n---\n\nPart two content.\n\n---\n\nPart three content."
        sections = _split_for_adaptation(text, max_chars=50000)
        assert len(sections) == 3
        assert sections[0] == "Part one content."
        assert sections[1] == "Part two content."
        assert sections[2] == "Part three content."

    def test_short_multipart_not_merged(self):
        """Even when total text is under max_chars, part boundaries are respected."""
        text = "Short A.\n\n---\n\nShort B."
        sections = _split_for_adaptation(text, max_chars=50000)
        assert len(sections) == 2
        assert sections[0] == "Short A."
        assert sections[1] == "Short B."

    def test_long_part_further_split(self):
        """A single part exceeding max_chars is further split by paragraph."""
        long_part = "Para one.\n\nPara two.\n\nPara three."
        text = f"Short part.\n\n---\n\n{long_part}"
        sections = _split_for_adaptation(text, max_chars=20)
        # First section is the short part, remaining sections come from the long part
        assert sections[0] == "Short part."
        assert len(sections) >= 3
        rejoined = "\n\n".join(sections[1:])
        assert "Para one." in rejoined
        assert "Para three." in rejoined

    def test_empty_parts_skipped(self):
        """Empty parts between delimiters are ignored."""
        text = "Content.\n\n---\n\n\n\n---\n\nMore content."
        sections = _split_for_adaptation(text, max_chars=50000)
        assert len(sections) == 2
        assert sections[0] == "Content."
        assert sections[1] == "More content."
