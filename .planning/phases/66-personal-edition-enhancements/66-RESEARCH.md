# Phase 66: Personal Edition Enhancements - Media, Creative & Smart Home - Research

**Researched:** February 20, 2026
**Domain:** Media Control, Smart Home Integration, Creative Tools, Local-First Privacy
**Confidence:** HIGH

## Summary

Phase 66 extends Atom Personal Edition with personal assistant capabilities to achieve feature parity with OpenClaw for home automation, media control, and creative tasks. The research identified mature, well-documented Python libraries for all target integrations (Spotify, Sonos, Philips Hue, Home Assistant, Notion, FFmpeg, Stable Diffusion) with active community support and clear integration patterns.

**Key findings:**
- All target integrations have established Python libraries (Spotify: Spotipy/Tekore, Sonos: SoCo, Hue: python-hue-v2, HomeKit: HAP-python)
- OAuth 2.0 infrastructure already exists in Atom (`core/oauth_handler.py`) - can be reused for Spotify/Apple Music
- Local-first privacy is achievable through Docker network isolation and encrypted token storage (already implemented)
- FFmpeg-python is the standard for video editing; Diffusers library for local Stable Diffusion
- OpenClaw has 700+ community skills via ClawHub - Atom can leverage existing skills with security scanning
- Governance patterns from existing tools (browser_tool, device_tool) apply directly to new integrations

**Primary recommendation:** Implement 6-8 focused plans: (1) Media Control (Spotify, Sonos, Apple Music), (2) Smart Home (Philips Hue, Home Assistant, HomeKit), (3) Notion & Productivity, (4) Creative Tools (FFmpeg, Stable Diffusion), (5) Local-First Security, (6) Docker Compose enhancements, (7) Testing & Documentation, (8) OpenClaw Skills Bridge.

**Complexity assessment:** MEDIUM - No new architectural patterns required, leveraging existing OAuth/tool/governance systems. Most work is integration wiring and API endpoints.

## User Constraints

<user_constraints>

**No CONTEXT.md exists yet** - All areas are Claude's discretion for research and recommendations.

### Claude's Discretion (Research & Recommend)

The following areas require investigation and recommendations:

1. **Media Control Stack**
   - Which Python libraries for Spotify, Sonos, Apple Music?
   - How to handle OAuth 2.0 for media services?
   - Maturity gates for media control?

2. **Smart Home Integration**
   - Philips Hue API version (1.0 vs 2.0)?
   - Home Assistant local API vs cloud?
   - HomeKit/HAP-python for Apple ecosystem?
   - Elgato Stream Deck support?

3. **Creative Tools**
   - FFmpeg-python vs alternatives for video editing?
   - Stable Diffusion local setup (Diffusers vs WebUI)?
   - Image generation providers (DALL-E vs local)?

4. **Privacy & Local-First Architecture**
   - Docker network isolation patterns?
   - Token encryption for third-party APIs?
   - Governance for device control?

5. **OpenClaw Parity**
   - Which OpenClaw skills to prioritize?
   - How to import/use ClawHub skills safely?
   - Feature gaps vs. Atom strengths?

</user_constraints>

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **spotipy** | Latest (2026) | Spotify Web API | Most popular, comprehensive coverage, active maintenance |
| **SoCo (Sonos Controller)** | Latest | Sonos speaker control | Python-standard, simple API, multi-room support |
| **python-hue-v2** | Latest | Philips Hue API 2.0 | Supports latest Hue API, modern async support |
| **HAP-python** | Latest | HomeKit accessory protocol | Standard for HomeKit emulation/control |
| **homeassistant-api** | Latest (custom) | Home Assistant REST API | Official Python client for HA |
| **notion-sdk-py** | Latest | Notion API | Official Notion client, async support |
| **ffmpeg-python** | Latest | Video/audio processing | Pythonic FFmpeg wrapper, standard choice |
| **diffusers** | Latest | Stable Diffusion inference | HuggingFace standard, Metal acceleration for Apple Silicon |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | Latest | Async HTTP client | OAuth token exchanges, API calls |
| **python-elgato-streamdeck** | Latest | Elgato Stream Deck control | Custom button interfaces |
| **PyYAML** | Latest | YAML config parsing | Home Assistant, device configs |
| **pillow** | Latest | Image processing | Image generation post-processing |
| **numpy** | Latest | Numerical computing | Audio/video data manipulation |

