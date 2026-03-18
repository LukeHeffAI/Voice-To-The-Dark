# Voice In The Dark — Full Project Documentation & Modernization Plan

## Context

Voice In The Dark is a self-hosted web application that transforms Reddit r/nosleep horror stories into dramatic multi-voice audio productions using Claude AI for script adaptation and ElevenLabs for TTS/SFX generation. The project has grown organically with an ad-hoc approach: vanilla JS with a custom SPA router, Jinja2 server-rendered templates with inline CSS, no build system, no database migrations, and tightly coupled business logic. While functional, this architecture won't scale for maintainability, testability, or feature development. This plan documents every feature of the current system and recommends a modern tech stack for a ground-up rebuild.

---

# PART 1: COMPLETE PROJECT DOCUMENTATION

## 1.1 Project Overview

| Attribute | Value |
|-----------|-------|
| **Purpose** | Transform Reddit r/nosleep horror stories into dramatic audio productions |
| **Users** | 2-10 (small group, self-hosted) |
| **Deployment** | Docker on self-hosted server (home network + optional Cloudflare Tunnel) |
| **Backend** | Python 3.11, FastAPI 0.104+, SQLAlchemy 2.0+, SQLite |
| **Frontend** | Jinja2 templates, vanilla JS, CSS-in-HTML, custom SPA router |
| **External APIs** | Anthropic Claude (script adaptation), ElevenLabs (TTS/SFX), Reddit (content) |
| **Audio Processing** | pydub + ffmpeg |
| **Auth** | JWT (HS256, 4-week expiry) + bcrypt, cookie + header based |
| **PWA** | Basic service worker, MediaSession API, installable |

## 1.2 Core User Workflows

### Primary Workflow: Story Submission → Audio Production Pipeline

#### Step 1: Story Discovery & Submission
- **Browse top r/nosleep stories**: Home page shows top posts from Reddit r/nosleep, filterable by timeframe (today, week, month, year, all-time). Each card shows title, author, score, gilding, flair, and series flair. User clicks a card to preview or submit.
- **URL submission**: User pastes a Reddit r/nosleep URL. System validates the URL format, fetches the post via Reddit's JSON API, and extracts title, author, and body text. Duplicate detection uses both URL uniqueness and SHA-256 content hash.
- **Manual submission**: User enters a title, author (optional), and raw text content directly — no Reddit URL required. This enables stories from other sources, PDFs, or custom content.
- **Fetch preview**: Before committing, user can preview the story's title, author, and first ~500 chars to confirm it's the right post.
- **Related files**: `app/routers/stories.py` (submit, submit-manual, fetch-preview, check-duplicate), `app/services/reddit.py` (fetch_post_metadata, fetch_story_text), `app/templates/submit.html`

#### Step 2: Text Cleaning & Preparation
- **Markdown stripping**: Reddit markdown (bold, italic, headers, block quotes, code blocks, horizontal rules, links) is converted to clean prose suitable for TTS narration.
- **Navigation removal**: Part navigation blocks ("Previous | Next", "Part 1 | Part 2" link tables) are stripped since they're not part of the story.
- **Meta line removal**: Reddit-specific noise is stripped: "Edit:", "Update:", trigger/content warnings, TL;DR, "throwaway account" disclaimers.
- **Whitespace normalization**: Multiple blank lines collapsed, trailing whitespace removed, indentation stripped.
- **Result**: Clean prose stored in `story.narration_text` alongside the original `story.text_content`.
- **Related files**: `app/services/text_cleaner.py` (clean_for_narration pipeline), `app/routers/stories.py` (calls cleaner on submit)

#### Step 3: Series Detection & Multi-Part Handling
- **Automatic series discovery**: When a story is submitted, the system searches the author's Reddit profile for other r/nosleep posts with similar base titles (e.g., "The Cabin" matches "The Cabin - Part 2", "The Cabin Chapter 3"). Title matching strips part/chapter suffixes and compares base strings.
- **Auto-submission of parts**: Discovered series parts not already in the database are automatically submitted, cleaned, and linked. The `series_json` field on each story caches the discovered parts list.
- **Multi-part concatenation**: For stories with explicit next-part links in the body text, the system recursively follows those links, fetching and concatenating all parts with `---` separators. Visited post IDs prevent infinite loops.
- **Part ordering**: Series parts are sorted by `created_utc` (oldest first) — more reliable than title-derived part numbers which vary in format.
- **Related files**: `app/services/reddit.py` (find_series_parts, fetch_multi_part_story, _gather_story_parts), `app/routers/stories.py` (series-parts endpoint, auto-submit logic)

#### Step 4: Script Generation (Claude AI)
- **AI adaptation**: The cleaned narration text is sent to Claude Sonnet with a detailed system prompt that instructs it to act as a horror audio drama director. Claude transforms the first-person story into a structured narration script.
- **Script structure**: The output is a `NarrationScript` containing:
  - **Characters**: A dictionary mapping character names to voice profiles (e.g., `{"narrator": {"voice_profile": "deep, steady, ominous"}, "Sarah": {"voice_profile": "young, female, fearful"}}`). The narrator is always the first-person protagonist.
  - **Segments**: An ordered list of typed segments:
    - `narration` — Narrator's internal monologue/description, with tone direction (e.g., "foreboding", "building dread")
    - `dialogue` — Character speech, with character reference and tone (e.g., "panicked whisper")
    - `sfx` — Sound effect cues with text description (e.g., "door creaking slowly", "footsteps on wooden floor")
    - `ambient` — Background atmosphere (e.g., "rain on windows", "distant thunder"), optionally looping
    - `pause` — Silence between scenes, specified in milliseconds (800-2000ms)
- **Long story handling**: Stories exceeding ~12,000 characters are split at paragraph boundaries into sections. Each section is adapted independently, with character definitions carried forward. If Claude's response is truncated (hits `max_tokens`), the section is automatically re-split into smaller pieces.
- **Series character inheritance**: When generating a script for Part 2+ of a series, character definitions from earlier parts are passed to Claude as `prior_characters`, ensuring consistent voice assignments across the series.
- **Rate limited**: 10 requests per hour per user.
- **Related files**: `app/services/script_adapter.py` (generate_script, system prompt), `app/schemas/narration.py` (NarrationScript, ScriptSegment, CharacterProfile), `app/routers/audio.py` (generate-script endpoint)

#### Step 5: Script Editing
- **Interactive editor**: The script editor page displays all characters and segments in an editable interface. Users can:
  - Edit character names and voice profile descriptions
  - Change voice assignments per character (dropdown of all available ElevenLabs voices)
  - Edit segment text, tone directions, SFX descriptions
  - Add/remove/reorder segments
  - Change segment types (narration ↔ dialogue ↔ SFX ↔ ambient ↔ pause)
- **Script validation**: On save, the editor validates that all segment character references exist in the characters dictionary, and that required fields are present.
- **Audio invalidation**: Saving edits invalidates the existing audio file (sets `audio_file_path` to null), requiring re-generation.
- **Related files**: `app/routers/audio.py` (GET/PUT script endpoints), `app/templates/script_editor.html`

