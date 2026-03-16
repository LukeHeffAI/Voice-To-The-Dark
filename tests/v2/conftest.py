"""Minimal conftest for v2 service tests.

Services are framework-agnostic Python — most tests only need Django
settings to be configured (for services that read API keys or data paths).
"""

import os

import django
from django.conf import settings  # noqa: F401

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()
