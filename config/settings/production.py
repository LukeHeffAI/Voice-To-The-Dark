"""Production settings — security hardened."""

import os

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8000").split(",")
]

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Configurable for HTTP LAN access (set SECURE_COOKIES=false in .env)
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "true").lower() == "true"
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
