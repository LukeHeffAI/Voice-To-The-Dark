import hashlib


def hash_content(text: str) -> str:
    """Generate a SHA-256 hash of the story text for duplicate detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
