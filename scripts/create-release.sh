#!/bin/bash

# ATOM AI Web Development Studio - One-Click Release Builder
# Usage: ./scripts/create-release.sh [version]

set -e

VERSION=${1:-"0.1.0-alpha.1"}
BUILD_DIR="dist/atom-desktop-$VERSION"
NEXTJS_DIR="frontend-nextjs"
TAURI_DIR="frontend-nextjs/src-tauri"

# Ensure we are in the project root
if [ ! -d "$NEXTJS_DIR" ]; then
    echo "❌ Error: Could not find $NEXTJS_DIR. Please run this script from the project root."
    exit 1
fi

echo "🚀 Building ATOM Desktop App v$VERSION"

# Clean build directory
rm -rf dist
mkdir -p "$BUILD_DIR"

# Build Next.js
echo "🏗️  Building Next.js application..."
cd "$NEXTJS_DIR"
npm ci

# Backup config and switch to static export config
if [ -f "next.config.js" ]; then
    mv next.config.js next.config.js.bak
fi

cat > next.config.js << EOF
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
};
module.exports = nextConfig;
EOF

# Build static export
npm run build

# Restore config
rm next.config.js
if [ -f "next.config.js.bak" ]; then
    mv next.config.js.bak next.config.js
fi

# Build Tauri
echo "💻 Building desktop applications..."
# Stay in frontend-nextjs directory to run tauri
# npm run tauri build automatically looks for src-tauri
npm run tauri build

cd ..

# Copy artifacts
echo "📦 Collecting artifacts..."
# Find the created bundle
FIND_CMD="find $TAURI_DIR/target/release/bundle -type f \( -name '*.dmg' -o -name '*.app' -o -name '*.msi' -o -name '*.deb' -o -name '*.AppImage' \)"
eval $FIND_CMD | while read -r file; do
    echo "Found artifact: $file"
    cp "$file" "$BUILD_DIR/"
done

echo "✅ Release build complete in $BUILD_DIR"
