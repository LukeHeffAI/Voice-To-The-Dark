# Voice To The Dark — Project Plan

**Voice To The Dark** transforms horror stories from r/nosleep into dramatically narrated audio productions — complete with multiple character voices, ambient soundscapes, and cinematic sound effects — ready to listen to like a horror podcast.

---

## Current State of the Repository

### What Exists

| File | Status | Notes |
|---|---|---|
| `app/config.py` | Functional | Loads `ELEVENLABS_API_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` from `.env` |
| `app/database.py` | Functional | SQLAlchemy + SQLite (`horror_narrator.db`) |
| `app/main.py` | Skeleton | FastAPI app created, but **routers are not registered** |
| `app/models/story.py` | Functional | `Story` model (id, title, reddit_url, text_content, audio_file_path) and `User` model (id, username, password_hash, is_admin) |
| `app/schemas/story.py` | Empty | No Pydantic schemas defined |
| `app/services/reddit.py` | Functional | Fetches top posts via PRAW, multi-part story detection with recursive link following, single-post fetch |
| `app/services/elevenlabs.py` | Functional | Basic TTS generation with text chunking (4900 char limit), audio stitching via pydub |
| `app/services/audio_utils.py` | Functional | Audio file stitching, temp folder management, cleanup utilities |
| `app/routers/audio.py` | Functional | `POST /generate-audio` — takes story_id + voice_id, generates audio, saves path to DB |
| `app/routers/stories.py` | Empty | No endpoints |
| `app/routers/auth.py` | Empty | No endpoints |
| `requirements.txt` | Empty | Dependencies not listed |

### What Works

