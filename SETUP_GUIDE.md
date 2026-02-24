# Voice To The Dark — Setup Guide

## Server Setup (Your Linux PC)

### Prerequisites

- **Docker** with Docker Compose v2: [Install Docker](https://docs.docker.com/engine/install/)
- **API keys** (add to `.env`):
  - [ElevenLabs](https://elevenlabs.io) — for TTS and sound effects
  - [Anthropic](https://console.anthropic.com) — for Claude script adaptation

### One-Command Deploy

```bash
git clone <your-repo-url>
cd Voice-To-The-Dark
bash deploy.sh
```

The script will:
1. Create your `.env` from the template (you fill in API keys)
2. Generate a secure JWT secret
3. Build and start the Docker container
4. Ask you to create your admin account
5. Ask you to create your girlfriend's account
6. Print the URL to open on her phone

That's it. The app auto-restarts on reboot.

### Managing the App

```bash
# View logs
docker compose logs -f

# Restart
docker compose restart

# Stop
docker compose down

# Update after code changes
docker compose up -d --build

# Create another user account
docker compose exec voice-to-the-dark python -m app.create_user <username> <password>
```

### Data

Everything persists in `./data/`:
- `data/db/horror_narrator.db` — database (stories, users, playback state)
- `data/stories/` — generated audio files
- `data/sfx_cache/` — cached sound effects

To back up, just copy the `data/` folder.

---

## Phone Setup (Samsung Internet on her phone)

### Step 1: Connect to Home WiFi

Make sure her phone is on the same WiFi network as the server.

### Step 2: Open the App

Open **Samsung Internet** and go to:

```
http://<server-ip>:8000
```

Replace `<server-ip>` with the IP shown at the end of `deploy.sh`
(e.g. `http://192.168.1.50:8000`).

### Step 3: Add to Home Screen

This makes it feel like a real app — one tap to open, no URL to remember.

1. Open the URL in Samsung Internet
2. Tap the **menu** button (three horizontal lines, bottom-right)
3. Tap **"Add page to"**
4. Tap **"Home screen"**
5. Name it **"Voice To The Dark"** (or whatever you like)
6. Tap **Add**

Now there's an icon on her home screen that opens straight to the app.

### Step 4: Log In

1. Tap **Sign in** (top-right corner)
2. Enter the username and password you created for her
3. Tap **Sign in**

The login lasts **4 weeks** — she won't need to sign in again unless
she clears her browser data.

### Step 5: Using the App

**Submit a story:**
1. Tap **"+ Submit a new story"** from the home page
2. Either paste a r/nosleep URL, or browse the **Best of All Time** list
3. Tap **Submit** — the story is fetched and cleaned automatically

**Generate audio:**
1. On the story's detail page, tap **"Generate Script"**
   (Claude adapts the story into a dramatic narration with characters and SFX)
2. Once the script is ready, tap **"Generate Audio"**
   (ElevenLabs generates multi-voice narration with sound effects)
3. When audio is ready, tap **"Listen"** to open the player

**Listen:**
- Full audio player with play/pause, seek bar, and progress saving
- Works on the lock screen — playback controls appear in the notification area
- Your position is saved automatically — come back any time and resume

### Troubleshooting

**"Can't reach this page"**
- Make sure the phone is on the same WiFi as the server
- Make sure the server is running: `docker compose ps` on the server
- Check the IP address is correct: `hostname -I` on the server

**"Not authenticated" errors**
- Sign in again — the 4-week cookie may have expired
- If Samsung Internet cleared cookies, just log in again

**Audio won't play on lock screen**
- This is a Samsung Internet feature — make sure you're using Samsung Internet (not Chrome)
- If it stops, open the app and tap play again — the position is saved

**Server IP changed**
- Your router may assign a new IP after a reboot
- Run `hostname -I` on the server to find the new IP
- To prevent this, set a static IP or DHCP reservation on your router
