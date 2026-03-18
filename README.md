# Voice In The Dark

A self-hosted web app that transforms Reddit r/nosleep horror stories into dramatic multi-voice audio productions using AI.

## Features

- **Reddit integration** — Submit any r/nosleep URL or browse the Best of All Time list
- **AI script adaptation** — Claude rewrites stories into dramatic narration scripts with characters, stage directions, and sound effect cues
- **Multi-voice TTS** — ElevenLabs generates narration with distinct voices per character
- **Sound effects** — Automatic SFX generation from script cues, mixed into the final audio
- **Audio player** — Full playback controls with seek bar, progress saving, and lock screen support
- **Folder organisation** — Group stories into custom folders
- **Mobile-friendly** — Vue 3 SPA designed for phone use; add to home screen for an app-like experience
- **Self-hosted** — Runs on any Linux machine with Docker; your data stays on your network

## Quick Start

```bash
git clone <your-repo-url>
cd Voice-To-The-Dark
bash deploy.sh
```

The deploy script handles everything: environment setup, Docker build, database migrations, legacy data import (if upgrading from v1), and admin account creation. The app auto-restarts on reboot.

For detailed deployment instructions, phone setup, Cloudflare Tunnel remote access, and troubleshooting, see **[SETUP_GUIDE.md](SETUP_GUIDE.md)**.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, Django 5, Django Ninja |
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS v4, Pinia |
| TTS & SFX | ElevenLabs API |
| Script Adaptation | Anthropic Claude API |
| Audio Processing | pydub + ffmpeg |
| Deployment | Docker, Gunicorn, WhiteNoise |
| Database | SQLite |

## Development

```bash
# Backend
python manage.py runserver

# Frontend (separate terminal)
cd frontend && npm run dev

# Run Python tests
python -m pytest tests/ -v --tb=short

# Run frontend tests
cd frontend && npm run test
```

The Vite dev server proxies `/api` and `/admin` requests to Django on port 8010.

## Project Structure

```
config/           Django project settings & URL routing
apps/
  accounts/       User authentication (JWT via Django Ninja)
  stories/        Story management, Reddit integration, folders
  audio/          Audio generation pipeline, task queue
  player/         Playback state, streaming endpoints
  core/           Shared utilities (rate limiting)
frontend/         Vue 3 SPA (pages, stores, API client, composables)
tests/            Python test suite (pytest + pytest-django)
deploy.sh         One-command production deployment
tunnel.sh         Optional Cloudflare Tunnel for remote access
```

## Requirements

- **Docker** with Docker Compose v2
- **ElevenLabs API key** — for text-to-speech and sound effects
- **Anthropic API key** — for Claude script adaptation

## License

Private use.
