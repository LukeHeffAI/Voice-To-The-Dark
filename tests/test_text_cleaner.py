"""Unit tests for app.services.text_cleaner."""

from app.services.text_cleaner import clean_for_narration


class TestNavigationRemoval:
    def test_removes_part_links(self):
        text = "[Part 1](https://reddit.com/abc) | [Part 2](https://reddit.com/def)\nActual story text."
        result = clean_for_narration(text)
        assert "Part 1" not in result
        assert "Part 2" not in result
        assert "Actual story text." in result

    def test_removes_previous_next_links(self):
        text = "Story paragraph.\n[Previous](https://reddit.com/a) | [Next](https://reddit.com/b)\nMore story."
        result = clean_for_narration(text)
        assert "Previous" not in result
        assert "Next" not in result
        assert "Story paragraph." in result
        assert "More story." in result

    def test_removes_bare_reddit_urls(self):
        text = "Story text.\nhttps://www.reddit.com/r/nosleep/comments/abc123/title/\nMore text."
        result = clean_for_narration(text)
        assert "reddit.com" not in result
        assert "Story text." in result

    def test_removes_next_colon_url(self):
        text = "End of part.\nNext: https://reddit.com/r/nosleep/comments/xyz"
        result = clean_for_narration(text)
        assert "Next:" not in result


class TestMetaLineRemoval:
    def test_removes_edit_notes(self):
        text = "Story text.\nEdit: Fixed some typos.\nMore story."
        result = clean_for_narration(text)
        assert "Edit:" not in result
        assert "Fixed some typos" not in result

    def test_removes_update_notes(self):
        text = "Update 2: Added more details.\nThe actual story continues."
        result = clean_for_narration(text)
        assert "Update 2:" not in result
        assert "The actual story continues." in result

    def test_removes_trigger_warnings(self):
        text = "TW: Gore, violence\nThe story starts here."
        result = clean_for_narration(text)
        assert "TW:" not in result
        assert "The story starts here." in result

    def test_removes_tldr(self):
        text = "Long story.\nTL;DR: It was scary."
        result = clean_for_narration(text)
        assert "TL;DR" not in result

    def test_removes_formatting_apologies(self):
        text = "Sorry for formatting, I'm on mobile.\nThe house was old and decrepit."
        result = clean_for_narration(text)
        assert "Sorry for" not in result
        assert "The house was old and decrepit." in result

    def test_removes_throwaway_disclaimers(self):
        text = "Using a throwaway account for obvious reasons.\nI need to tell someone what happened."
        result = clean_for_narration(text)
        assert "throwaway" not in result
        assert "I need to tell someone" in result


class TestMarkdownConversion:
    def test_strips_bold(self):
        text = "This is **very important** text."
        result = clean_for_narration(text)
        assert result == "This is very important text."

    def test_strips_italic(self):
        text = "She whispered *quietly* in the dark."
        result = clean_for_narration(text)
        assert result == "She whispered quietly in the dark."

    def test_strips_bold_italic(self):
        text = "***Something terrible*** happened."
        result = clean_for_narration(text)
        assert result == "Something terrible happened."

    def test_strips_strikethrough(self):
        text = "He was ~~dead~~ alive."
        result = clean_for_narration(text)
        assert result == "He was dead alive."

    def test_strips_heading_markers(self):
        text = "## Chapter One\nThe night was dark."
        result = clean_for_narration(text)
        assert "##" not in result
        assert "Chapter One" in result

    def test_strips_horizontal_rules(self):
        text = "First part.\n---\nSecond part."
        result = clean_for_narration(text)
        assert "---" not in result
        assert "First part." in result
        assert "Second part." in result

    def test_converts_links_to_text(self):
        text = "I found [this article](https://example.com) interesting."
        result = clean_for_narration(text)
        assert "this article" in result
        assert "https://example.com" not in result
        assert "[" not in result

    def test_removes_bare_urls(self):
        text = "Check this: https://example.com/something for more info."
        result = clean_for_narration(text)
        assert "https://" not in result

    def test_strips_block_quotes(self):
        text = "> He said something ominous.\nThen he left."
        result = clean_for_narration(text)
        assert ">" not in result
        assert "He said something ominous." in result

    def test_strips_inline_code(self):
        text = "The file was named `manifest.json` on the desktop."
        result = clean_for_narration(text)
        assert "`" not in result
        assert "manifest.json" in result

    def test_removes_code_blocks(self):
        text = "Before.\n```\nsome code\n```\nAfter."
        result = clean_for_narration(text)
        assert "some code" not in result
        assert "Before." in result
        assert "After." in result

    def test_converts_html_entities(self):
        text = "Tom &amp; Jerry were scared. 5 &gt; 3."
        result = clean_for_narration(text)
        assert "Tom & Jerry" in result
        assert "5 > 3" in result

    def test_removes_zero_width_spaces(self):
        text = "Hello&#x200B;World"
        result = clean_for_narration(text)
        assert "HelloWorld" in result

    def test_strips_escaped_markdown(self):
        text = r"She said \*hello\* nervously."
        result = clean_for_narration(text)
        assert "\\" not in result
        # After un-escaping \* → *, the italic regex further strips them
        assert "hello" in result
        assert "nervously" in result


class TestWhitespaceCleaning:
    def test_collapses_multiple_blank_lines(self):
        text = "Paragraph one.\n\n\n\n\nParagraph two."
        result = clean_for_narration(text)
        assert "\n\n\n" not in result
        assert "Paragraph one.\n\nParagraph two." == result

    def test_strips_trailing_whitespace(self):
        text = "Line one.   \nLine two.  "
        result = clean_for_narration(text)
        assert "   " not in result

    def test_strips_leading_whitespace(self):
        text = "   Indented line.\n    Another indented line."
        result = clean_for_narration(text)
        assert result.startswith("Indented line.")
        assert "\n" in result
        assert "Another indented line." in result


class TestFullPipeline:
    def test_complex_reddit_post(self):
        """Test cleaning a realistic Reddit nosleep post with multiple artifacts."""
        text = """TW: Violence, death

Sorry for formatting, I'm on mobile.

## Part One

I moved into the old house on **Elm Street** last Tuesday. The realtor, [Mrs. Henderson](https://example.com/realtor), had been *unusually* eager to close the deal.

> "You won't find a better price in this market," she'd said.

The first night, I heard ~~nothing~~ something scratching inside the walls.

Edit: Fixed some details about the timeline.

---

[Part 1](https://reddit.com/abc) | [Part 2](https://reddit.com/def)
Next: https://reddit.com/r/nosleep/comments/nextpart"""

        result = clean_for_narration(text)

        # Story content should survive
        assert "I moved into the old house on Elm Street last Tuesday" in result
        assert "Mrs. Henderson" in result
        assert "unusually" in result
        assert "something scratching inside the walls" in result

        # Artifacts should be gone
        assert "TW:" not in result
        assert "Sorry for formatting" not in result
        assert "##" not in result
        assert "**" not in result
        assert "*" not in result
        assert "~~" not in result
        assert "Edit:" not in result
        assert "---" not in result
        assert "Part 1" not in result
        assert "https://" not in result
        assert "reddit.com" not in result

    def test_empty_string(self):
        assert clean_for_narration("") == ""

    def test_plain_text_unchanged(self):
        text = "A simple story with no markdown or artifacts."
        assert clean_for_narration(text) == text
