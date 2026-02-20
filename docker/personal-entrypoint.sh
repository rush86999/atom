#!/bin/bash
set -e

echo "Starting Atom Personal Edition..."

# Check if encryption key is set (not default)
if [ "$BYOK_ENCRYPTION_KEY" = "default-insecure-key-change-me" ] || [ "$BYOK_ENCRYPTION_KEY" = "default-personal-key-change-me" ] || [ -z "$BYOK_ENCRYPTION_KEY" ]; then
    echo "⚠️  WARNING: Using default encryption key!"
    echo "   Generate a secure key with: openssl rand -base64 32"
    echo "   Set BYOK_ENCRYPTION_KEY in .env file"
fi

# Check if at least one AI provider is configured
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️  WARNING: No AI provider API key configured!"
    echo "   Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY in .env"
fi

# Check local-only mode
if [ "$ATOM_LOCAL_ONLY" = "true" ]; then
    echo "ℹ️  Local-only mode ENABLED (cloud services blocked)"
    echo "   Available: Sonos, Hue, Home Assistant, FFmpeg"
else
    echo "ℹ️  Local-only mode DISABLED (cloud services available)"
    echo "   Available: All integrations (Spotify, Notion, etc.)"
fi

# Create required directories
mkdir -p /app/data/media/input
mkdir -p /app/data/media/output
mkdir -p /app/data/exports
mkdir -p /app/data/lancedb
mkdir -p /app/logs

# Check FFmpeg installation
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg installed: $(ffmpeg -version | head -n 1)"
else
    echo "⚠️  WARNING: FFmpeg not found - video/audio processing will fail"
fi

# Check Python packages
echo "✅ Personal Edition startup checks complete"
echo "🚀 Starting Atom backend..."

# Run the main command
exec "$@"
