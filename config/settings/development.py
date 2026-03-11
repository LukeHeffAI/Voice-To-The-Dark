"""Development settings — DEBUG on, permissive CORS."""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

# In development, Vite serves the frontend on port 5173
# Django only needs to serve the API
