# ATOM Desktop App - System Tray Build Instructions

## 🚀 Complete Build Process with System Tray

### Prerequisites
- Node.js 18+ installed
- Rust/Cargo installed
- Python 3.8+ (for icon generation)
- Git CLI configured

### Project Structure
```
atom/
├── desktop/tauri/          # Tauri desktop app
│   ├── src-tauri/
│   │   ├── icons/         # New system tray icons
│   │   ├── main.rs        # Updated with system tray
│   │   └── tauri.conf.json # System tray config
```

## 🔧 Quick Start

### 1. Environment Setup
```bash
cd atom/desktop/tauri
npm install                    # Install frontend dependencies
cargo build --release          # Build Rust backend with system tray
```

### 2. Icon Bundle
Your new icon bundle includes:
- **System Tray**: `icons/tray_icon.png` (32x32 "A" letter)
- **Desktop Icons**: New complete icon set for all platforms
- **App Icons**: Professional Atom branding across Windows/Mac/Linux

### 3. Build Commands

#### Development Mode with System Tray
```bash
npm run tauri dev
```
- Creates background app
- Shows "A" letter icon in tray/menu bar
- Click icon to show/hide main window

#### Production Build
```bash
npm run tauri build
```
- Creates signed desktop installers
- Background app mode enabled
- Cross-platform system tray support

### 4. Platform-Specific Notes

#### macOS
- **Menu Bar**: Top-right menu bar with "A" icon
- **Click**: Single-click to toggle window
- **Background**: App continues running when window closed

#### Windows
- **System Tray**: Bottom-right tray area
- **Right-click**: Context menu (Open, Settings, Quit)
- **Auto-start**: Windows startup integration

#### Linux
- **System Tray**: Standard desktop environment tray
- **Click/Right-click**: Both support context menu
- **AppIndicator**: Modern tray support on Ubuntu/Fedora

### 5. Testing the System Tray
After successful build:

1. **Run the app**: `npm run tauri dev`
2. **Look for the "A"** icon in your system tray/menu bar
3. **Click the icon** to show/hide main window
4. **Right-click** for context menu with options

### 6. Distribution Files
After production build, find your installers:
- `desktop/tauri/src-tauri/target/release/bundle/`
  - Windows: `.msi` and `.exe`
  - macOS: `.dmg` and `.app`
  - Linux: `.deb`, `.rpm`, `.AppImage`

## ✅ Features Added
- **Background App Mode** - Runs in system tray when closed
- **Click-to-Open** - Instant window toggle from tray
- **Context Menu** - Professional tray menu
- **Memory Efficient** - Minimal background resource usage
- **Cross-Platform** - Works on macOS, Windows, Linux
- **Professional Branding** - Custom "A" letter system tray icon

## 🚦 Ready to Deploy
Your desktop app now includes complete system tray functionality with professional Atom branding. Start with development mode to test, then build production installers for distribution.

The app will automatically handle:
- Background initialization
- Tray icon display
- Click events
- Memory management
- Platform-specific behaviors