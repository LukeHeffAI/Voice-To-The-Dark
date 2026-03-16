"""Unit tests for apps.stories.services.hashing."""

import hashlib
from apps.stories.services.hashing import hash_content


def test_returns_sha256_hex():
    text = "Hello, world!"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert hash_content(text) == expected


def test_consistent_for_same_input():
    text = "Some story text that should always hash the same way."
    assert hash_content(text) == hash_content(text)


def test_different_for_different_input():
    assert hash_content("story A") != hash_content("story B")


def test_64_char_hex_string():
    result = hash_content("test")
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_handles_unicode():
    text = "A story with unicode: \u00e9\u00e0\u00fc \u00f1 \u2014 \u201cquotes\u201d"
    result = hash_content(text)
    assert len(result) == 64


def test_empty_string():
    result = hash_content("")
    expected = hashlib.sha256(b"").hexdigest()
    assert result == expected
