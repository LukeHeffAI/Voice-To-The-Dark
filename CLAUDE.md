# Voice In The Dark - Development Guide

## Project Overview

A Django web application that transforms Reddit r/nosleep horror stories into dramatic audio productions using ElevenLabs TTS and Claude AI script adaptation. Features a Vue 3 SPA frontend with Tailwind CSS.

## Tech Stack

- **Backend**: Python 3.11, Django 5, Django Ninja (API), SQLite
- **Frontend**: Vue 3, TypeScript, Vite, Tailwind CSS v4, Pinia
- **External APIs**: ElevenLabs (TTS/SFX), Anthropic Claude (script adaptation)
- **Audio**: pydub + ffmpeg
- **Deployment**: Docker, Gunicorn, WhiteNoise

## Running the App

```bash
# Backend (development)
python manage.py runserver

# Frontend (development)
cd frontend && npm run dev

# Production (Docker)
docker compose up -d --build
```

## Running Tests

```bash
# Run all Python tests
python -m pytest tests/ -v --tb=short

# Run specific test module
python -m pytest tests/test_api_stories.py -v

# Run tests matching a keyword
python -m pytest tests/ -k "test_submit" -v

# Run frontend tests
cd frontend && npm run test

# Run frontend tests in watch mode
cd frontend && npm run test:watch
```

## Project Structure

- `config/` - Django project configuration
  - `settings/` - Settings (base, development, production)
  - `urls.py` - URL routing (API + SPA catch-all)
  - `wsgi.py` / `asgi.py` - WSGI/ASGI entry points
- `apps/` - Django application modules
  - `accounts/` - User authentication (JWT via Django Ninja)
  - `stories/` - Story management, Reddit integration, folders
  - `audio/` - Audio generation pipeline, task queue
  - `player/` - Playback state, streaming endpoints
  - `core/` - Shared utilities (rate limiting)
- `frontend/` - Vue 3 SPA
  - `src/pages/` - Page components (Home, Story, Player, Settings, etc.)
  - `src/stores/` - Pinia stores (auth, player, playlist, notifications)
  - `src/api/` - API client and TypeScript types
  - `src/composables/` - Reusable composition functions
- `tests/` - Test suite (pytest + pytest-django)
- `manage.py` - Django management CLI

## Testing Requirements

**After every change**, run the relevant tests:
1. Identify which tests cover the changed files
2. Run the relevant tests
3. Fix any failures before committing
4. Write new tests for any uncovered functionality

## Key Conventions

- All external API calls (Reddit, ElevenLabs, Claude) must be mocked in tests
- Use `@patch("apps.MODULE.api.function_name")` to mock at the import site
- Test fixtures are in `tests/conftest.py` (api_client, test_user, auth_headers, sample_story, etc.)
- Rate limiting state is cleared between tests via `_request_log.clear()`
- API endpoints are under `/api/` prefix (e.g., `/api/stories/`, `/api/auth/login`)
- Django Ninja auth uses JWT (HttpBearer) with optional auth via `OptionalJWTAuth`
- Background tasks use `GenerationTask` model + thread-based `task_runner`
