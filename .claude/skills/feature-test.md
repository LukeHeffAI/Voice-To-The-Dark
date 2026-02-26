# Feature Testing Agent

## Purpose

This skill is a comprehensive testing agent that should be run whenever a change is made to the codebase. It identifies, documents, and runs tests to catch regressions before code goes to production.

## When to Use

Run this agent:
- After any feature addition or modification
- After any bug fix
- After any refactoring
- Before any merge to dev or master
- When investigating reported breakages

## Testing Strategy

### 1. Identify Changed Files

Determine which files were modified and map them to their test coverage:

| Source File | Test File(s) | Coverage Area |
|---|---|---|
| `app/auth.py` | `tests/test_auth.py` | Password hashing, JWT creation/decode |
| `app/deps.py` | `tests/test_router_auth.py`, `tests/test_router_stories.py` | Auth dependencies |
| `app/rate_limit.py` | `tests/test_rate_limit.py` | Rate limiting logic |
| `app/config.py` | Multiple (used everywhere) | Settings propagation |
| `app/database.py` | `tests/conftest.py` | DB session management |
| `app/models/story.py` | `tests/test_router_stories.py`, `tests/test_integration.py` | ORM models |
| `app/models/app_setting.py` | `tests/test_router_settings.py` | Settings model |
| `app/schemas/story.py` | `tests/test_router_stories.py`, `tests/test_router_audio.py` | Request/response schemas |
| `app/schemas/narration.py` | `tests/test_router_audio.py`, `tests/test_script_adapter.py` | Script schemas |
| `app/routers/auth.py` | `tests/test_router_auth.py`, `tests/test_integration.py` | Auth endpoints |
| `app/routers/stories.py` | `tests/test_router_stories.py`, `tests/test_integration.py` | Story endpoints |
| `app/routers/audio.py` | `tests/test_router_audio.py`, `tests/test_integration.py` | Audio endpoints |
| `app/routers/player.py` | `tests/test_router_player.py` | HTML page endpoints |
| `app/routers/settings.py` | `tests/test_router_settings.py` | Settings endpoints |
| `app/services/text_cleaner.py` | `tests/test_text_cleaner.py` | Text cleaning |
| `app/services/hashing.py` | `tests/test_hashing.py` | Content hashing |
| `app/services/voice_pool.py` | `tests/test_voice_pool.py` | Voice assignment |
| `app/services/winks.py` | `tests/test_winks.py` | Quota tracking |
| `app/services/script_adapter.py` | `tests/test_script_adapter.py` | Script generation |
| `app/services/reddit.py` | `tests/test_reddit.py` | Reddit integration |
| `app/services/elevenlabs.py` | `tests/test_elevenlabs.py` | TTS generation |
| `app/services/audio_mixer.py` | `tests/test_audio_mixer.py` | Audio mixing |
| `app/services/narration_generator.py` | `tests/test_narration_generator.py` | Narration pipeline |
| `app/services/audio_utils.py` | `tests/test_audio_utils.py` | Audio utilities |
| `app/main.py` | `tests/test_main.py` | App initialization |
| `app/templates/*.html` | `tests/test_templates.py` | Template rendering |

### 2. Test Categories

Run tests in this order (fast to slow, unit to integration):

#### A. Schema & Model Validation
- All Pydantic models serialize/deserialize correctly
- SQLAlchemy models create tables without errors
- Required fields enforced, optional fields nullable
- Enum values valid

#### B. Pure Function Unit Tests
- `text_cleaner.py` - every regex pattern, edge cases
- `hashing.py` - determinism, encoding
- `voice_pool.py` - profile parsing, scoring, assignment
- `winks.py` - quota calculations, caching
- `auth.py` - password hashing, JWT lifecycle
- `rate_limit.py` - cleanup, limiting
- `reddit.py` - URL helpers, title matching (pure functions only)
- `elevenlabs.py` - text chunking
- `audio_mixer.py` - timeline building, rendering
- `script_adapter.py` - text splitting, JSON parsing

#### C. Router Endpoint Tests
- Every endpoint returns correct status codes
- Auth required/optional enforced correctly
- Request validation (malformed bodies rejected)
- Response schemas match documented models
- Error responses have correct detail messages
- Rate limiting enforced at correct thresholds

#### D. Integration Tests
- Full pipeline: submit → script → narration
- Playback save/resume flow
- Auth lifecycle: register → login → access → logout
- Series discovery and auto-submission
- Duplicate detection (URL and content hash)

#### E. Template Rendering Tests
- Every template renders without errors
- Templates handle None/missing data gracefully
- Template variables match what routers provide

#### F. Cross-Feature Regression Tests
- Mock patches target correct module paths (not stale imports)
- Database schema matches model definitions
- Response models match actual endpoint output
- URL patterns consistent across routers

### 3. Test Execution

```bash
# Run all tests with verbose output and short traceback
python -m pytest tests/ -v --tb=short

# Run specific test file
python -m pytest tests/test_router_stories.py -v --tb=short

# Run tests matching a pattern
python -m pytest tests/ -v -k "test_submit" --tb=short

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=term-missing
```

### 4. Common Failure Patterns to Check

#### Stale Mocks
When a function is renamed or moved, tests that mock the old name will fail with `AttributeError: module does not have attribute`. Fix by:
1. Finding all `@patch("app.routers.X.old_function")` decorators
2. Updating to match the current import in the router

#### Response Shape Changes
When endpoint return values change, tests checking specific keys/values fail. Fix by:
1. Reading the actual endpoint code to see current return shape
2. Updating test assertions to match

#### Missing Template Variables
When a template references a variable not passed by the router, the page returns 500. Fix by:
1. Checking all `{{ variable }}` references in the template
2. Ensuring the router passes all required variables in the template context

#### Database Schema Drift
When model columns are added/removed without matching migration, queries fail. Fix by:
1. Comparing model definitions to actual table schemas
2. Running `_migrate_db()` or recreating the test database

### 5. Writing New Tests

When adding tests for new or changed features:

```python
# Use existing fixtures from conftest.py
def test_new_feature(client, auth_headers, sample_story, db_session):
    # Arrange - set up test data
    # Act - call the endpoint
    resp = client.post("/stories/some-endpoint", json={...}, headers=auth_headers)
    # Assert - check response
    assert resp.status_code == 200
    assert resp.json()["key"] == expected_value
    # Assert - check side effects in DB
    row = db_session.query(Story).filter(Story.id == ...).first()
    assert row.field == expected_db_value
```

For external API calls, always mock:
```python
@patch("app.routers.stories.fetch_story_text")
@patch("app.routers.stories.fetch_post_metadata")
def test_with_mocked_reddit(mock_meta, mock_text, client, auth_headers, db_session):
    mock_meta.return_value = {"title": "Test", "author": "author"}
    mock_text.return_value = "Story text content."
    # ... test logic
```

### 6. Validation Checklist

Before marking tests as passing, verify:

- [ ] All existing tests still pass (no regressions)
- [ ] New feature has tests for success path
- [ ] New feature has tests for error/edge cases
- [ ] Auth requirements tested (protected endpoints reject anonymous)
- [ ] Response shapes match Pydantic models
- [ ] Mock patches use correct module paths
- [ ] Database state changes verified
- [ ] Rate limiting tested where applicable
- [ ] Template rendering tested for HTML endpoints
