#!/bin/bash

# ATOM AI Web Development Studio - One-Click Release Builder
# Creates complete distribution for end users (desktop + cloud setup)
# Usage: ./create-release.sh [version]

set -euo pipefail

VERSION=${1:-$(date +%Y.%m.%d)}
BUILD_DIR="dist/atom-web-dev-studio-$VERSION"
DESKTOP_DIR="desktop/tauri"
NEXTJS_DIR="atomic-docker/app_build_docker"

echo "🚀 Building ATOM AI Web Development Studio v$VERSION"
echo "📦 This creates user-ready distribution (zero local setup required)"

# Clean build directory
rm -rf dist
mkdir -p "$BUILD_DIR"

# Build Next.js cloud application
echo "🏗️  Building cloud application..."
cd "$NEXTJS_DIR"
npm ci --silent
npm run build
npm run export
cd ../..

# Copy cloud application
echo "📋 Preparing cloud components..."
cp -r "$NEXTJS_DIR/out" "$BUILD_DIR/cloud-app"

# Build desktop app for all platforms
echo "💻 Building desktop applications..."
cd "$DESKTOP_DIR"
npm ci
npm run tauri build -- --target universal-apple-darwin
npm run tauri build -- --target x86_64-pc-windows-msvc
npm run tauri build -- --target x86_64-unknown-linux-gnu
cd ../..

# Package desktop builds
echo "📱 Creating platform packages..."

# Windows
cp "$DESKTOP_DIR/target/release/bundle/msi/ATOM AI Web Studio*.msi" "$BUILD_DIR/ATOM-WebDev-Studio-$VERSION-Windows-x64.msi"

# macOS
cp "$DESKTOP_DIR/target/universal-apple-darwin/release/bundle/dmg/ATOM AI Web Studio*.dmg" "$BUILD_DIR/ATOM-WebDev-Studio-$VERSION-macOS.dmg"

# Linux
cp "$DESKTOP_DIR/target/release/bundle/deb/atom-ai-web-studio*.deb" "$BUILD_DIR/ATOM-WebDev-Studio-$VERSION-Linux-x64.deb"
cp "$DESKTOP_DIR/target/release/bundle/appimage/atom-ai-web-studio*.AppImage" "$BUILD_DIR/ATOM-WebDev-Studio-$VERSION-Linux-x64.AppImage"

# Create unified configuration
cat > "$BUILD_DIR/config.json" << EOF
{
  "name": "ATOM AI Web Development Studio",
  "version": "$VERSION",
  "tagline": "Build modern web applications through conversation",
  "features": [
    "Zero local setup required",
    "Cloud-only builds with live previews",
    "9 AI agent team collaboration",
    "Real-time deployment monitoring",
    "Performance optimization included",
    "GitHub auto-integration",
    "Cross-platform desktop app"
  ],
  "cloud_resources": {
    "primary": "Vercel Free Tier",
    "capacity": "100GB/month bandwidth",
    "build_time": "<2 minutes cold, <15s incremental",
    "preview_urls": "every commit/draft"
  },
  "installation": {
    "Windows": "Run ATOM-WebDev-Studio-*.msi",
+    "macOS": "Drag ATOM-WebDev-Studio-*.dmg to Applications",
+    "Linux": "Run ATOM-WebDev-Studio-*.AppImage"
+  },
+  "getting_started": {
+    "1": "Open the desktop app",
+    "2": "Type what you want to build",
+    "3": "Wait for cloud deployment",
+    "4": "Share live preview URLs"
+  }
+}
+EOF

# Create README for end users
cat > "$BUILD_DIR/INSTALL.md" << EOF
# ATOM AI Web Development Studio - Zero Setup Guide

## 🎯 What This Is
A complete web development workflow that works purely through conversation and cloud infrastructure.

✅ **No local Node.js** required
✅ **No build tools** to install
✅ **Real-time cloud builds** with live previews
✅ **9 AI agents** working together on every request

## 🔧 Installation

### Windows
1. Run `ATOM-WebDev-Studio-${VERSION}-Windows-x64.msi`
2. Complete setup wizard
3. Open from Start Menu

### macOS
1. Open `ATOM-WebDev-Studio-${VERSION}-macOS.dmg`
2. Drag ATOM Web Studio to Applications
3. Launch from Applications folder

### Linux
1. Make AppImage executable: `chmod +x ATOM-WebDev-Studio-${VERSION}-Linux-x64.AppImage`
2. Run: `./ATOM-WebDev-Studio-${VERSION}-Linux-x64.AppImage`

## 🚀 Your First Project

1. **Open** ATOM Web Studio
2. **Type**: "Create SaaS landing page"
3. **Watch**: Cloud build starts immediately
4. **Receive**: Live preview
