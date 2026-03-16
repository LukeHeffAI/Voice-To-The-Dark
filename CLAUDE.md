# Voice In The Dark - Development Guide

## Project Overview

A web application that transforms Reddit r/nosleep horror stories into dramatic audio productions using ElevenLabs TTS and Claude AI script adaptation.

## Tech Stack

- **Backend**: Python 3.11, Django 5.1, Django Ninja (REST API), SQLite
- **Frontend**: Vue 3, TypeScript, Vite, Tailwind CSS v4, Pinia
- **External APIs**: ElevenLabs (TTS/SFX), Anthropic Claude (script adaptation)
- **Audio**: pydub + ffmpeg
- **Deployment**: Docker (multi-stage build), Gunicorn, WhiteNoise

## Running the App

```bash
# Development — backend
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver

# Development — frontend (separate terminal)
cd frontend && npm run dev

# Production — Docker
docker compose up -d --build
```

## Running Tests

```bash
# Backend tests (Django + services)
python -m pytest tests/ -v --tb=short

# Run specific test module
python -m pytest tests/test_api/test_stories_api.py -v

# Run tests matching a keyword
python -m pytest tests/ -k "test_submit" -v

# Frontend unit tests
cd frontend && npm test

# Frontend E2E tests (requires both servers running)
cd frontend && npm run test:e2e
```

## Project Structure

- `apps/` - Django apps
  - `accounts/` - User authentication (custom User model, JWT)
  - `stories/` - Story models, folders, settings
  - `audio/` - Characters, scripts, segments
  - `player/` - Playback state, audio streaming
  - `tasks/` - Background task queue with progress tracking
  - `common/` - Shared utilities (rate limiting)
- `config/` - Django configuration
  - `settings/` - Base, development, production settings
  - `urls.py` - URL routing (Django Ninja API + SPA catch-all)
  - `views.py` - SPA catch-all view
  - `wsgi.py` - WSGI application
- `frontend/` - Vue 3 SPA
  - `src/components/` - Reusable Vue components
  - `src/pages/` - Route page views
  - `src/stores/` - Pinia state management
  - `src/api/client.ts` - API client
  - `src/router/` - Vue Router configuration
  - `e2e/` - Playwright E2E tests
- `services/` - Framework-agnostic business logic (reddit, elevenlabs, script_adapter, etc.)
- `schemas/` - Pydantic request/response schemas
- `scripts/` - Utility scripts (v1 migration, deployment verification)
- `tests/` - Test suite
  - `test_api/` - Django API integration tests
  - `v2/` - Service unit tests
- `app/` - Legacy FastAPI v1 app (kept for reference during migration)

## Testing Requirements

**After every change**, run the feature testing agent (`.claude/skills/feature-test.md`) to:
1. Identify which tests cover the changed files
2. Run the relevant tests
3. Fix any failures before committing
4. Write new tests for any uncovered functionality

## Key Conventions

- All external API calls (Reddit, ElevenLabs, Claude) must be mocked in tests
- Use `@patch("apps.MODULE.api.function_name")` to mock at the import site
- Test fixtures are in `tests/test_api/conftest.py` (client, test_user, auth_headers, etc.)
- API routes are mounted at `/api/` via Django Ninja
- Vue SPA is served by a catch-all route for all non-API, non-admin paths
- Static files served via WhiteNoise from `frontend/dist`