### Existing Atom Infrastructure (Reuse)

| Component | Purpose | Reuse For |
|-----------|---------|-----------|
| `core/oauth_handler.py` | OAuth 2.0 flows | Spotify, Apple Music, Notion |
| `core/governance_cache.py` | Cached permission checks | Device control governance |
| `tools/registry.py` | Tool discovery & metadata | Register new media/smart home tools |
| `tools/device_tool.py` | Device capability patterns | Smart home device management |
| `backend/core/models.py` | Encrypted token storage | OAuth tokens for media services |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **spotipy** | Tekore, spotify.py | Spotipy has most community momentum, Tekore has better async |
| **python-hue-v2** | phue (API 1.0) | python-hue-v2 supports latest API, phue is simpler but deprecated |
| **ffmpeg-python** | MoviePy, PyAV | ffmpeg-python is more flexible, MoviePy is higher-level but slower |
| **Diffusers** | Stable Diffusion WebUI API | Diffusers is programmatic Python, WebUI is easier but less flexible |

**Installation:**
```bash
# Media control
pip install spotipy SoCo python-hue-v2 HAP-python

# Creative tools
pip install ffmpeg-python diffusers torch pillow

# Productivity
pip install notion-sdk-py

# Already in Atom
pip install httpx PyYAML numpy
```

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── tools/
│   ├── media_tool.py           # Spotify, Sonos, Apple Music control
│   ├── smarthome_tool.py       # Hue, Home Assistant, HomeKit
│   ├── creative_tool.py        # FFmpeg, Stable Diffusion
│   └── productivity_tool.py    # Notion, Obsidian (future)
├── api/
│   ├── media_routes.py         # Media control endpoints
│   ├── smarthome_routes.py     # Smart home endpoints
│   └── creative_routes.py      # Creative tool endpoints
├── core/
│   ├── media/                  # Media service layer
│   │   ├── spotify_service.py
│   │   ├── sonos_service.py
│   │   └── apple_music_service.py
│   ├── smarthome/              # Smart home service layer
│   │   ├── hue_service.py
│   │   ├── home_assistant_service.py
│   │   └── homekit_service.py
│   └── creative/               # Creative service layer
│       ├── ffmpeg_service.py
│       └── image_generation_service.py
├── tests/
│   ├── test_media_tool.py
│   ├── test_smarthome_tool.py
│   └── test_creative_tool.py
└── integrations/
    ├── spotify_oauth_config.py
    └── apple_music_jwt.py      # Apple Music uses JWT, not OAuth
```

### Pattern 1: OAuth-Protected Media Service

**What:** Service layer for third-party APIs with OAuth token management

**When to use:** Any integration requiring user authorization (Spotify, Notion, Apple Music)

**Example:**

```python
# Source: backend/core/media/spotify_service.py

from core.oauth_handler import OAuthConfig, OAuthHandler
from core.models import _encrypt_token, _decrypt_token