#### Step 6: Voice Assignment
- **Auto-assignment**: The voice pool contains 30+ curated ElevenLabs voices, each tagged with gender (male/female), age (young/adult/middle/elder), archetypes (keyword tags like "deep", "warm", "sinister", "British"), and role (narrator/character).
- **Scoring algorithm**: For each character, the system parses the `voice_profile` text and scores each pool voice: +10 for gender match (−20 penalty for mismatch), +5 for age match, +2 per keyword overlap. A small random jitter prevents identical voice assignments when scores tie.
- **Narrator voices**: Voices tagged with `role: "narrator"` use the `eleven_multilingual_v2` model for richer delivery. Character voices use `eleven_v3`.
- **Manual override**: Users can manually assign specific voices in the script editor, bypassing auto-assignment.
- **Related files**: `app/services/voice_pool.py` (VOICE_POOL, auto_assign_voices), `app/routers/audio.py` (generate-narration auto-assignment)

#### Step 7: Audio Generation Pipeline
- **Segment merging**: Consecutive narration/dialogue segments from the same character are merged to reduce API calls and improve speech flow.
- **Per-segment generation**: For each segment in order:
  - **Cache check**: A SHA-256 hash of the segment content + voice_id + preset is checked against the segment cache (`./data/segment_cache/`). If the MP3 already exists, it's reused (saving API costs and time).
  - **TTS generation** (narration/dialogue): Text is sent to ElevenLabs with voice-specific settings. Long text is chunked at sentence boundaries (max 4,900 chars per request). Four horror-tuned presets control stability, similarity boost, and style parameters: `horror_narrator`, `horror_dialogue`, `whisper`, `calm`. The tone direction maps to the appropriate preset (e.g., "panicked" → `horror_dialogue`, "quiet" → `whisper`).
  - **SFX generation** (sfx): The description text is sent to ElevenLabs' sound generation API. SFX are cached by description hash in `./data/sfx_cache/`.
  - **Ambient generation** (ambient): Similar to SFX but with longer duration and optional looping flag.
  - **Pause generation** (pause): Pure silence of specified duration.
- **Rate limited**: 5 requests per hour per user.
- **Related files**: `app/services/narration_generator.py` (generate_narration orchestrator), `app/services/elevenlabs.py` (TTS/SFX API calls), `app/services/segment_cache.py` (cache lookup/store)

#### Step 8: Audio Mixing & Mastering
- **Timeline-based composition**: All generated segments are placed on a timeline:
  - **Voice track**: Narration and dialogue segments are concatenated sequentially with 100ms crossfades between adjacent segments and 1,800ms silence between scene transitions.
  - **Ambient bed**: Ambient segments are layered underneath the voice track at −20 dB, running from their cue point to the next ambient change or end of story.
  - **SFX overlay**: Sound effects are overlaid on top at −6 dB, placed at the timeline position where they were cued in the script.
- **Fades**: 2,500ms fade-in at the start, 3,500ms fade-out at the end.
- **Loudness normalization**: Final mix is normalized to −18 dBFS for consistent listening volume.
- **Output**: Single MP3 file saved to `./data/stories/{uuid}.mp3`, path stored in `story.audio_file_path`.
- **Cache statistics**: Response includes total segments processed, cache hits/misses, and API calls saved.
- **Related files**: `app/services/audio_mixer.py` (mix_narration, timeline building, rendering, fading, normalization)

#### Step 9: Playback
- **Persistent audio player**: A single `<audio>` element lives in the app shell (`base.html`) and survives all page navigation via the custom SPA router. The mini-player bar is fixed to the bottom of every page (56px height).
- **Full player page**: Dedicated `/listen/{story_id}` page with large controls, animated EQ visualizer (Web Audio API + Canvas), progress bar with seek, speed control (0.5x-3x), and series navigation.
- **Queue/playlist**: Users can queue multiple stories: add-next, add-to-end, reorder (drag-and-drop via SortableJS), remove, clear. The playlist drawer slides up from the bottom as a sheet overlay.
- **Repeat modes**: Off → All (loop queue) → One (loop current track), cycled via repeat button.
- **Speed control**: Playback speed 0.5x-3.0x in 0.25x increments, persisted in localStorage.
- **Position saving**: Current playback position auto-saved to the server every 15 seconds via `navigator.sendBeacon` (fire-and-forget, works even on page close). Position is restored when revisiting a story.
- **MediaSession API**: Lock-screen controls on mobile (play/pause, skip forward/back, track info, artwork).
- **Audio streaming**: HTTP Range request support (206 Partial Content) for efficient mobile playback and seeking without downloading the entire file.
- **Download**: Direct MP3 download link with Content-Disposition header.
- **Related files**: `app/static/js/player-core.js` (PlayerCore class), `app/static/js/playlist.js` (PlaylistManager), `app/routers/player.py` (stream, download, listen page), `app/templates/player.html`, `app/templates/base.html` (mini-player)

### Secondary Workflows

#### Story Reading
- **In-app reader**: The `/read/{story_id}` page renders the full story text in a comfortable reading format with a serif font (Cormorant Garamond), drop caps on the first paragraph, and generous line-height.
- **Scroll progress**: A progress bar at the top of the reader tracks scroll position through the story (0-100%).
- **Story metadata**: Word count and estimated reading time displayed at the top. If audio exists, a "Listen" button links to the audio player.
- **Series navigation**: For multi-part stories, navigation links to previous/next parts are shown.
- **Related files**: `app/templates/reader.html`, `app/routers/player.py` (read endpoint)

#### Story Browsing & Home Page
- **Recently viewed** (logged in): Home page shows stories the user has recently opened, sorted by last viewed, with the ability to hide stories from this list. Each card shows title, author, audio/script status badges, and estimated Winks cost.
- **All stories** (not logged in): Shows all stories in the database, most recent first.
- **Folder sidebar**: User-created folders appear as a sidebar/dropdown navigation. Clicking a folder shows its stories.
- **Story cards**: Each card has a context menu (three-dot button) with actions: add to queue, add to folder, hide from view.
- **Teaser text**: Stories show a 2-4 sentence teaser preview on hover or in the card.
- **Related files**: `app/templates/story_list.html`, `app/templates/folder.html`, `app/routers/player.py` (home and folder endpoints)

#### Folder Organization
- **Create folders**: Users create named folders (max 60 chars) to organize stories by theme, series, or preference.
- **Add/remove stories**: Stories can be added to or removed from any folder. A story can exist in multiple folders.
- **Folder view**: Each folder has a dedicated page showing its stories with the same card format as the home page.
- **Delete folders**: Deleting a folder removes all memberships but does not delete the stories themselves.
- **Per-user isolation**: Folders are scoped to the authenticated user — each user has their own folder structure.
- **Related files**: `app/routers/stories.py` (folders/list, folders/create, folders/{id}/add, etc.), `app/models/story.py` (StoryFolder, StoryFolderMembership)

#### Voice Library & Previews
- **Voice browser**: The settings page has a "Voice Library" tab displaying all 30+ voices in the pool, organized by gender. Each voice card shows name, age, archetypes, role (narrator/character), and model.
- **Voice previews**: Users can click "Preview" to hear a sample of any voice reading a horror-themed sentence. Previews are generated once via ElevenLabs and cached as MP3s in `./data/voice_previews/`. Users can select which ElevenLabs model to use for the preview.
- **Voice notes**: Users can add persistent text notes to any voice (e.g., "Good for villains", "Too breathy for narrator"). Notes are stored in `app_settings` as a JSON dictionary.
- **Related files**: `app/routers/settings.py` (voice-preview, voice-notes endpoints), `app/services/elevenlabs.py` (generate_voice_preview), `app/services/voice_pool.py` (VOICE_POOL), `app/templates/settings.html`

