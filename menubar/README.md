# Atom Menu Bar Companion

A macOS menu bar companion app for Atom AI-Powered Automation Platform.

## Features

- **Quick Chat**: Send messages to agents directly from the menu bar (Cmd+Shift+A)
- **Recent Agents**: View and quickly access recently used agents
- **Recent Canvases**: View recent canvas presentations
- **Connection Status**: Real-time connection status indicator
- **Native macOS Integration**: System tray, global hotkeys, notifications

## Prerequisites

- macOS 10.13+
- Node.js 18+
- Rust 1.70+ (for Tauri)
- Atom backend running on `http://localhost:8000`

## Installation

```bash
cd menubar
npm install
```

## Development

```bash
# Start Vite dev server
npm run dev

# Start Tauri dev mode
npm run tauri:dev
```

## Building

```bash
# Build for production
npm run tauri:build
```

The built DMG will be in `src-tauri/target/release/bundle/dmg/`.

## Usage

1. **Sign In**: Click the Atom icon in the menu bar and sign in with your Atom credentials
2. **Quick Chat**: Type your message and press Cmd+Enter to send
3. **Keyboard Shortcut**: Press `Cmd+Shift+A` anywhere to open quick chat
4. **View Recent**: Scroll through recent agents and canvases

## Configuration

Edit `src-tauri/src/commands.rs` to change the API base URL:

```rust
const API_BASE_URL: &str = "http://localhost:8000";
```

For production, update this to your production API URL.

## Architecture

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type safety
- **Tauri API**: Native system integration

### Backend (Rust)
- **Tauri v2**: Desktop app framework
- **tokio**: Async runtime
- **reqwest**: HTTP client
- **keyring**: Secure token storage in macOS Keychain
- **tokio-tungstenite**: WebSocket client

### Backend API Integration

The menubar app communicates with these Atom backend endpoints:

- `POST /api/menubar/auth/login` - Authentication
- `GET /api/menubar/status` - Connection status
- `GET /api/menubar/recent/agents` - Recent agents
- `GET /api/menubar/recent/canvases` - Recent canvases
- `POST /api/menubar/quick/chat` - Quick chat

## Security

- Tokens stored securely in macOS Keychain
- HTTPS for production API communication
- Bearer token authentication
- Auto-hide on window focus loss

## Development Notes

### Window Behavior
- Window auto-hides when it loses focus (standard menu bar behavior)
- Use the system tray icon to show the window again
- Global hotkey `Cmd+Shift+A` to show and focus quick chat

### State Management
- Auth token stored in Rust app state and macOS Keychain
- React components use Tauri invoke to call Rust commands
- Session persists across app restarts (via Keychain)

### Global Hotkey
The `Cmd+Shift+A` hotkey is registered in Tauri's setup. When pressed:
1. Shows the menu bar window
2. Focuses on the quick chat input
3. Triggers the `quick-chat-hotkey` event

### WebSocket (Future)
Real-time agent responses and canvas presentations will be delivered via WebSocket connection. See `src-tauri/src/websocket.rs` for the client implementation.

## Troubleshooting

### "Failed to connect to server"
- Ensure Atom backend is running on port 8000
- Check `API_BASE_URL` in `src-tauri/src/commands.rs`
- Verify network connectivity

### "Login failed"
- Check email and password
- Verify backend API is accessible
- Check backend logs for errors

### Window doesn't appear
- Check system tray for Atom icon
- Use `Cmd+Shift+A` hotkey
- Check App.log for errors

## License

MIT