class SpotifyService:
    """Spotify Web API integration with OAuth"""

    SCOPES = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "user-library-read"
    ]

    def __init__(self, db: Session):
        self.db = db
        self.oauth_config = OAuthConfig(
            client_id_env="SPOTIFY_CLIENT_ID",
            client_secret_env="SPOTIFY_CLIENT_SECRET",
            redirect_uri_env="SPOTIFY_REDIRECT_URI",
            auth_url="https://accounts.spotify.com/authorize",
            token_url="https://accounts.spotify.com/api/token",
            scopes=self.SCOPES
        )
        self.oauth_handler = OAuthHandler(self.oauth_config)

    async def get_authorization_url(self) -> str:
        """Generate Spotify OAuth authorization URL"""
        import secrets
        state = secrets.token_urlsafe(16)
        return self.oauth_handler.get_authorization_url(state)

    async def exchange_code_for_tokens(self, code: str, user_id: str) -> Dict:
        """Exchange OAuth code for access/refresh tokens"""
        tokens = await self.oauth_handler.exchange_code_for_tokens(code)

        # Store encrypted tokens
        oauth_token = OAuthToken(
            user_id=user_id,
            provider="spotify",
            access_token=_encrypt_token(tokens["access_token"]),
            refresh_token=_encrypt_token(tokens.get("refresh_token", "")),
            expires_at=datetime.now() + timedelta(seconds=tokens["expires_in"])
        )
        self.db.add(oauth_token)
        self.db.commit()

        return {"status": "connected"}

    async def get_current_track(self, user_id: str) -> Dict:
        """Get user's currently playing track"""
        # Retrieve and decrypt token
        oauth_token = self.db.query(OAuthToken).filter(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == "spotify"
        ).first()

        if not oauth_token:
            raise HTTPException(401, "Spotify not connected")

        access_token = _decrypt_token(oauth_token.access_token)

        # Call Spotify API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.spotify.com/v1/me/player/currently-playing",
                headers={"Authorization": f"Bearer {access_token}"}
            )

        return response.json()
```

### Pattern 2: Local Network Device Discovery

**What:** mDNS/UDP-based device discovery for local smart home devices

**When to use:** Philips Hue bridges, Sonos speakers, Home Assistant instances

**Example:**

```python
# Source: backend/core/smarthome/hue_service.py (python-hue-v2 pattern)

from python_hue_v2 import Hue, BridgeFinder

class HueService:
    """Philips Hue lighting control service"""

    async def discover_bridges(self) -> List[str]:
        """Discover Hue bridges on local network via mDNS"""
        finder = BridgeFinder()
        addresses = finder.get_bridge_addresses()
        return addresses

    async def connect_to_bridge(self, bridge_ip: str, api_key: str) -> Hue:
        """Connect to Hue bridge with API key"""
        hue = Hue(bridge_ip, api_key)

        # Test connection
        if hue.bridge.is_authorized:
            return hue
        else:
            raise ValueError("Invalid Hue API key")

    async def set_light_state(
        self,
        bridge_ip: str,
        api_key: str,
        light_id: str,
        on: bool = True,
        brightness: float = 100.0,
        color_xy: Optional[Tuple[float, float]] = None
    ) -> Dict:
        """Control Hue light state"""
        hue = await self.connect_to_bridge(bridge_ip, api_key)

        # Find light by ID or name
        light = next((l for l in hue.lights if l.id == light_id), None)
        if not light:
            raise ValueError(f"Light {light_id} not found")

        # Set state
        light.on = on
        light.brightness = brightness
        if color_xy:
            light.color_xy = color_xy

        return {"status": "success", "light_id": light.id, "state": "on" if on else "off"}
```

### Pattern 3: FFmpeg Video Editing (Async Task)

**What:** Async FFmpeg video processing with progress tracking

**When to use:** Video editing, transcoding, format conversion

**Example:**

```python
# Source: backend/core/creative/ffmpeg_service.py

import ffmpeg
from asyncio import create_task

class FFmpegService:
    """FFmpeg-based video editing service"""

    async def trim_video(
        self,
        input_path: str,
        output_path: str,
        start_time: str,
        duration: str
    ) -> Dict:
        """Trim video to specified duration"""
        try:
            # Build FFmpeg pipeline
            stream = ffmpeg.input(input_path, ss=start_time, t=duration)
            stream = ffmpeg.output(stream, output_path, c='copy')
            ffmpeg.run(stream, overwrite_output=True)

            return {
                "status": "success",
                "output_path": output_path,
                "duration": duration
            }

        except ffmpeg.Error as e:
            return {
                "status": "error",
                "error": str(e.stderr.decode('utf8'))
            }

    async def generate_thumbnail(
        self,
        video_path: str,
        thumbnail_path: str,
        timestamp: str = "00:00:01"
    ) -> Dict:
        """Extract thumbnail from video at timestamp"""
        try:
            (
                ffmpeg
                .input(video_path, ss=timestamp)
                .output(thumbnail_path, vframes=1, format='image2', vcodec='mjpeg')
                .overwrite_output()
                .run()
            )

            return {
                "status": "success",
                "thumbnail_path": thumbnail_path
            }

        except ffmpeg.Error as e:
            return {
                "status": "error",
                "error": str(e.stderr.decode('utf8'))
            }
