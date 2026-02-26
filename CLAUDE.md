# Voice In The Dark - Development Guide

## Project Overview

A FastAPI web application that transforms Reddit r/nosleep horror stories into dramatic audio productions using ElevenLabs TTS and Claude AI script adaptation.

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, SQLite
- **External APIs**: ElevenLabs (TTS/SFX), Anthropic Claude (script adaptation)
- **Frontend**: Jinja2 templates, vanilla JavaScript, PWA
- **Audio**: pydub + ffmpeg

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v --tb=short

# Run specific test module
python -m pytest tests/test_router_stories.py -v

# Run tests matching a keyword
python -m pytest tests/ -k "test_submit" -v
```

## Project Structure

- `app/` - Main application package
  - `routers/` - API endpoints (auth, stories, audio, player, settings)
  - `services/` - Business logic (reddit, elevenlabs, script_adapter, text_cleaner, etc.)
  - `models/` - SQLAlchemy ORM models
  - `schemas/` - Pydantic request/response schemas
  - `templates/` - Jinja2 HTML templates
  - `static/` - CSS, JS, icons
- `tests/` - Test suite (pytest)

## Testing Requirements

**After every change**, run the feature testing agent (`.claude/skills/feature-test.md`) to:
1. Identify which tests cover the changed files
2. Run the relevant tests
3. Fix any failures before committing
4. Write new tests for any uncovered functionality

## Key Conventions

- All external API calls (Reddit, ElevenLabs, Claude) must be mocked in tests
- Use `@patch("app.routers.MODULE.function_name")` to mock at the import site
- Test fixtures are in `tests/conftest.py` (db_session, client, test_user, auth_headers, etc.)
- Rate limiting state is cleared between tests via `_request_log.clear()`
- Templates must handle None values gracefully (use `| default()` filters)