- Reddit story fetching (single and multi-part) via PRAW
- Basic ElevenLabs TTS generation with chunking
- Audio file concatenation with pydub
- SQLite storage for stories and audio paths
- Audio generation endpoint (though the router isn't wired up)

### What Needs Improvement or Rework

1. **Text chunking is naive** — splits at a fixed character count, potentially mid-word or mid-sentence. Must split on sentence/paragraph boundaries.
2. **No dramatic adaptation** — stories are sent to TTS as raw Reddit text. No processing to make narration dramatic, remove Reddit-isms (e.g. "edit:", "update:", markdown formatting), or add pacing/tone cues.
3. **Single voice only** — no support for multiple character voices or narrator vs. dialogue distinction.
4. **No sound effects or ambient audio** — just flat speech with no atmosphere.
5. **No LLM integration** — no script adaptation layer to transform a written story into a performance-ready narration script.
6. **Routers not wired up** — `main.py` doesn't include any routers, so the API doesn't actually serve any endpoints.
7. **No requirements.txt** — dependencies aren't tracked.
8. **No local TTS fallback** — entirely dependent on ElevenLabs API.
9. **`_extract_reddit_links` returns tuples** — `re.findall` with groups returns a list of tuples, not strings. The multi-part logic will break.
10. **No error handling on the audio route** — DB session not properly managed (no dependency injection, no `finally` close).
11. **No frontend** — no way for a user to interact with the system beyond raw API calls.
12. **No tests** — nothing is tested.

---

## Architecture: The Narration Pipeline

The core of this project is a **5-stage pipeline** that transforms a Reddit URL into a fully produced audio narration:

```
[1. FETCH] → [2. ADAPT] → [3. GENERATE] → [4. MIX] → [5. DELIVER]
   Reddit       Claude        ElevenLabs     pydub       Web UI /
   story text   script        voice + SFX    mixing      file download
```

### Stage 1: Fetch (Reddit Extraction)

**Input:** r/nosleep URL (or browse/search for stories)
**Output:** Clean story text with metadata (title, author, part count)

- Fetch story text via PRAW (existing code, needs refinement)
- Handle multi-part stories (existing code, needs the regex bug fixed)
- Strip Reddit-specific formatting: "Edit:", "Update:", awards, markdown artifacts
- Extract metadata: title, author, word count, part indicators
- Store raw text in the database

### Stage 2: Adapt (LLM Script Generation)

**Input:** Clean story text
**Output:** Structured narration script (JSON)

This is the key differentiator — using Claude to transform a written story into a dramatic narration script. The LLM will:

- **Identify characters** and assign them distinct voice profiles (narrator, character A, character B, etc.)
- **Add dramatic direction** — pacing cues, emotional tone indicators, pause markers
- **Insert SFX cues** at appropriate moments (e.g., `[SFX: door creaking]`, `[SFX: thunder rumble]`, `[AMBIENT: rain on window]`)
- **Clean the text** — remove Reddit-isms, fix grammar, smooth transitions between multi-part stories
- **Structure the output** as a sequence of segments, each with a type (narration, dialogue, sfx, ambient, pause) and associated metadata

Example output structure:
```json
{
  "title": "The Thing in My Basement",
  "characters": {
    "narrator": { "voice_profile": "deep, steady, ominous" },
    "sarah": { "voice_profile": "young woman, anxious" }
  },
  "segments": [
    { "type": "ambient", "description": "quiet suburban night, crickets, distant wind" },
    { "type": "narration", "character": "narrator", "text": "I never should have gone down to the basement that night.", "tone": "foreboding" },
    { "type": "pause", "duration_ms": 1500 },
    { "type": "sfx", "description": "old wooden stairs creaking under weight" },
    { "type": "dialogue", "character": "sarah", "text": "Hello? Is someone down there?", "tone": "nervous, whispered" },
    { "type": "sfx", "description": "sharp metallic scraping sound" }
  ]
}
```

**LLM choice:** Claude API (via the Anthropic SDK). The prompt engineering for this stage is critical and will need iteration to get the right dramatic tone without being over-the-top.

### Stage 3: Generate (Voice & SFX Production)

**Input:** Structured narration script
**Output:** Individual audio files for each segment

Two sub-systems work here:

#### 3a. Voice Generation

**Primary: ElevenLabs API**
- Use **Eleven v3** (their most expressive model) for maximum dramatic quality
- Assign different ElevenLabs voices to different characters
- Use voice settings tuned for horror narration:
  - Stability: ~0.35-0.50 (lower for more emotional range)
  - Similarity Boost: ~0.75
  - Style Exaggeration: ~0.3-0.5 (more pronounced character)
- The text itself carries emotional cues that the model responds to, so the LLM-adapted script will naturally produce more dramatic output
- Chunk long narration segments at sentence boundaries (not mid-word)

**Fallback: Local TTS (RTX 4090)**
- **Primary local option: Orpheus TTS (3B)** — best for emotional/dramatic speech, supports laughing, crying, whispering. Fits comfortably in 24GB VRAM.
- **Alternative: Chatterbox TTS** — supports voice cloning (could clone a preferred narrator voice from a sample) and has paralinguistic tags (`[laugh]`, `[cough]`). Also tested on RTX 4090.
- The local fallback uses the same script format but maps voice settings differently
- Local TTS is useful for: saving ElevenLabs quota, iterating on scripts without API cost, offline usage

#### 3b. Sound Effects Generation

**Primary: ElevenLabs Sound Effects V2 API**
- Generate SFX from the text descriptions in the script (e.g., "old wooden stairs creaking")
- Supports clips up to 30 seconds, 48kHz professional audio
- Generate ambient loops with the `loop` parameter for continuous background atmosphere

**Fallback / Supplement: Pre-built SFX library**
- Maintain a local library of commonly-used horror SFX (rain, thunder, wind, creaking, footsteps, etc.)
- Cache generated SFX for reuse across stories (a "door creak" doesn't need to be regenerated every time)
- The SFX cache saves API calls and ensures consistency

### Stage 4: Mix (Audio Production)

**Input:** Individual voice segments, SFX clips, ambient loops
**Output:** Single mixed audio file (MP3)

- Layer ambient audio underneath narration at reduced volume
- Insert SFX at the correct positions with appropriate volume levels
- Add crossfades between segments for smooth transitions
- Insert silence/pauses as specified in the script
- Add a subtle intro (fade-in of ambient) and outro (fade-out)
- Normalize audio levels across the entire production
- Use **pydub** (already a dependency) for all mixing operations — it handles overlaying, volume adjustment, crossfades, and export

### Stage 5: Deliver

**Input:** Final mixed audio file
**Output:** Playable/downloadable audio accessible via the web UI

- Store the final audio file and associate it with the story record in the database
- Serve via FastAPI static files or a streaming endpoint
- Provide download option
- Display story metadata (title, author, duration, word count)

---

## Implementation Plan — Phased Approach

### Phase 1: Fix Foundations

Get the existing code working correctly before adding new features.

- [ ] **1.1** Populate `requirements.txt` with all dependencies (fastapi, uvicorn, sqlalchemy, praw, requests, pydub, python-dotenv, anthropic, elevenlabs)
- [ ] **1.2** Wire up routers in `main.py` (audio, stories, auth)
- [ ] **1.3** Fix `_extract_reddit_links` regex bug (returns tuples instead of strings)
- [ ] **1.4** Add proper FastAPI dependency injection for DB sessions (replace manual `SessionLocal()` calls)
- [ ] **1.5** Improve text chunking to split on sentence boundaries instead of fixed character count
- [ ] **1.6** Add text cleaning to strip Reddit formatting artifacts from story text
- [ ] **1.7** Define Pydantic schemas for story creation, response, and audio generation
- [ ] **1.8** Implement stories router: endpoints to submit a URL, list stories, get story by ID, delete a story
- [ ] **1.9** Add `.env.example` with required environment variable names
- [ ] **1.10** Add `ANTHROPIC_API_KEY` to config settings

### Phase 2: Script Adaptation Engine (Claude Integration)

The LLM-powered transformation from raw text to dramatic narration script.

- [ ] **2.1** Design the narration script JSON schema (segment types, character definitions, SFX cues, tone markers)
- [ ] **2.2** Create `app/services/script_adapter.py` — the Claude API integration that transforms story text into a narration script
- [ ] **2.3** Craft and iterate on the system prompt for dramatic horror narration adaptation
- [ ] **2.4** Handle long stories that exceed Claude's output limits — process in sections, maintain continuity
- [ ] **2.5** Store the generated script in the database (add a `script_json` column to the Story model)
- [ ] **2.6** Add an endpoint to trigger script generation and retrieve/preview the script
- [ ] **2.7** Allow manual script editing (so the user can tweak character assignments, add/remove SFX cues, etc. before generating audio)

### Phase 3: Enhanced Audio Generation

Upgrade from flat TTS to dramatic multi-voice + SFX production.

- [ ] **3.1** Upgrade ElevenLabs integration to use Eleven v3 model with voice settings tuned for horror
- [ ] **3.2** Implement voice mapping — assign ElevenLabs voice IDs to characters defined in the script
- [ ] **3.3** Create `app/services/sfx_generator.py` — ElevenLabs Sound Effects V2 integration for generating SFX from text descriptions
- [ ] **3.4** Implement SFX caching — store generated SFX by description hash, reuse across stories
- [ ] **3.5** Create `app/services/audio_mixer.py` — takes all generated segments and mixes them into a single production:
  - Layer ambient audio under narration
  - Insert SFX at correct positions
  - Apply crossfades, pauses, volume normalization
  - Add intro/outro fades
- [ ] **3.6** Refactor `generate_audio` to orchestrate the full pipeline: script → voice segments → SFX → mix → final file
- [ ] **3.7** Add a voice/character configuration system (map character profiles to specific ElevenLabs voice IDs, store preferred voices)

### Phase 4: Local TTS Fallback

Add local TTS support for the RTX 4090 as an alternative to ElevenLabs.

- [ ] **4.1** Integrate Orpheus TTS (3B) as the primary local TTS engine
- [ ] **4.2** Create `app/services/local_tts.py` with a common interface matching the ElevenLabs service
- [ ] **4.3** Add a TTS provider selection mechanism (ElevenLabs vs. local) configurable per generation or globally
- [ ] **4.4** Optionally integrate Chatterbox for voice cloning capability (clone a preferred narrator voice from an audio sample)
- [ ] **4.5** Test and tune local model voice settings for horror narration quality

### Phase 5: Frontend

Build a simple, functional web UI.

- [ ] **5.1** Choose frontend approach (recommend: simple server-rendered templates with HTMX, or a lightweight React/Svelte SPA)
- [ ] **5.2** Story submission page: paste a nosleep URL, see story preview, trigger narration
- [ ] **5.3** Story browser: list stored stories with status (fetched, scripted, narrated), filter by top/recent
- [ ] **5.4** Narration player: in-browser audio player with download option
- [ ] **5.5** Script preview/editor: view the generated narration script, tweak character assignments and SFX cues before audio generation
- [ ] **5.6** Voice configuration page: select/preview ElevenLabs voices for each character role
- [ ] **5.7** Pipeline status: show progress as a story moves through fetch → adapt → generate → mix stages

### Phase 6: Auth & Security

Lock it down so only you (and your girlfriend) can use it.

- [ ] **6.1** Implement simple authentication (recommend: basic username/password with JWT tokens — no need for OAuth complexity for 1-2 users)
- [ ] **6.2** Protect all API routes with auth middleware
- [ ] **6.3** Add rate limiting to prevent accidental API abuse
- [ ] **6.4** Ensure API keys are never exposed to the frontend

### Phase 7: Testing & Polish

- [ ] **7.1** Write unit tests for text cleaning, chunking, and script parsing
- [ ] **7.2** Write integration tests for the narration pipeline (mock external APIs)
- [ ] **7.3** Add logging throughout the pipeline for debugging
- [ ] **7.4** Add error recovery — if a stage fails, allow retrying from that stage instead of starting over
- [ ] **7.5** Add audio quality presets (quick draft vs. full production)

### Phase 8: Deployment (Optional)

- [ ] **8.1** Dockerize the application
- [ ] **8.2** Set up for deployment (self-hosted or cloud) — since the RTX 4090 is local, a local deployment may be preferable
- [ ] **8.3** Configure HTTPS if exposing externally

---

## Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| **Backend** | FastAPI (Python) | Already in use, async-friendly, good for streaming audio |
| **Database** | SQLite → PostgreSQL (if needed) | SQLite is fine for single-user, upgrade if deploying |
| **Reddit API** | PRAW | Already in use, works well |
| **Script Adaptation** | Claude API (Anthropic SDK) | Best at creative writing tasks, structured output, long context |
| **Primary TTS** | ElevenLabs (Eleven v3) | Most expressive commercial TTS, the user has a subscription |
| **Local TTS** | Orpheus TTS 3B | Best emotional/dramatic quality in open-source, fits RTX 4090 |
| **Sound Effects** | ElevenLabs SFX V2 API | Text-to-SFX, up to 30s, looping support, 48kHz |
| **Audio Mixing** | pydub | Already a dependency, handles all needed mixing operations |
| **Frontend** | TBD (HTMX or React) | To be decided based on preference |
| **Auth** | JWT (python-jose + passlib) | Simple, stateless, sufficient for 1-2 users |

---

## Recommended Build Order

Start with the pipeline core (Phases 1-3) before worrying about UI or auth. The priority is getting a single story through the full pipeline — from URL to dramatic audio — even if triggered manually via API calls or a script.

**Suggested order:**
1. Phase 1 (Fix Foundations) — get existing code working
2. Phase 2 (Script Adaptation) — the creative core
3. Phase 3 (Enhanced Audio) — dramatic production
4. Phase 5 (Frontend) — make it usable
5. Phase 6 (Auth) — lock it down
6. Phase 4 (Local TTS) — add the fallback
7. Phase 7 (Testing) — harden it
8. Phase 8 (Deployment) — ship it

Phase 4 (Local TTS) is deliberately placed after the frontend because ElevenLabs will work for initial use, and the local fallback is a nice-to-have rather than a blocker.