```

### Pattern 4: Local-Only Docker Network Isolation

**What:** Docker Compose configuration for privacy-focused local services

**When to use:** Personal Edition, privacy-sensitive deployments

**Example:**

```yaml
# Source: docker-compose-personal.yml (enhanced for Phase 66)

services:
  # Backend with local-only integrations
  atom-backend:
    build: ./backend
    container_name: atom-personal-backend
    ports:
      - "8000:8000"
    environment:
      # Enable local-only mode (no cloud relays)
      - ATOM_LOCAL_ONLY=true
      - ATOM_DISABLE_METRICS=true

      # Media service credentials (OAuth)
      - SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID:-}
      - SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET:-}
      - SPOTIFY_REDIRECT_URI=http://localhost:8000/integrations/spotify/callback

      # Smart home device IPs (local network)
      - HUE_BRIDGE_IP=${HUE_BRIDGE_IP:-}
      - HUE_API_KEY=${HUE_API_KEY:-}
      - HOME_ASSISTANT_URL=${HOME_ASSISTANT_URL:-http://homeassistant:8123}
      - HOME_ASSISTANT_TOKEN=${HOME_ASSISTANT_TOKEN:-}

    volumes:
      - ./data:/app/data
      - ./backend:/app
    networks:
      - atom-local

  # Home Assistant (optional - for local smart home)
  homeassistant:
    image: homeassistant/home-assistant:latest
    container_name: atom-personal-homeassistant
    volumes:
      - ./data/homeassistant:/config
      - /etc/localtime:/etc/localtime:ro
    network_mode: host  # Required for mDNS device discovery
    restart: unless-stopped

  # Network isolation - no external internet access
networks:
  atom-local:
    driver: bridge
    internal: false  # Allow outbound for OAuth, but can restrict further
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

### Anti-Patterns to Avoid

- **Hardcoding device IPs**: Use mDNS discovery (Hue, Sonos) instead of hardcoded IPs
- **Storing OAuth tokens plaintext**: Use `_encrypt_token()` from `core/models.py`
- **Blocking FFmpeg calls**: Run FFmpeg in background tasks/threads with progress callbacks
- **Skipping maturity gates**: Device control requires SUPERVISED+ or AUTONOMOUS maturity
- **Cloud relays for local devices**: Connect directly to Hue bridges, Home Assistant on LAN
- **Ignoring token refresh**: Implement refresh token logic for all OAuth providers

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth 2.0 flows | Custom token exchange logic | `core.oauth_handler.OAuthHandler` | Handles edge cases, refresh tokens, provider-specific quirks |
| Device discovery | mDNS/UDP from scratch | `python-hue-v2.BridgeFinder`, SoCo discovery | Handles network edge cases, timeouts, multi-device |
| Video processing | Raw subprocess FFmpeg calls | `ffmpeg-python` library | Pythonic API, better error handling, chainable filters |
| Image generation | HTTP calls to WebUI API | `diffusers.DiffusionPipeline` | Native Python, async support, Metal acceleration |
| Token encryption | Custom AES encryption | `core.models._encrypt_token()` | Consistent with existing tokens, Fernet-tested |
| Governance checks | Custom permission logic | `core.governance_cache.GovernanceCache` | <1ms cached lookups, thread-safe, auto-expiry |

**Key insight:** Atom already has OAuth, governance, and tool patterns. Leverage existing infrastructure instead of building parallel systems.

## Common Pitfalls

### Pitfall 1: OAuth Token Management

**What goes wrong:** Access tokens expire after 1 hour, refresh tokens fail silently

**Why it happens:** Not implementing refresh token logic, storing tokens plaintext

**How to avoid:**
- Use `core.oauth_handler.OAuthHandler` for all OAuth flows
- Store tokens encrypted with `_encrypt_token()` in `OAuthToken` model
- Implement background token refresh task
- Check token expiration before API calls

**Warning signs:** 401 Unauthorized errors from Spotify/Notion, tokens working for 1 hour then failing

### Pitfall 2: Local Network Device Discovery

**What goes wrong:** mDNS discovery fails in Docker containers due to network isolation

**Why it happens:** Docker containers use bridge networks, can't see LAN mDNS broadcasts

**How to avoid:**
- Use `network_mode: host` for services requiring mDNS (Home Assistant)
- Or pass device IPs via environment variables (`HUE_BRIDGE_IP`)
- Test discovery on LAN before Dockerizing

**Warning signs:** "Bridge not found" errors from Hue/Sonos services

### Pitfall 3: FFmpeg Blocking Operations

**What goes wrong:** Long video transcodes block FastAPI event loop, timeout errors

**Why it happens:** Running FFmpeg synchronously in async endpoint

**How to avoid:**
- Run FFmpeg in background thread/task
- Use `asyncio.create_task()` for long operations
- Implement progress callback endpoints
- Set reasonable timeouts (5-10 min for video processing)

**Warning signs:** "Server timeout" errors, unresponsive endpoints during video processing

### Pitfall 4: Smart Home Privacy Leaks

**What goes wrong:** Local device data sent to cloud for "processing"

**Why it happens:** Using Home Assistant cloud API instead of local, Hue cloud remote

**How to avoid:**
- Use local API endpoints only (`http://homeassistant:8123/api`)
- Disable Hue cloud remote in Hue app settings
- Set `ATOM_LOCAL_ONLY=true` environment variable
- Audit outbound network connections with `docker stats`

**Warning signs:** Outbound HTTPS traffic to cloud APIs, data usage spikes

### Pitfall 5: Apple Music JWT vs OAuth Confusion

**What goes wrong:** Trying to use OAuth 2.0 for Apple Music (which uses JWT tokens)

**Why it happens:** Apple Music Kit uses JWT developer tokens, not OAuth user tokens

**How to avoid:**
- Generate JWT tokens with Apple Music private key (developer account required)
- Token valid for 6 months, no refresh token
- Use `pyjwt` library for JWT generation
- Note: Apple Music API is more limited than Spotify (no playback control)

**Warning signs:** "Invalid grant_type" errors, confusing Apple Music with Spotify OAuth

### Pitfall 6: Maturity Gate Bypass

**What goes wrong:** STUDENT agents controlling smart home devices, changing settings

**Why it happens:** Not wiring tool governance checks through existing `GovernanceCache`

**How to avoid:**
- Set `maturity_required="SUPERVISED"` for device control tools
- Check `agent_governance_service.check_permission()` before device operations
- Use `tools/registry.py` metadata for governance
- Audit all device actions in `AgentExecution` logs

**Warning signs:** Unexpected device state changes, lights toggling automatically

## Code Examples

Verified patterns from official sources:

### Spotify OAuth Flow

```python
# Source: Spotipy documentation + Atom OAuth handler pattern

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Generate auth URL (from Atom OAuth handler)
auth_url = "https://accounts.spotify.com/authorize?client_id=...&scope=..."

# Exchange code for tokens
sp = Spotify(auth_manager=SpotifyOAuth(
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="http://localhost:8000/integrations/spotify/callback",
    scope="user-read-playback-state user-modify-playback-state"
))

# Get current track
track = sp.current_user_playing_track()
print(f"Now playing: {track['item']['name']}")

# Control playback
sp.start_playback(device_id="device_id", uris=["spotify:track:track_id"])
sp.pause_playback()
sp.next_track()
```

### Philips Hue Control (python-hue-v2)

```python
# Source: python-hue-v2 official documentation

from python_hue_v2 import Hue, BridgeFinder

# Discover bridges
finder = BridgeFinder()
addresses = finder.get_bridge_addresses()  # Returns list of IPs

# Connect (requires pressing link button on bridge first)
hue = Hue(addresses[0], 'your-api-key-from-hue-app')

# Control lights
for light in hue.lights:
    light.on = True
    light.brightness = 80.0  # 0-100%
    light.color_xy = (0.5, 0.3)  # XY color space

# Get all lights
lights_data = [(l.id, l.name, l.on) for l in hue.lights]

# Create scene
hue.scenes.create("Movie Mode", lights_data)
```

### Home Assistant REST API

```python
# Source: Home Assistant API documentation

import httpx

HA_URL = "http://homeassistant:8123"
HA_TOKEN = "your_long_lived_access_token"

async def get_states():
    """Get all entity states from Home Assistant"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{HA_URL}/api/states",
            headers={
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "application/json"
            }
        )
        return response.json()

async def call_service(domain: str, service: str, entity_id: str, data: dict):
    """Call Home Assistant service"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{HA_URL}/api/services/{domain}/{service}",
            headers={
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"entity_id": entity_id, **data}
        )
        return response.json()

# Turn on light
await call_service("light", "turn_on", "light.living_room", {"brightness_pct": 80})
```

### FFmpeg Video Editing

```python
# Source: ffmpeg-python official documentation

import ffmpeg

# Trim video
(
    ffmpeg
    .input('input.mp4', ss='00:00:10', t='00:00:30')
    .output('output.mp4', c='copy')
    .run()
)

# Add watermark
(
    ffmpeg
    .input('input.mp4')
    .input('watermark.png')
    .filter('[0:v][1:v] overlay=10:10')
    .output('output.mp4')
    .run()
)

# Extract audio
(
    ffmpeg
    .input('video.mp4')
    .output('audio.mp3', acodec='libmp3lame')
    .run()
)

# Generate thumbnail
(
    ffmpeg
    .input('video.mp4', ss='00:00:05')
    .output('thumb.jpg', vframes=1, format='image2', vcodec='mjpeg')
    .overwrite_output()
    .run()
)
```

### Stable Diffusion (Diffusers)

```python
# Source: HuggingFace Diffusers documentation

from diffusers import DiffusionPipeline
import torch

# Load model (first run downloads ~5GB)
pipe = DiffusionPipeline.from_pretrained(
    "stable-diffusion-v1-5/stable-diffusion-v1-5",
    torch_dtype=torch.float16
)

# GPU acceleration
pipe.to("cuda")

# Generate image
prompt = "A photo of a golden retriever in a forest"
image = pipe(prompt).images[0]
image.save("dog.png")

# Apple Silicon Metal acceleration (40% faster)
# pipe.to("mps")  # For M1/M2 Macs
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hue API 1.0 (`phue` library) | Hue API 2.0 (`python-hue-v2`) | 2022 | API 2.0 required for newer Hue bridges, richer color control |
| Stable Diffusion WebUI only | Diffusers library (programmatic) | 2023-2024 | Diffusers enables Python automation, WebUI is GUI-only |
| FFmpeg subprocess calls | `ffmpeg-python` wrapper | 2019+ | Pythonic API, chainable filters, better error handling |
| OAuth manual implementation | Atom `OAuthHandler` unified | Phase 1-4 | Reusable OAuth flows, encrypted token storage, refresh handling |
| Cloud-only smart home | Local-first + Docker isolation | 2025+ | Privacy focus, no cloud relays, local mDNS discovery |

**Deprecated/outdated:**
- **Hue API 1.0**: Deprecated by Signify, use `python-hue-v2` for API 2.0
- **MoviePy**: Slower than `ffmpeg-python`, not actively maintained
- **PyAV**: Lower-level than `ffmpeg-python`, steeper learning curve
- **Custom OAuth flows**: Use Atom's `OAuthHandler`, not per-integration OAuth code
- **Plaintext token storage**: All tokens must use `_encrypt_token()` from `core/models.py`

## Open Questions

1. **Apple Music Developer Token Generation**
   - What we know: Apple Music uses JWT tokens (6-month validity), requires Apple Developer account
   - What's unclear: JWT generation with `pyjwt` and Apple private key (.p8 file)
   - Recommendation: Defer Apple Music to later plan, prioritize Spotify (easier OAuth)

2. **Elgato Stream Deck Support Priority**
   - What we know: `python-elgato-streamdeck` library exists, supports button images, events
   - What's unclear: User demand for Stream Deck vs. other smart home devices
   - Recommendation: Add as stretch goal if time permits, not core to Phase 66

3. **Stable Diffusion Model Storage**
   - What we know: Models are 5GB+ each, need persistent Docker volumes
   - What's unclear: Where to store models (host mount vs. Docker volume), download strategy
   - Recommendation: Store in `./data/models` Docker volume, download on first use with progress indicator

4. **Home Assistant Authentication**
   - What we know: Supports long-lived access tokens (no expiry) and API tokens
   - What's unclear: OAuth vs. long-lived token security tradeoff
   - Recommendation: Use long-lived access tokens for simplicity (Personal Edition), OAuth for multi-user (future)

5. **OpenClaw Skills Integration**
   - What we know: OpenClaw has 700+ skills via ClawHub (`npx clawhub install`)
   - What's unclear: Security scan process, compatibility with Atom governance
   - Recommendation: Research in Plan 08 (OpenClaw Bridge), leverage existing Community Skills security scanning

## Sources

### Primary (HIGH confidence)

- **Spotipy GitHub** - Spotify Web API Python library, OAuth flow examples
- **python-hue-v2 PyPI** - Philips Hue API 2.0 library, bridge discovery, light control
- **SoCo Documentation** - Sonos controller Python library, multi-room audio
- **ffmpeg-python GitHub** - FFmpeg Python wrapper, video editing examples
- **Diffusers Documentation** - HuggingFace Stable Diffusion library, async support, Metal acceleration
- **Notion SDK PyPI** - Official Notion API Python client, async support
- **Atom Codebase** - `backend/core/oauth_handler.py`, `backend/tools/registry.py`, `backend/core/models.py`

### Secondary (MEDIUM confidence)

- **Spotify Web API Guide** (CSDN, Oct 2025) - OAuth token refresh flow implementation
- **Home Assistant Docker Guide** (CSDN, Jan 2026) - Local deployment, mDNS discovery, network isolation
- **Smart Home Privacy Best Practices** (CSDN, Feb 2026) - Docker network isolation, blocking internet access
- **OpenClaw Skills Ecosystem** (CSDN/Toutiao, Jan 2026) - 700+ skills, ClawHub registry, personal-assistant skill
- **Apple Music API Documentation** (developer.apple.com, 2025) - JWT token generation, MusicKit framework
- **FFmpeg Python Tutorial** (CSDN, Dec 2025) - Video editing workflows, performance optimization

### Tertiary (LOW confidence)

- **Elgato Stream Deck Python** - Library exists but user demand unclear, needs validation
- **Obsidian API Integration** - No official Python API, markdown-based approach uncertain
- **Sonos API Documentation** - SoCo library well-established, but edge cases unknown
- **Local-Only Smart Home** - Concept validated, but real-world Docker networking edge cases need testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries well-documented, actively maintained, industry-standard
- Architecture: HIGH - Existing Atom patterns (OAuth, governance, tools) directly applicable
- Pitfalls: MEDIUM - OAuth and smart home edge cases documented, Docker networking needs testing
- OpenClaw integration: LOW - 700+ skills confirmed, but security scanning process needs research

**Research date:** February 20, 2026
**Valid until:** March 22, 2026 (30 days - Python library ecosystem stable)

**Estimated complexity:** MEDIUM (6-8 plans, 1-2 weeks)
**Risk level:** LOW (leverages existing infrastructure, no novel algorithms)

**Next step:** Create PLAN.md files for each plan using this research as foundation
