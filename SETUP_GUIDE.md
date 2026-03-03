# Voice In The Dark — Setup Guide

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

### Remote Access (Optional — Cloudflare Tunnel)

If someone outside your home network needs access (e.g., a friend in another city),
you can use a **free Cloudflare Tunnel**. This creates a secure public URL without
opening ports on your router, and hides your home IP address.

#### 1. Create a Free Cloudflare Account

Go to [dash.cloudflare.com](https://dash.cloudflare.com) and sign up.

#### 2. Add a Domain (or use Cloudflare's free subdomain)

You need a domain pointed at Cloudflare. If you don't own one, you can register
a cheap one through Cloudflare Registrar, or use a free domain service.

#### 3. Create the Tunnel

1. In the Cloudflare dashboard, go to **Zero Trust** (left sidebar)
2. Navigate to **Networks** > **Connectors**
3. Click **Add a tunnel**
4. Choose **Cloudflared** as the connector type
5. Name it something like `voice-in-the-dark`
6. On the **Install connector** step, find and copy the **tunnel token**
   (it's the long string after `--token` in the install command)
7. On the **Route tunnel** step, add a public hostname:
   - **Subdomain**: e.g., `stories` (or whatever you like)
   - **Domain**: select your domain
   - **Service type**: `HTTP`
   - **URL**: `voice-to-the-dark:8000`

   This last URL uses the Docker container name, which resolves automatically
   on Docker's internal network.

#### 4. Enable the Tunnel

Run the tunnel setup script:

```bash
bash tunnel.sh enable
```

It will prompt for your token, save it to `.env`, and start the tunnel container.
Your app will be available at the URL you configured (e.g., `https://stories.yourdomain.com`).

You can also run `bash tunnel.sh` with no arguments for an interactive walkthrough.

#### Tunnel Management

```bash
# Check tunnel status
bash tunnel.sh status

# Enable (interactive token prompt)
bash tunnel.sh enable

# Disable and stop tunnel
bash tunnel.sh disable

# View tunnel logs
docker compose --profile tunnel logs -f cloudflared
```

**Note:** If the tunnel is enabled, use `docker compose --profile tunnel up -d`
(instead of plain `docker compose up -d`) when restarting to include the tunnel.

#### Sharing with Your Friend

Once the tunnel is running, send them the URL (e.g., `https://stories.yourdomain.com`).
They can open it in any browser — no VPN or special software needed. They can also
add it to their phone's home screen the same way described in the Phone Setup section below.

---

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
5. Name it **"Voice In The Dark"** (or whatever you like)
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