#### Settings Management
- **Reddit cache TTL**: Users can configure how long Reddit API responses are cached before being refreshed. Options range from 1 hour to 1 month (default: 1 week). This affects how fresh the "Top r/nosleep" listings are.
- **Manual cache upload**: Users can upload a Reddit `.json` file for any timeframe (today, week, month, year, alltime) to manually populate or update the listing cache — useful when Reddit API is rate-limited or down.
- **Cache age display**: Each timeframe shows when it was last refreshed, with visual indicators for stale caches.
- **Related files**: `app/routers/settings.py`, `app/services/reddit.py` (get_cache_info, get_cache_path_for_timeframe), `app/templates/settings.html`

#### Winks Tracking (ElevenLabs Quota)
- **What are Winks**: A user-friendly representation of ElevenLabs' character quota. The app maps the account's remaining character allowance to a 0-40 "Winks" scale (0 = quota exhausted, 40 = full quota available).
- **Display**: The current Winks balance is shown in the navigation/header area and on story cards.
- **Per-story cost estimation**: For stories without audio, the system estimates how many Winks generating their audio would cost, based on the script's total TTS character count (or narration text length if no script exists).
- **Caching**: Subscription info is fetched from ElevenLabs API and cached for 5 minutes (1 minute on failure) to avoid excessive API calls.
- **Related files**: `app/services/winks.py` (get_winks_remaining, estimate_story_winks), `app/routers/player.py` (passes winks to templates)

#### Story Detail Page
- **Pipeline controls**: The story detail page (`/story/{id}`) is the central hub for managing a story's lifecycle. It shows the current state and provides action buttons for each pipeline step:
  1. "Generate Script" (if no script exists) → triggers Claude adaptation
  2. "Edit Script" (if script exists) → opens script editor
  3. "Generate Audio" (if script exists but no audio) → triggers full audio pipeline
  4. "Re-generate Audio" (if audio exists) → regenerates with cache utilization
  5. "Listen" / "Read" → links to player/reader
- **Story statistics**: Word count, estimated listening duration, Winks cost estimate, character count, segment count.
- **Series parts**: If the story is part of a series, all discovered parts are listed with links and generation status indicators.
- **Related files**: `app/templates/story_detail.html`, `app/routers/player.py` (story detail endpoint)

#### Authentication
- **Admin-creates-users model**: Only admin users can register new accounts (no self-registration). This keeps the app private for a small group.
- **Login**: Username + password authentication returns a JWT (4-week expiry) set as both an HTTP-only cookie and a Bearer token in the response body. The cookie enables browser navigation; the Bearer token enables API calls from JavaScript.
- **Logout**: Clears the auth cookie.
- **Role-based access**: Admin users can create other users. Most features require authentication; browsing stories and streaming audio are available without login.
- **Related files**: `app/routers/auth.py`, `app/auth.py` (JWT/bcrypt utilities), `app/deps.py` (get_current_user, require_admin), `app/templates/login.html`

