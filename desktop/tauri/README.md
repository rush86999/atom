# ATOM Desktop Application

A cross-platform desktop application built with Tauri, React, and TypeScript that provides a local-first interface for the ATOM AI Web Studio.

## Features

- 🚀 **Fast Build Times** - Uses esbuild for 2-second builds (vs 6+ minutes with Vite)
- 📱 **Cross-Platform** - Builds for macOS, Windows, and Linux
- 🎨 **Modern UI** - Built with Material-UI and React
- 🔒 **Secure** - Local-first architecture with Rust backend
- ⚡ **Performance** - Optimized bundle size and startup time

## Prerequisites

- **Node.js** 18+ and npm
- **Rust** (install via [rustup](https://rustup.rs/))
- **Tauri CLI**: `npm install -g @tauri-apps/cli`

## Development

### Setup

1. Install dependencies:
```bash
npm install
```

2. Build the application:
```bash
npm run build
```

3. Start development server:
```bash
npm run tauri dev
```

### Build for Production

```bash
npm run tauri build
```

This will create:
- macOS: `.app` bundle and `.dmg` installer
- Windows: `.exe` installer
- Linux: `.AppImage` and `.deb` packages

## Project Structure

```
src/
├── components/          # React components
│   ├── DevDashboard.tsx
│   └── MainDevInterface.tsx
├── hooks/              # Custom React hooks
│   └── useFinanceAgent.ts
├── Automations.tsx     # Automation features
├── Dashboard.tsx       # Main dashboard
├── Finance.tsx         # Financial tools
├── GitHubIntegration.ts # GitHub integration
├── SmartSearch.tsx     # Search functionality
├── web-dev-service.ts  # Web development service
└── main.tsx           # Application entry point

src-tauri/
├── main.rs            # Rust backend entry point
├── Cargo.toml         # Rust dependencies
└── tauri.conf.json    # Tauri configuration
```

## Performance Optimizations

- **Removed MUI Icons**: Replaced with text/emoji alternatives to eliminate 6+ minute build times
- **esbuild Integration**: Replaced Vite with esbuild for faster builds
- **TypeScript Only**: Removed duplicate JavaScript files
- **Bundle Optimization**: Reduced bundle size from 10+ MB to 2.3 MB

## Troubleshooting

### Common Issues

1. **Port 1420 already in use**: 
   ```bash
   lsof -ti:1420 | xargs kill
   ```

2. **Rust compilation errors**: 
   ```bash
   cargo clean && npm run build
   ```

3. **Build hangs**: Check for stuck processes and kill them:
   ```bash
   pkill -f "tauri dev"
   pkill -f "npm run tauri"
   ```

### Rust Warnings

The build may show warnings about unused imports/variables. These are safe to ignore for development but can be fixed with:

```bash
cargo fix --bin "atom"
```

## Deployment

### macOS
The build creates:
- `ATOM AI Web Studio.app` - Application bundle
- `ATOM AI Web Studio_2.0.0_x64.dmg` - Installer

### Windows
```bash
npm run tauri build -- --target x86_64-pc-windows-msvc
```

### Linux
```bash
npm run tauri build -- --target x86_64-unknown-linux-gnu
```

## Contributing

1. Follow TypeScript best practices
2. Use functional components with hooks
3. Keep bundle size minimal
4. Test on multiple platforms
5. Update this README with changes

## License

AGPL-3.0 - See LICENSE file for details