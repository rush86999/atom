# ATOM Development Guide

## Overview

ATOM is a unified platform that provides both desktop and web applications with feature parity. This guide covers the development workflow, build processes, and architecture.

## Architecture

### Platform Structure

```
atom/
├── src-tauri/           # Desktop app (Tauri + Rust)
├── frontend-nextjs/     # Web app (Next.js + React)
├── src/                 # Shared TypeScript code
├── scripts/             # Build and deployment scripts
└── docs/               # Documentation
```

### Unified Platform

The platform uses a unified architecture that provides consistent features across both desktop and web:

- **Desktop**: Tauri-based native application with system integration
- **Web**: Next.js progressive web app with offline capabilities
- **Shared**: Common TypeScript codebase with platform-specific implementations

## Development Setup

### Prerequisites

- Node.js 18+ and npm
- Rust (for desktop development)
- Git

### Quick Start

1. **Clone and install dependencies:**
   ```bash
   git clone <repository>
   cd atom
   ```

2. **Development build (recommended):**
   ```bash
   ./scripts/dev-build.sh desktop development true
   ```

3. **Production build:**
   ```bash
   ./scripts/dev-build.sh desktop production false true
   ```

## Development Scripts

### Enhanced Development Build

The main development script provides comprehensive build capabilities:

```bash
# Development mode with hot reloading
./scripts/dev-build.sh desktop development true

# Production build with cleanup
./scripts/dev-build.sh desktop production false true

# Web-only development
./scripts/dev-build.sh web development true

# Build all platforms
./scripts/dev-build.sh all production false true
```

**Options:**
- `platform`: `desktop` | `web` | `all`
- `environment`: `development` | `production`
- `watch_mode`: `true` | `false`
- `debug_mode`: `true` | `false`
- `clean_build`: `true` | `false`

### Other Useful Scripts

```bash
# Quick development start
./scripts/start-dev.sh

# Production deployment
./scripts/deploy-production.sh

# Testing
./scripts/test-all-features.sh
```

## Desktop Development

### Tauri Backend

The desktop app uses Tauri with Rust for system integration:

**Key Features:**
- File system access
- Command execution
- System information
- Native dialogs
- System tray integration

**Main Commands:**
- `open_file_dialog` - Enhanced file picker with filters
- `execute_command` - Run system commands
- `list_directory` - Browse file system
- `get_system_info` - Platform information

### Adding New Desktop Commands

1. **Define in Rust (`src-tauri/src/main.rs`):**
   ```rust
   #[tauri::command]
   async fn my_new_command(param: String) -> Result<serde_json::Value, String> {
       // Implementation
       Ok(json!({ "success": true }))
   }
   ```

2. **Register in handler:**
   ```rust
   .invoke_handler(tauri::generate_handler![
       my_new_command,
       // other commands...
   ])
   ```

3. **Call from frontend:**
   ```typescript
   const result = await invoke('my_new_command', { param: 'value' });
   ```

## Web Development

### Next.js Frontend

The web app is built with Next.js and provides PWA capabilities:

**Key Features:**
- Server-side rendering
- API routes
- Progressive Web App
- Offline support
- Responsive design

### Development Tools

Access development utilities at `/dev-tools`:

- **System Information**: Platform details and capabilities
- **File Explorer**: Browse and edit files
- **Command Runner**: Execute system commands
- **Code Editor**: Basic file editing

## Platform-Specific Features

### Desktop-Only Features

```typescript
// Check if running in desktop
const isDesktop = platform.isDesktop();

// Use desktop-specific features
if (isDesktop) {
    const systemInfo = await invoke('get_system_info');
    const files = await invoke('list_directory', { path: '/some/path' });
}
```

**Available Desktop Features:**
- System tray integration
- Global keyboard shortcuts
- File system access
- Hardware acceleration
- Background services
- Auto-start capabilities
- Offline mode
- Voice processing
- Wake word detection

### Web-Only Features

```typescript
// Check if running in web
const isWeb = platform.isWeb();

// Use web-specific features
if (isWeb) {
    // Service worker operations
    // Push notifications
    // IndexedDB access
}
```

**Available Web Features:**
- Service workers
- Push notifications
- IndexedDB storage
- Real-time sync
- Collaborative editing
- Multi-device access
- Cloud backup
- Progressive Web App

## Build Process

### Development Build

1. **Dependency Check**: Verify all required tools
2. **Clean Build** (optional): Remove previous builds
3. **Install Dependencies**: npm and cargo dependencies
4. **Build Frontend**: Next.js development build
5. **Build Desktop**: Tauri development build
6. **Health Checks**: Verify services are running

### Production Build

1. **Clean Build**: Remove all previous artifacts
2. **Install Dependencies**: Fresh dependency installation
3. **Build Frontend**: Next.js production build
4. **Build Desktop**: Tauri production build with bundling
5. **Package Distribution**: Create platform-specific packages

## Testing

### Running Tests

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run specific test files
npm test -- path/to/test/file
```

### Test Structure

```
frontend-nextjs/
├── tests/
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/           # End-to-end tests
```

## Deployment

### Desktop Distribution

**Windows:**
- MSI installer package
- Automatic updates

**macOS:**
- DMG disk image
- Universal binary (Intel + Apple Silicon)

**Linux:**
- AppImage (portable)
- DEB package (Debian/Ubuntu)

### Web Deployment

**Options:**
- Vercel (recommended)
- Netlify
- Self-hosted
- Docker containers

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Clean build: `./scripts/dev-build.sh desktop development false false true`
   - Check dependencies: Verify Node.js and Rust versions

2. **Desktop App Not Starting**
   - Check Tauri configuration
   - Verify frontend is running on port 3000
   - Check system permissions

3. **Web App Issues**
   - Clear browser cache
   - Check service worker registration
   - Verify API endpoints

### Debug Mode

Enable debug logging:

```bash
# Frontend debug
DEBUG=atom:* npm run dev

# Rust debug
RUST_LOG=debug npm run tauri dev
```

## Contributing

### Code Style

- TypeScript with strict type checking
- React functional components with hooks
- Consistent naming conventions
- Comprehensive error handling

### Pull Request Process

1. Create feature branch from `main`
2. Implement changes with tests
3. Run full test suite
4. Update documentation
5. Submit PR with detailed description

## Resources

- [Tauri Documentation](https://tauri.app/)
- [Next.js Documentation](https://nextjs.org/)
- [Rust Documentation](https://doc.rust-lang.org/)
- [Chakra UI Documentation](https://chakra-ui.com/)

## Support

For development issues:
1. Check this guide and existing documentation
2. Search existing issues
3. Create detailed bug report with reproduction steps
4. Include platform information and error logs