#### PWA (Progressive Web App)
- **Installable**: Manifest with `standalone` display mode, dark theme color (#050505), 192px and 512px icons. Can be installed on home screen on mobile.
- **Service worker**: Minimal implementation (skipWaiting + clientsClaim, no asset caching strategy). Enables PWA installation badge.
- **Apple integration**: `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style` meta tags for iOS Safari.
- **MediaSession**: Lock-screen playback controls on both Android and iOS with track metadata and artwork.
- **Related files**: `app/static/manifest.json`, `app/static/service-worker.js`, `app/templates/base.html` (meta tags)

## 1.3 Database Schema (6 tables + 1 KV store)

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | Auto-increment |
| username | str | Unique, indexed |
| password_hash | str | bcrypt |
| is_admin | bool | Default false |

### `stories`
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | Auto-increment |
| title | str | Required |
| reddit_url | str | Unique, indexed, nullable |
| text_content | text | Required, raw story text |
| narration_text | text | Cleaned for TTS |
| script_json | text | Serialized NarrationScript |
| content_hash | str(64) | SHA-256, indexed, dedup |
| author | str | Nullable |
| audio_file_path | str | Path to final MP3 |
| part_count | int | Default 1 |
| series_json | text | Cached series metadata |
| created_at | datetime | Auto |
| updated_at | datetime | Auto |

### `playback_states`
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| user_id | int FK→users | CASCADE delete |
| story_id | int FK→stories | CASCADE delete |
| position_seconds | float | Default 0.0 |
| updated_at | datetime | Auto |
| | | UNIQUE(user_id, story_id) |

### `story_views`
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| user_id | int FK→users | CASCADE delete |
| story_id | int FK→stories | CASCADE delete |
| viewed_at | datetime | Auto |
| hidden | bool | Default false |
| | | UNIQUE(user_id, story_id) |

### `story_folders`
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| user_id | int FK→users | CASCADE delete |
| name | str | |
| created_at | datetime | Auto |
| | | UNIQUE(user_id, name) |

### `story_folder_memberships`
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| folder_id | int FK→story_folders | CASCADE delete |
| story_id | int FK→stories | CASCADE delete |
| added_at | datetime | Auto |
| | | UNIQUE(folder_id, story_id) |

### `app_settings` (Key-Value)
| Column | Type | Notes |
|--------|------|-------|
| key | str PK | Setting name |
| value | text | Setting value |
| updated_at | datetime | Auto |

## 1.4 API Endpoints (Complete)

### Auth (`/auth`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | Admin | Create user |
| POST | `/auth/login` | None | Authenticate, set cookie + return JWT |
| POST | `/auth/logout` | None | Clear cookie |
| GET | `/auth/me` | Required | Get current user |

### Stories (`/stories`)
| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/stories/submit` | Required | — | Submit story from r/nosleep URL |
| POST | `/stories/submit-manual` | Required | — | Manual story entry |
| GET | `/stories/` | None | — | List stories (paginated) |
| GET | `/stories/top-nosleep` | None | — | Browse top r/nosleep posts |
| GET | `/stories/fetch-preview` | Required | 30/min | Preview URL before submission |
| GET | `/stories/check-duplicate/` | None | — | Check URL duplicate |
| GET | `/stories/{id}` | None | — | Get story by ID |
| GET | `/stories/{id}/series-parts` | None | — | Get/discover series parts |
| POST | `/stories/playback` | Optional | — | Save playback position |
| GET | `/stories/playback/{id}` | Optional | — | Get playback position |
| POST | `/stories/{id}/hide` | Required | — | Hide from recently viewed |
| POST | `/stories/{id}/unhide` | Required | — | Restore hidden story |
| GET | `/stories/folders/list` | Required | — | List user folders |
| POST | `/stories/folders/create` | Required | — | Create folder |
| DELETE | `/stories/folders/{id}` | Required | — | Delete folder |
| POST | `/stories/folders/{id}/add` | Required | — | Add story to folder |
| DELETE | `/stories/folders/{id}/stories/{sid}` | Required | — | Remove from folder |

### Audio (`/audio`)
| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/audio/generate-script` | Required | 10/hr | Claude script generation |
| GET | `/audio/script/{id}` | None | — | Get script for preview |
| PUT | `/audio/script/{id}` | Required | — | Edit script (invalidates audio) |
| POST | `/audio/generate-narration` | Required | 5/hr | Full audio generation pipeline |
| POST | `/audio/generate-audio` | Required | — | Simple single-voice TTS |

### Player (Web UI — root level)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Optional | Story list (recently viewed for logged-in) |
| GET | `/folder/{id}` | Required | Folder view |
| GET | `/login` | None | Login page |
| GET | `/submit` | Optional | Submission page |
| GET | `/story/{id}` | Optional | Story detail + pipeline controls |
| GET | `/story/{id}/edit-script` | Optional | Script editor |
| GET | `/read/{id}` | Optional | Text reader |
| GET | `/listen/{id}` | Optional | Audio player |
| GET | `/story-info/{id}` | None | Lightweight JSON metadata |
| GET | `/stream/{id}` | None | Audio streaming (HTTP Range) |
| GET | `/download/{id}` | None | Audio file download |

### Settings (`/settings`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/settings/` | Required | Settings page |
| GET | `/settings/api` | Required | Get settings JSON |
| PUT | `/settings/api` | Required | Update settings |
| POST | `/settings/upload-reddit-cache` | Required | Upload Reddit JSON |
| GET | `/settings/voice-notes` | Required | Get voice notes |
| PUT | `/settings/voice-notes` | Required | Update voice notes |
| GET | `/settings/voice-preview/{id}` | Required | Generate/get voice preview |

## 1.5 Services Architecture

### Reddit Service (`app/services/reddit.py`)
- Disk-cached Reddit API fetching with configurable TTL (default 1 week listings, 24h posts)
- Retry with exponential backoff (4 attempts, 2^n seconds)
- Stale cache fallback when Reddit is unreachable
- Series discovery via author page search with title similarity matching
- Multi-part story concatenation via next-part link following

### Script Adapter (`app/services/script_adapter.py`)
- Claude Sonnet integration for story→script transformation
- System prompt: horror audio drama director persona
- Auto-splitting for long stories (12K char sections, paragraph boundaries)
- Truncation detection and automatic re-splitting
- Character definition carryover across series parts
- Output: NarrationScript with characters, segments (narration/dialogue/SFX/ambient/pause)

### ElevenLabs Service (`app/services/elevenlabs.py`)
- TTS generation with sentence-boundary chunking (4,900 char limit)
- 4 horror-tuned voice presets (horror_narrator, horror_dialogue, whisper, calm)
- SFX generation from text descriptions with hash-based caching
- Voice preview generation and caching
- Models: eleven_multilingual_v2, eleven_v3

### Narration Generator (`app/services/narration_generator.py`)
- Orchestrates segment generation: consecutive same-character merging → cache check → TTS/SFX generation → audio mixing
- Persistent segment cache (SHA-256 of content+voice+preset → MP3 file)
- Tone-to-preset mapping (panicked→horror_dialogue, quiet→whisper, calm→calm)

### Audio Mixer (`app/services/audio_mixer.py`)
- Timeline-based audio composition
- Voice track with crossfades (100ms) and scene pauses (1,800ms)
- Ambient bed layered underneath (-20 dB)
- SFX overlaid on top (-6 dB)
- Intro fade (2,500ms) and outro fade (3,500ms)
- Loudness normalization to -18 dBFS

### Voice Pool (`app/services/voice_pool.py`)
- 30+ curated ElevenLabs voices with gender, age, archetype tags, and role (`"narrator"` or `"character"`)
- Narrator voices use `eleven_multilingual_v2` model for richer delivery; character voices use `eleven_v3`
- Profile-based scoring (gender match: +10/-20, age: +5, keyword overlap: +2 each)
- Random jitter for tie-breaking variety
- Pre-assigned voice_id passthrough

### Text Cleaner (`app/services/text_cleaner.py`)
- Pipeline: navigation blocks → meta lines → markdown→prose → whitespace normalization
- Removes: Part X links, edit notes, disclaimers, warnings, Reddit formatting artifacts

### Winks (`app/services/winks.py`)
- ElevenLabs character quota tracking mapped to 0-40 "Winks" scale
- Subscription info cached 5 min (1 min on failure)
- Per-story and batch cost estimation

## 1.6 Frontend Architecture

### SPA Router (`app/static/js/router.js`)
- Intercepts internal link clicks, fetches pages via AJAX
- Swaps `#page-content` and `#page-styles` only (preserves persistent audio)
- Re-executes `<script>` tags in fetched HTML
- Supports browser back/forward via `popstate`
- Custom events: `page:unload`, `page:load`

### Player Core (`app/static/js/player-core.js`)
- Single persistent `<audio>` element surviving navigation
- Event emitter pattern (trackchange, play, pause, timeupdate, ended, speedchange)
- Auto-save position every 15s via `navigator.sendBeacon`
- MediaSession API integration (lock-screen controls, metadata)
- Speed control (0.5x-3x) persisted in localStorage
- Track restoration from localStorage on page reload

### Playlist Manager (`app/static/js/playlist.js`)
- Queue operations: addNext, addToEnd, removeAt, reorder, playAt, clear
- Repeat modes: off → all → one (cycle)
- Auto-advance on track end, auto-replay for repeat-one
- Full state persisted in localStorage

### Design System (CSS in `base.html`)
- Dark theme: #050505 base, red accent (#a02020), semi-transparent surfaces
- Fonts: Cormorant Garamond (serif, elegant) + Inter (sans-serif)
- 3-layer fog animation system (18s, 12s, 7s cycles)
- Mini-player bar (fixed bottom, 56px)
- Playlist drawer (bottom sheet, drag-to-reorder via SortableJS)
- Toast notifications with auto-dismiss
- Film grain and vignette decorative overlays

### Pages (10 templates)
1. **base.html** — Master layout, design system, mini-player, playlist drawer, fog effects
2. **story_list.html** — Home: recently viewed, folders, story cards with action menus
3. **story_detail.html** — Pipeline controls (fetch→script→audio), stats, series
4. **submit.html** — Browse top stories + manual entry popout
5. **player.html** — Full player: EQ visualizer, controls, speed, queue, series
6. **script_editor.html** — Edit characters, voices, segments inline
7. **reader.html** — Text reader with scroll progress, drop caps
8. **settings.html** — Reddit cache + voice library tabs
9. **login.html** — Auth form
10. **folder.html** — Folder view with story list

### PWA
- Service worker (minimal: skipWaiting + claim, no caching strategy)
- Manifest: standalone, dark theme, 192/512 icons
- Apple mobile web app meta tags
- MediaSession for lock-screen playback controls

## 1.7 Caching Architecture (4 layers)
1. **Segment Cache** (`./data/segment_cache/`) — Generated TTS/SFX MP3s by content hash
2. **SFX Cache** (`./data/sfx_cache/`) — Sound effects by description hash
3. **Voice Preview Cache** (`./data/voice_previews/`) — Voice samples by voice_id
4. **Reddit Cache** (`data/reddit_cache/`) — API responses by URL hash, TTL-based

## 1.8 Testing (27 test files, ~10K lines)
- Full pytest suite covering all routers, services, schemas, templates
- All external APIs mocked at import site
- In-memory SQLite for test isolation
- Fixtures: db_session, client, test_user, admin_user, auth_headers, sample_story
- Rate limiter state cleared between tests

## 1.9 Deployment
- Docker: python:3.11-slim + ffmpeg
- docker-compose with optional Cloudflare Tunnel profile
- deploy.sh: interactive setup (API keys, JWT secret gen, admin user creation)
- Volumes: db, stories, sfx_cache, voice_previews

## 1.10 Current Weaknesses

| Area | Problem |
|------|---------|
| **Frontend** | No component system, no build tooling, no TypeScript, CSS-in-HTML (660+ lines), custom SPA router is fragile |
| **State Management** | Scattered localStorage, no centralized store, no reactivity |
| **Database** | No migrations (custom ALTER TABLE hack), no relationships defined, JSON blobs for structured data |
| **API Design** | Mixed REST/RPC, inconsistent response shapes, no versioning |
| **Error Handling** | Basic try/catch, no structured error responses, no retry logic for long operations |
| **Testing** | No CI/CD, no integration tests with real audio, no E2E tests |
| **Code Organization** | Business logic in routers, services are procedural, no dependency injection beyond FastAPI |
| **Async** | Synchronous everywhere despite FastAPI's async support — blocks on long API calls |
| **Observability** | Basic logging only, no metrics, no health checks |
| **Security** | In-memory rate limiting (lost on restart), no CSRF, minimal input sanitization |

---

# PART 2: RECOMMENDED MODERN TECH STACK

## 2.1 Recommended Stack Summary

| Layer | Current | Recommended | Why |
|-------|---------|-------------|-----|
| **Backend Framework** | FastAPI | **Django 5.x** | Batteries-included: ORM with migrations, admin panel, auth, form validation, mature ecosystem |
| **API Layer** | Implicit Pydantic schemas | **Django Ninja** | FastAPI-like syntax (Pydantic, type hints, auto-OpenAPI) on top of Django — easiest migration path from current FastAPI code |
| **ORM / DB** | SQLAlchemy + SQLite (no migrations) | **Django ORM + SQLite** (with PostgreSQL option) | Built-in migrations, admin, queryset API, well-documented patterns |
| **Task Queue** | Synchronous (blocks during generation) | **Django Q2** | Uses Django ORM as broker — no Redis needed. Trivial setup for self-hosted. Django 6.0 may ship built-in tasks. |
| **Frontend Framework** | Vanilla JS + Jinja2 | **Vue 3 + Vite** | `<keep-alive>` makes persistent audio trivial, SFCs, gentle learning curve, best docs of the three major frameworks |
| **State Management** | Scattered localStorage | **Pinia** (Vue's official store) | Centralized, reactive, lives outside component tree (persists across navigation), localStorage plugin |
| **Styling** | CSS-in-HTML (660 lines) | **Tailwind CSS v4** | Zero-config (Oxide engine), CSS-first `@theme` tokens, container queries for responsive player, first-party Vite plugin |
| **TypeScript** | None | **TypeScript** | Type safety for API contracts, component props, audio player state |
| **Build System** | None | **Vite** | Fast HMR, TypeScript support, optimized builds, Vue ecosystem standard |
| **Testing (Backend)** | pytest (good) | **pytest + Django test client** | Keep pytest, gain Django's test utilities, factory_boy for fixtures |
| **Testing (Frontend)** | None | **Vitest + Vue Test Utils + Playwright** | Unit tests for components, E2E for critical flows |
| **Linting** | None | **Ruff (Python) + ESLint + Prettier (JS/TS)** | Fast, opinionated, catches bugs |
| **CI/CD** | None | **GitHub Actions** | Automated test runs, Docker builds, deployment |

### Research Sources
- [JetBrains: Django, Flask, or FastAPI (2025)](https://blog.jetbrains.com/pycharm/2025/02/django-flask-fastapi/)
- [Better Stack: FastAPI vs Django vs Flask](https://betterstack.com/community/guides/scaling-python/fastapi-vs-django-vs-flask/)
- [Merge.rocks: Svelte vs React vs Vue 2025](https://merge.rocks/blog/comparing-front-end-frameworks-for-startups-in-2025-svelte-vs-react-vs-vue)
- [Tailwind CSS v4.0 Official Blog](https://tailwindcss.com/blog/tailwindcss-v4)
- [Loopwerk: Django Task Queues](https://www.loopwerk.io/articles/2025/django-task-queues/)

## 2.2 Backend: Django 5.x

### Why Django over FastAPI/Litestar

FastAPI is excellent for pure APIs, but Voice In The Dark is a **full-stack application** with:
- Server-rendered pages (story detail, settings, script editor)
- File management (audio files, caches)
- Admin operations (user management, story inspection)
- Database relationships and migrations
- Session/auth management
- Background task orchestration

Django provides all of this out of the box:

| Need | Django | FastAPI |
|------|--------|---------|
| Database migrations | `manage.py migrate` (built-in) | Alembic (separate setup) |
| Admin panel | `admin.site.register(Story)` | Build from scratch |
| Auth system | `django.contrib.auth` | Roll your own JWT |
| Form validation | Django forms/serializers | Pydantic (good, but no admin) |
| File handling | `FileField`, storage backends | Manual `os.path` management |
| Background tasks | django-q2, celery integration | Manual thread/process management |
| Testing | TestCase, Client, fixtures | TestClient (good, but less batteries) |
| Security | CSRF, XSS, SQL injection protection | Manual middleware setup |

### Django Project Structure
```
voice_in_the_dark/
├── manage.py
├── config/                      # Project settings
│   ├── settings/
│   │   ├── base.py              # Shared settings
│   │   ├── development.py       # Dev overrides
│   │   └── production.py        # Production overrides
│   ├── urls.py                  # Root URL config
│   └── wsgi.py
├── apps/
│   ├── accounts/                # User auth & profiles
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── tests/
│   ├── stories/                 # Story CRUD, folders, views
│   │   ├── models.py            # Story, StoryFolder, StoryView, etc.
│   │   ├── views.py             # API viewsets
│   │   ├── schemas.py           # Pydantic schemas (reuse existing)
│   │   ├── services/            # Business logic
│   │   │   ├── reddit.py
│   │   │   ├── text_cleaner.py
│   │   │   └── series_detector.py
│   │   ├── tasks.py             # Background tasks
│   │   ├── urls.py
│   │   └── tests/
│   ├── audio/                   # Script gen, narration, mixing
│   │   ├── models.py            # NarrationScript, Segment models
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── services/
│   │   │   ├── script_adapter.py
│   │   │   ├── elevenlabs.py
│   │   │   ├── narration_generator.py
│   │   │   ├── audio_mixer.py
│   │   │   ├── voice_pool.py
│   │   │   └── segment_cache.py
│   │   ├── tasks.py             # Long-running generation tasks
│   │   ├── urls.py
│   │   └── tests/
│   └── player/                  # Playback state, streaming
│       ├── models.py            # PlaybackState
│       ├── views.py             # Stream, download, position
│       ├── urls.py
│       └── tests/
├── frontend/                    # Vue 3 SPA (see §2.3)
├── templates/                   # Django templates (minimal - just SPA shell)
├── static/                      # Collected static files
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

### Key Django Patterns to Adopt

**Models with proper relationships:**
```python
# Instead of JSON blobs, use proper relational models
class NarrationScript(models.Model):
    story = models.OneToOneField(Story, on_delete=models.CASCADE)
    title = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

class Character(models.Model):
    script = models.ForeignKey(NarrationScript, related_name='characters', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    voice_profile = models.TextField()
    voice_id = models.CharField(max_length=100, blank=True)

class ScriptSegment(models.Model):
    script = models.ForeignKey(NarrationScript, related_name='segments', on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    type = models.CharField(max_length=20, choices=SegmentType.choices)
    character = models.ForeignKey(Character, null=True, blank=True, on_delete=models.SET_NULL)
    text = models.TextField(blank=True)
    tone = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    loop = models.BooleanField(default=False)
```

**Background tasks for long operations:**
```python
# Instead of blocking the request for 2-5 minutes during audio generation:
from django_q.tasks import async_task

class GenerateNarrationView(APIView):
    def post(self, request):
        task_id = async_task(
            'apps.audio.tasks.generate_narration',
            story_id=request.data['story_id'],
            voice_map=request.data.get('voice_map'),
        )
        return Response({'task_id': task_id, 'status': 'queued'})
```

**Admin panel (free):**
```python
@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'has_audio', 'created_at']
    search_fields = ['title', 'author']
    list_filter = ['created_at']
```

## 2.3 Frontend: Vue 3 + Vite + TypeScript

### Why Vue 3

The persistent audio player is the critical constraint. The app needs:
1. An **app shell** that never unmounts (houses `<audio>`, mini-player, playlist drawer)
2. **Client-side routing** that swaps page content without destroying the shell
3. **Reactive state** that updates the mini-player when tracks change
4. **Rich interactivity** for the script editor, queue management, speed control

Vue 3 is the best fit because:

| Requirement | Vue 3 | React | Svelte | HTMX+Alpine |
|-------------|-------|-------|--------|-------------|
| Persistent audio across navigation | `<RouterView>` inside app shell — `<audio>` in App.vue never unmounts | Same pattern with React Router, but heavier | Same with SvelteKit, but smaller ecosystem | Very difficult — requires manual DOM preservation |
| Component reactivity | Composition API, reactive refs | hooks, useState | Stores, reactive declarations | Alpine.js x-data (limited) |
| Script editor (complex forms) | v-model, computed, watchers | Controlled components (more boilerplate) | bind:value | Not suited for complex state |
| Drag-and-drop | vue-draggable-next (wrapper for SortableJS) | react-beautiful-dnd | svelte-dnd-action | SortableJS directly |
| Learning curve | Moderate, excellent docs | Moderate | Low | Low but ceiling is low |
| TypeScript | First-class support | First-class | First-class | Limited |
| Bundle size | ~33KB gzipped | ~42KB gzipped | ~2KB (but grows per component) | ~15KB |
| Ecosystem maturity | Very mature, large community | Largest ecosystem | Growing but smaller | Very small |

### Vue App Architecture
```
frontend/
├── src/
│   ├── App.vue                   # App shell: <audio>, mini-player, playlist drawer, fog
│   ├── main.ts                   # App entry, router, pinia
│   ├── router/
│   │   └── index.ts              # Vue Router routes
│   ├── stores/
│   │   ├── player.ts             # Audio player state (Pinia)
│   │   ├── playlist.ts           # Queue management (Pinia)
│   │   ├── auth.ts               # User auth state (Pinia)
│   │   └── notifications.ts      # Toast notifications (Pinia)
│   ├── composables/
│   │   ├── useMediaSession.ts    # MediaSession API integration
│   │   ├── usePlaybackSave.ts    # Auto-save position to server
│   │   └── useApi.ts             # Typed API client (fetch wrapper)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── MiniPlayer.vue
│   │   │   ├── PlaylistDrawer.vue
│   │   │   ├── FogOverlay.vue
│   │   │   ├── AuthNav.vue
│   │   │   └── ToastContainer.vue
│   │   ├── stories/
│   │   │   ├── StoryCard.vue
│   │   │   ├── StoryList.vue
│   │   │   ├── FolderNav.vue
│   │   │   └── SeriesParts.vue
│   │   ├── player/
│   │   │   ├── FullPlayer.vue
│   │   │   ├── EqVisualizer.vue
│   │   │   ├── ProgressBar.vue
│   │   │   ├── SpeedControl.vue
│   │   │   └── PlayerControls.vue
│   │   ├── editor/
│   │   │   ├── ScriptEditor.vue
│   │   │   ├── CharacterPanel.vue
│   │   │   ├── SegmentCard.vue
│   │   │   └── VoiceSelector.vue
│   │   └── common/
│   │       ├── Badge.vue
│   │       ├── Button.vue
│   │       ├── Spinner.vue
│   │       └── Modal.vue
│   ├── pages/
│   │   ├── StoryListPage.vue
│   │   ├── StoryDetailPage.vue
│   │   ├── SubmitPage.vue
│   │   ├── PlayerPage.vue
│   │   ├── ReaderPage.vue
│   │   ├── ScriptEditorPage.vue
│   │   ├── SettingsPage.vue
│   │   ├── FolderPage.vue
│   │   └── LoginPage.vue
│   ├── api/
│   │   ├── client.ts             # Base API client with auth
│   │   ├── stories.ts            # Story API calls
│   │   ├── audio.ts              # Audio API calls
│   │   ├── auth.ts               # Auth API calls
│   │   └── settings.ts           # Settings API calls
│   ├── types/
│   │   ├── story.ts              # TypeScript interfaces matching DRF serializers
│   │   ├── narration.ts
│   │   └── player.ts
│   └── assets/
│       └── css/
│           └── tailwind.css      # Tailwind entry point
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
└── package.json
```

### Persistent Audio Pattern in Vue
```vue
<!-- App.vue — never unmounts -->
<template>
  <div id="app" class="min-h-screen bg-[#050505]">
    <FogOverlay />

    <!-- Page content changes, everything else persists -->
    <RouterView />

    <!-- These persist across all navigation -->
    <MiniPlayer />
    <PlaylistDrawer />
    <ToastContainer />

    <!-- The persistent audio element -->
    <audio ref="audioEl" />
  </div>
</template>
```

## 2.4 Styling: Tailwind CSS 4

### Why Tailwind
- **Dark mode**: Built-in `dark:` variant (or default class strategy)
- **Design tokens**: Define your color palette, fonts, spacing in `tailwind.config.ts`
- **No CSS-in-HTML**: Utility classes in templates, custom components via `@apply`
- **Purging**: Only ships CSS you actually use
- **Animations**: `@keyframes` in config for fog, EQ visualizer, glitch effects

### Design Token Configuration
```ts
// tailwind.config.ts
export default {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: '#050505',
        surface: {
          DEFAULT: 'rgba(255,255,255,0.03)',
          hover: 'rgba(255,255,255,0.045)',
          active: 'rgba(255,255,255,0.055)',
        },
        accent: { DEFAULT: '#a02020', hover: '#bf2626' },
        success: '#3a7d5c',
        info: '#6868b8',
        warn: '#b8a040',
        ambient: '#48b8b8',
      },
      fontFamily: {
        serif: ['Cormorant Garamond', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
}
```

## 2.5 State Management: Pinia

```ts
// stores/player.ts
export const usePlayerStore = defineStore('player', () => {
  const audioEl = ref<HTMLAudioElement | null>(null)
  const currentTrack = ref<Track | null>(null)
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const duration = ref(0)
  const speed = ref(1.0)

  // Auto-persisted to localStorage via pinia-plugin-persistedstate
  const persistedSpeed = ref(1.0)

  function loadTrack(track: Track) { /* ... */ }
  function togglePlay() { /* ... */ }
  function seek(time: number) { /* ... */ }
  function setSpeed(rate: number) { /* ... */ }

  return { currentTrack, isPlaying, currentTime, duration, speed, loadTrack, togglePlay, seek, setSpeed }
}, {
  persist: { paths: ['persistedSpeed'] }
})
```

## 2.6 Background Task Queue

Audio generation takes 2-5+ minutes. Currently this blocks the HTTP request. With Django Q2 or Celery:

1. Frontend sends POST to start generation → gets back a `task_id`
2. Frontend polls `/api/tasks/{task_id}/status` every 2-3 seconds (or uses WebSocket)
3. Backend worker processes the task asynchronously
4. Status updates: `queued → processing → mixing → complete` (or `failed`)
5. Frontend shows progress bar with stage information

**Recommended: Django Q2** — simpler than Celery for small deployments, uses the Django ORM as its broker (no Redis or RabbitMQ container needed). Setup takes under an hour. Note: Django 6.0 (expected late 2025/2026) may ship a built-in task framework, which could eliminate this third-party dependency entirely.

## 2.7 Build & Dev Tools

| Tool | Purpose |
|------|---------|
| **Vite** | Frontend dev server with HMR, production bundling |
| **TypeScript** | Type safety for API contracts, component props, stores |
| **Ruff** | Python linting + formatting (replaces flake8, black, isort) |
| **ESLint + Prettier** | JS/TS linting + formatting |
| **mypy** | Python type checking |
| **pre-commit** | Run linters on git commit |
| **pytest** | Backend tests (keep existing patterns) |
| **Vitest** | Frontend unit tests |
| **Playwright** | E2E tests for critical flows |

## 2.8 DevOps

### Docker Multi-Stage Build
```dockerfile
# Stage 1: Build frontend
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/ .
RUN npm ci && npm run build

# Stage 2: Python app
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg
COPY --from=frontend /app/frontend/dist /app/static/dist
COPY . /app
RUN pip install -r requirements.txt
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8010"]
```

### GitHub Actions CI/CD
```yaml
# On push: lint → test → build → (optional) deploy
- Ruff lint + mypy check
- pytest backend tests
- npm run lint + vitest frontend tests
- Docker build
- Playwright E2E (optional)
```

### Database Migrations in Deployment
```bash
# deploy.sh
docker exec app python manage.py migrate --noinput
```

## 2.9 API Layer: Django Ninja

Django Ninja is the recommended API layer because it uses **the same patterns as FastAPI** (Pydantic schemas, type hints, path/query params, dependency injection), making migration from the current codebase significantly easier:

```python
# Current FastAPI code:
@router.post("/submit")
async def submit_story(req: StorySubmitRequest, user: User = Depends(get_current_user)):
    ...

# Django Ninja equivalent (nearly identical):
@router.post("/submit")
def submit_story(request, payload: StorySubmitRequest, user=Depends(get_current_user)):
    ...
```

Key features:
- **Pydantic schemas** — Reuse existing Pydantic models (StorySubmitRequest, NarrationScript, etc.) directly
- **Auto-generated OpenAPI** — Swagger/Redoc at `/api/docs/`
- **Type-hint routing** — Same DI pattern as FastAPI (`Depends()`)
- **Django auth integration** — `django.contrib.auth` + JWT via `django-ninja-jwt`
- **Throttling** — Django's built-in rate limiting (persistent, database-backed)
- **Pagination** — Built-in paginated responses

## 2.10 Data Migration Script (Preserving Existing Content)

### Critical Requirement
All existing stories, generated narrations, sound effects, voice previews, and user data MUST be preserved during the rebuild. Most generated files are untracked by git (see `.gitignore`) and live only on the deployed server.

### Data Inventory (all under `./data/`, gitignored)

| Directory | Contents | Preservation Strategy |
|-----------|----------|----------------------|
| `./data/db/horror_narrator.db` | SQLite database (users, stories, playback states, views, folders, settings) | Direct SQL migration script |
| `./data/stories/*.mp3` | Generated final audio mixes | Copy files, update paths in new DB |
| `./data/sfx_cache/*.mp3` | Cached sound effects (keyed by description hash) | Copy directory wholesale |
| `./data/segment_cache/*.mp3` | Cached TTS/SFX segments (keyed by content+voice hash) | Copy directory wholesale |
| `./data/voice_previews/*.mp3` | Voice sample previews (keyed by voice_id) | Copy directory wholesale |
| `./data/reddit_cache/*.json` | Cached Reddit API responses (keyed by URL hash) | Copy directory wholesale |

### Migration Script Plan

The migration script (`scripts/migrate_from_v1.py`) will:

1. **Read the old SQLite database** directly using `sqlite3` module:
   ```python
   # Connect to old DB
   old_db = sqlite3.connect('./data/db/horror_narrator.db')
   old_db.row_factory = sqlite3.Row
   ```

2. **Migrate users** → new Django `User` model:
   - Map `username`, `password_hash`, `is_admin`
   - Bcrypt hashes are portable — Django's `BCryptPasswordHasher` reads them directly
   - Preserve user IDs to maintain foreign key integrity

3. **Migrate stories** → new Django `Story` model:
   - Port all fields: title, reddit_url, text_content, narration_text, content_hash, author, part_count
   - **Denormalize script_json**: Parse the JSON blob and create proper relational records:
     - `NarrationScript` row linked to Story
     - `Character` rows for each character in the script
     - `ScriptSegment` rows for each segment (preserving order)
   - **Update audio_file_path**: Remap from old `./data/stories/{uuid}.mp3` to new path structure
   - Port `series_json` as-is (or parse into proper series relationship)

4. **Migrate playback states** → new Django `PlaybackState` model:
   - Direct mapping: user_id, story_id, position_seconds

5. **Migrate story views** → new Django `StoryView` model:
   - Direct mapping: user_id, story_id, viewed_at, hidden

6. **Migrate folders** → new Django `StoryFolder` + `StoryFolderMembership`:
   - Direct mapping with preserved IDs

7. **Migrate app settings** → new Django `AppSetting` or `django.conf.settings`:
   - Port reddit_cache_ttl, voice_notes, and any other key-value pairs

8. **Copy file-based caches** (no transformation needed):
   ```bash
   cp -r ./data/stories/ ./new_project/data/stories/
   cp -r ./data/sfx_cache/ ./new_project/data/sfx_cache/
   cp -r ./data/segment_cache/ ./new_project/data/segment_cache/
   cp -r ./data/voice_previews/ ./new_project/data/voice_previews/
   cp -r ./data/reddit_cache/ ./new_project/data/reddit_cache/
   ```

9. **Verify migration**:
   - Count records in old vs new DB (should match exactly)
   - Verify all referenced audio files exist on disk
   - Test playback of migrated stories
   - Test login with migrated users

### Docker Volume Mapping (current)
```yaml
volumes:
  - ./data/db:/app/data/db
  - ./data/stories:/app/data/stories
  - ./data/sfx_cache:/app/data/sfx_cache
  - ./data/voice_previews:/app/data/voice_previews
```
Note: `segment_cache` and `reddit_cache` are NOT volume-mapped currently. They live inside the container and would be lost on rebuild. The migration script should extract them from the running container before proceeding: `docker cp voice-to-the-dark:/app/data/segment_cache ./data/segment_cache`

## 2.11 Migration Path (Phased Rebuild)

The rebuild should be incremental, not big-bang. Each phase is independently deployable:

### Phase 1: Project Skeleton & Tooling
- [ ] Initialize Django project with split settings (base/dev/prod)
- [ ] Set up Vue 3 + Vite + TypeScript in `frontend/` directory
- [ ] Configure Tailwind CSS v4 with dark theme design tokens
- [ ] Set up Ruff, ESLint, Prettier, pre-commit hooks
- [ ] Docker multi-stage build (Node frontend build → Python app)
- [ ] GitHub Actions CI pipeline (lint + test)

### Phase 2: Database Models & Data Migration
- [ ] Define Django models for Story, User, PlaybackState, StoryView, StoryFolder, StoryFolderMembership, AppSetting
- [ ] Properly model NarrationScript, Character, ScriptSegment as relational tables (not JSON blobs)
- [ ] Create initial Django migration
- [ ] Write and test `scripts/migrate_from_v1.py` against a copy of production data
- [ ] Verify all data integrity after migration

### Phase 3: Port Services (Framework-Agnostic Python)
- [ ] Port `reddit.py` — minimal changes (pure Python, no framework dependency)
- [ ] Port `text_cleaner.py` — zero changes needed
- [ ] Port `script_adapter.py` — update model references, keep Claude integration
- [ ] Port `elevenlabs.py` — update file path constants
- [ ] Port `narration_generator.py` — update model references
- [ ] Port `audio_mixer.py` — zero changes needed
- [ ] Port `voice_pool.py` — zero changes needed
- [ ] Port `segment_cache.py` — update path constants
- [ ] Port `winks.py` — zero changes needed
- [ ] Port `hashing.py`, `audio_utils.py` — zero changes needed
- [ ] Port existing pytest tests (update imports/fixtures)

### Phase 4: API Layer (Django Ninja)
- [ ] Set up Django Ninja with JWT auth (django-ninja-jwt)
- [ ] Port auth endpoints (register, login, logout, me)
- [ ] Port story endpoints (submit, list, detail, series, playback, folders)
- [ ] Port audio endpoints (generate-script, script CRUD, generate-narration)
- [ ] Port settings endpoints (cache TTL, voice notes, voice preview)
- [ ] Port streaming endpoint (HTTP Range support)
- [ ] Set up rate limiting (Django's built-in throttling)
- [ ] Register Story, User in Django admin

### Phase 5: Vue Frontend (Page by Page)
- [ ] App shell: `App.vue` with persistent `<audio>`, mini-player, playlist drawer, fog overlay
- [ ] Pinia stores: player, playlist, auth, notifications
- [ ] Vue Router with all routes
- [ ] Login page
- [ ] Story list / home page (recently viewed, folders)
- [ ] Story detail page (pipeline controls, stats, series)
- [ ] Submit page (browse top + manual entry)
- [ ] Audio player page (full controls, EQ visualizer)
- [ ] Script editor page (characters, segments, voices)
- [ ] Reader page (text display, scroll progress)
- [ ] Settings page (cache TTL, voice library)
- [ ] Folder page
- [ ] PWA setup (service worker, manifest, MediaSession)

### Phase 6: Background Task Queue
- [ ] Set up Django Q2 with ORM broker
- [ ] Move script generation to background task with progress reporting
- [ ] Move audio generation to background task with stage updates (queued → generating segments → mixing → complete)
- [ ] Frontend polling or WebSocket for task status
- [ ] Frontend progress bar component

### Phase 7: Testing & Polish
- [ ] Port all existing pytest tests to Django test patterns
- [ ] Add Vitest unit tests for Vue components (player, playlist, editor)
- [ ] Add Playwright E2E tests for critical flows (submit → generate → play)
- [ ] Performance testing (audio streaming, concurrent generation)
- [ ] Mobile testing (PWA install, MediaSession, touch interactions)

### Phase 8: Deployment & Cutover
- [ ] Final data migration from production instance
- [ ] Swap Docker containers
- [ ] Verify all stories play correctly
- [ ] Verify all user sessions work
- [ ] Monitor for issues, keep old container as rollback

---

# PART 3: RECENT CHANGES (since last merged PR #79)

The following changes have been made since the last merged PR and should be reflected in the rebuild:

1. **Voice pool `role` attribute** (PR pending): `VoiceEntry` dataclass now has a `role` field (`"narrator"` or `"character"`). Narrator voices use `eleven_multilingual_v2` model; character voices use `eleven_v3`. This affects voice auto-assignment logic.
2. **Voice preview file path fix**: `generate_voice_preview` now writes directly to the cached path instead of using a temp file, and handles cleanup on failure.
3. **Docker voice_previews volume**: `voice_previews/` directory added to Dockerfile `mkdir` and `docker-compose.yml` volumes.
4. **Script adapter TODO**: A TODO exists in `script_adapter.py` to review and refine the system prompt for better performance — this should be addressed during the services port (Phase 3).

---

# PART 4: VERIFICATION

## How to validate this plan
1. **Documentation completeness**: Cross-reference Part 1 against every file in `app/` — all 50 endpoints, 12 services, 8 database tables, 10 templates, 3 JS modules should be accounted for
2. **Framework fit**: The Django + Vue 3 stack handles every current feature (persistent audio, SPA navigation, script editing, queue management, MediaSession, PWA)
3. **Migration feasibility**: Services are mostly pure Python functions — they port directly. Database models gain migrations. Frontend components map 1:1 to current templates.
4. **Data preservation**: Migration script covers all 6 data directories and 8 database tables. Volume-mapped data survives container rebuild; non-mapped data (segment_cache, reddit_cache) must be extracted first.

## Key files documenting current state (for reference during rebuild)
- `app/main.py` — App setup, router registration
- `app/routers/stories.py` (815 lines) — Largest router, most complex logic
- `app/routers/audio.py` (368 lines) — Generation pipeline
- `app/routers/player.py` (427 lines) — All HTML pages + streaming
- `app/services/script_adapter.py` (275 lines) — Claude integration
- `app/services/narration_generator.py` (278 lines) — Audio orchestration
- `app/services/audio_mixer.py` (271 lines) — Multi-track mixing
- `app/services/voice_pool.py` (323 lines) — Voice assignment (updated: now has `role` attribute)
- `app/services/reddit.py` (368 lines) — Reddit API + caching
- `app/static/js/player-core.js` — Persistent audio player
- `app/static/js/playlist.js` — Queue management
- `app/static/js/router.js` — Custom SPA router
- `app/templates/base.html` — Design system + 660 lines CSS
- `app/schemas/narration.py` — Script data structures
