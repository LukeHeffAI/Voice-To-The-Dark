import re


def clean_for_narration(text: str) -> str:
    """Transform Reddit-formatted story text into clean prose ready for TTS.

    Strips markdown, meta-text, navigation boilerplate, and other artifacts
    that would sound wrong when read aloud by a text-to-speech engine.
    """
    text = _remove_navigation_blocks(text)
    text = _remove_meta_lines(text)
    text = _convert_markdown_to_prose(text)
    text = _clean_whitespace(text)
    return text.strip()


def _remove_navigation_blocks(text: str) -> str:
    """Remove part navigation links and author boilerplate that appear at the
    start or end of multi-part stories."""

    # Remove lines that are just link navigation, e.g.:
    #   [Part 1](url) | [Part 2](url) | [Part 3](url)
    #   [Previous](url) | [Next](url)
    #   Next: https://reddit.com/...
    nav_patterns = [
        # "Part X" link lists separated by pipes
        r"^.*\[Part\s*\d+\]\(https?://[^)]+\).*\|.*$",
        # Previous/Next navigation
        r"^.*\[(Previous|Next|Prev|Back|Continue|Forward)\]\(https?://[^)]+\).*$",
        # Bare "Next:" or "Previous:" lines with a URL
        r"^(Next|Previous|Prev|Continue)\s*:\s*https?://\S+\s*$",
        # Bare reddit links on their own line (usually navigation)
        r"^https?://(?:www\.)?reddit\.com/r/\w+/comments/\S+\s*$",
    ]
    for pattern in nav_patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE)

    return text


def _remove_meta_lines(text: str) -> str:
    """Remove Reddit-specific meta-text that isn't part of the story."""

    meta_patterns = [
        # Edit/Update notes
        r"^Edit\s*\d*\s*:.*$",
        r"^Update\s*\d*\s*:.*$",
        r"^EDIT\s*\d*\s*:.*$",
        r"^UPDATE\s*\d*\s*:.*$",
        # Trigger/content warnings
        r"^(?:TW|CW|Trigger Warning|Content Warning)\s*:.*$",
        # TL;DR
        r"^TL;?\s*DR\s*:?.*$",
        # "Obligatory" / "Mandatory" disclaimers
        r"^(?:Obligatory|Mandatory)\s+.*$",
        # Subreddit cross-post notices
        r"^(?:Cross-?posted|X-?posted|Originally posted)\s+(?:from|to|on)\s+.*$",
        # "This is my first post" / "Sorry for formatting" boilerplate
        r"^(?:Sorry for|Apologies for|Excuse).*(?:formatting|mobile|English).*$",
        # Throwaway account disclaimers
        r"^(?:Using a|This is a|On a)\s*(?:throwaway|throw-away|burner).*$",
    ]
    for pattern in meta_patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE)

    return text


def _convert_markdown_to_prose(text: str) -> str:
    """Convert markdown formatting to clean prose suitable for narration."""

    # Remove horizontal rules (---, ***, ___)
    text = re.sub(r"^[\-\*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove heading markers but keep the text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Convert bold/italic markers to plain text
    # Bold+italic: ***text*** or ___text___
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)
    # Bold: **text** or __text__
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    # Italic: *text* or _text_ (careful not to match mid-word underscores)
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)

    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"\1", text)

    # Inline code: `text`
    text = re.sub(r"`(.+?)`", r"\1", text)

    # Code blocks: ```...```
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Block quotes: lines starting with >
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # Markdown links: [text](url) → keep just the text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Bare URLs — remove them (they're not meant to be read aloud)
    text = re.sub(r"https?://\S+", "", text)

    # Superscript: ^text or ^(text)
    text = re.sub(r"\^\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\^(\S+)", r"\1", text)

    # HTML entities that sometimes leak through
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&#x200B;", "")  # zero-width space

    # Escaped markdown characters
    text = re.sub(r"\\([*_~`#\[\]()>])", r"\1", text)

    return text


def _clean_whitespace(text: str) -> str:
    """Normalize whitespace for natural reading flow."""

    # Collapse runs of blank lines into a single paragraph break
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove trailing whitespace on each line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

    # Remove leading whitespace on each line (Reddit sometimes indents)
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)

    return text
