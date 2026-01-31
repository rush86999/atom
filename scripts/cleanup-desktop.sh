#!/bin/bash

# ATOM Desktop Implementation Cleanup Script
# This script removes redundant desktop implementations to consolidate to a single Tauri app

set -e

echo "🧹 ATOM Desktop Implementation Cleanup"
echo "======================================"

# Check if we're in the project root
if [ ! -d "frontend-nextjs/src-tauri" ]; then
    echo "❌ Error: Must run from project root directory"
    echo "   frontend-nextjs/src-tauri not found"
    exit 1
fi

echo ""
echo "📋 Current desktop implementations found:"
echo "   ✅ frontend-nextjs/src-tauri/ (Primary Tauri - CONSOLIDATED)"
if [ -d "desktop/tauri" ]; then
    echo "   ⚠️  desktop/tauri/ (Redundant Tauri)"
fi
if [ -d "desktop" ] && [ ! -d "desktop/tauri" ]; then
    echo "   ⚠️  desktop/ (Electron)"
fi

echo ""
read -p "🚨 This will PERMANENTLY remove redundant desktop implementations. Continue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

echo ""
echo "🗑️  Starting cleanup..."

# Remove redundant Tauri implementation
if [ -d "desktop/tauri" ]; then
    echo "   Removing desktop/tauri/..."
    rm -rf desktop/tauri/
    echo "   ✅ Removed desktop/tauri/"
fi

# Note: frontend-nextjs/src-tauri is now the PRIMARY implementation
# Do not remove it!

# Archive Electron implementation (optional)
if [ -d "desktop" ] && [ ! -d "desktop/tauri" ]; then
    echo ""
    read -p "📦 Archive Electron implementation to desktop-electron-archive/? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Archiving desktop/ to desktop-electron-archive/..."
        mv desktop/ desktop-electron-archive/
        echo "   ✅ Archived Electron implementation"
    else
        echo "   ℹ️  Electron implementation kept as desktop/"
    fi
fi

echo ""
echo "✅ Cleanup completed!"
echo ""
echo "📋 Remaining implementation:"
echo "   ✅ frontend-nextjs/src-tauri/ (Primary Tauri implementation)"
echo ""
echo "🔧 Next steps:"
echo "   1. Test Tauri build: cd frontend-nextjs/src-tauri && cargo check"
echo "   2. Test frontend build: cd frontend-nextjs && npm run build"
echo "   3. Build desktop app: cd frontend-nextjs && npm run tauri build"
echo ""
echo "📚 See .archive/tauri-root-dev-2025-01-30/README.md for consolidation details"
