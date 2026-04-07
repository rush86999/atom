# Menu Bar Companion App Guide

## Overview

Atom Menu Bar is a native macOS application that provides quick access to AI agents, canvases, and automation workflows from your menu bar. Built with Tauri v2, it offers a fast, secure, and seamless experience.

## Prerequisites

- macOS 10.15 (Catalina) or later
- Node.js 18+ and npm
- Rust and Cargo
- Xcode Command Line Tools

## Installation

### From Source

```bash
cd menubar
npm install
npm run tauri build
```

The DMG will be in `src-tauri/target/release/bundle/dmg/`.

### From DMG

1. Download the latest DMG from [Releases](https://github.com/rush86999/atom/releases)
2. Open the DMG
3. Drag Atom Menu Bar to Applications
4. Launch from Applications

## First Run

1. Click the Atom icon in the menu bar
2. Enter your credentials (email/password)
3. The app will register as a device and save your token in Keychain
4. You're ready to go!

## Features

### 1. Quick Chat

**Global Hotkey**: `Cmd+Shift+A`

- Fast access to AI agents
- Streaming responses
- Agent selection dropdown
- Episode context display
- Canvas references

### 2. Recent Agents

- View your top 5 most recently used agents
- Filter by maturity level
- See agent status (online/offline)
- One-click access to agent chat

### 3. Recent Canvases

- View your top 5 most recent canvases
- Quick preview of canvas content
- One-click to open full canvas

### 4. Connection Status

- Real-time connection indicator
- Last sync timestamp
- Pending actions count
- Quick reconnect button

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+Shift+A` | Open Quick Chat |
| `Cmd+Shift+R` | Refresh Data |
| `Cmd+Shift+P` | Preferences |
| `Cmd+Shift+Q` | Quit |

## Menu Bar Menu

Right-click the menu bar icon for:

- **Show Atom**: Open the main window
- **Connection Status**: View sync status
- **Refresh**: Update recent items
- **Preferences**: Configure settings
- **About**: Version and credits
- **Quit**: Close the app

## Architecture

```
┌─────────────────────────────────────┐
│         Menu Bar Icon               │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      Tauri (Rust Backend)           │
│  - Keychain Storage                 │
│  - HTTP Client                      │
│  - WebSocket Client                 │
│  - Native macOS Integration         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      React (Frontend)               │
│  - Login Screen                     │
│  - Quick Chat                       │
│  - Agent List                       │
│  - Canvas List                      │
└─────────────────────────────────────┘
         │
         │ REST API + WebSocket
         ▼
┌─────────────────────────────────────┐
│         Atom Backend                │
│  - Agent Execution                  │
│  - Canvas Rendering                 │
│  - Episode Memory                   │
│  - Push Notifications               │
└─────────────────────────────────────┘
```

## Security

### Token Storage

- Tokens are stored in macOS Keychain
- Encrypted at rest
- Automatic token refresh
- Secure HTTPS/WSS connections

### Device Registration

- Each app instance registers as a DeviceNode
- Device type: "menubar"
- Audit trail for all actions
- Remote logout support

### Code Signing

Production builds are:
- Signed with Apple Developer certificate
- Notarized by Apple
- Verified on launch

## Troubleshooting

### App Won't Launch

```bash
# Check if previous instance is running
killall Atom

# Clear cache
rm -rf ~/Library/Application\ Support/com.atom.menubar

# Restart
open -a Atom
```

### Login Issues

1. Verify backend is accessible: `curl https://api.atom-platform.com/api/menubar/health`
2. Check network connection
3. Clear Keychain (search for "atom" in Keychain Access)
4. Try logging in again

### Connection Drops

1. Check internet connection
2. Verify WebSocket endpoint: `wss://api.atom-platform.com`
3. Check firewall settings
4. Restart the app

## Development

### Start Development Server

```bash
cd menubar
npm run tauri:dev
```

### Build for Production

```bash
npm run tauri build
```

### Run Tests

```bash
npm test
```

## Configuration

### API Endpoint

Edit `src-tauri/src/commands.rs`:

```rust
const API_BASE_URL: &str = "https://api.atom-platform.com";
```

### Window Size

Edit `src-tauri/tauri.conf.json`:

```json
{
  "app": {
    "windows": [{
      "width": 400,
      "height": 600
    }]
  }
}
```

### Hotkey

Edit `src-tauri/src/menu.rs` to change the global hotkey.

## Performance

Optimizations enabled:

- Streaming responses (token-by-token)
- Cached session data
- Lazy loading for large lists
- Debounced API calls
- Efficient re-renders (React.memo)

## Updates

### Automatic Updates

The app checks for updates on launch and prompts to download new versions.

### Manual Check

1. Right-click menu bar icon
2. Select "Check for Updates"

### Changelog

See [Releases](https://github.com/rush86999/atom/releases) for version history.

## Uninstallation

```bash
# Quit the app
killall Atom

# Remove app
rm -rf /Applications/Atom.app

# Remove data
rm -rf ~/Library/Application\ Support/com.atom.menubar
rm -rf ~/Library/Caches/com.atom.menubar
rm -rf ~/Library/Preferences/com.atom.menubar.plist

# Remove Keychain items
# Open Keychain Access and search for "atom"
```

## Distribution

### Direct Download

Host the DMG on your server and provide download link.

### Homebrew Cask

Create a formula in Homebrew:

```ruby
cask "atom-menubar" do
  version "1.0.0"
  sha256 "your-sha256-hash"

  url "https://releases.atomplatform.com/Atom-1.0.0.dmg"
  name "Atom Menu Bar"
  homepage "https://atom-platform.com"

  app "Atom.app"
end
```

### Mac App Store

Requires:
- Apple Developer Account ($99/year)
- App Store Connect setup
- App Review approval

## Support

For issues and questions:
- GitHub: https://github.com/rush86999/atom/issues
- Documentation: https://docs.atom-platform.com
- Email: support@atom-platform.com

## License

Copyright © 2026 Atom Platform. All rights reserved.
