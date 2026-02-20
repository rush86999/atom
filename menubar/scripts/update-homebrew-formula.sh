#!/bin/bash

# Script to update Homebrew formula with new release
# Usage: ./scripts/update-homebrew-formula.sh <version> <architecture>

set -e

VERSION="${1:-latest}"
ARCH="${2:-aarch64}"

REPO_OWNER="rush86999"
REPO_NAME="atom"
FORMULA_FILE="Formula/atom-menubar.rb"

echo "Updating Homebrew formula for Atom Menu Bar v${VERSION} (${ARCH})..."

# Get the release info
if [ "$VERSION" == "latest" ]; then
  RELEASE_INFO=$(curl -s "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest")
  VERSION=$(echo "$RELEASE_INFO" | jq -r '.tag_name' | sed 's/v//')
else
  RELEASE_INFO=$(curl -s "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/tags/v${VERSION}")
fi

# Get the download URL
DOWNLOAD_URL=$(echo "$RELEASE_INFO" | jq -r ".assets[] | select(.name | contains(\"${ARCH}\") and endswith(\".dmg\")) | .browser_download_url")

if [ -z "$DOWNLOAD_URL" ]; then
  echo "Error: Could not find DMG for ${VERSION} (${ARCH})"
  exit 1
fi

echo "Download URL: ${DOWNLOAD_URL}"

# Download the DMG to calculate SHA256
TEMP_DMG=$(mktemp)
curl -L -o "$TEMP_DMG" "$DOWNLOAD_URL"

# Calculate SHA256
SHA256=$(shasum -a 256 "$TEMP_DMG" | awk '{print $1}')
echo "SHA256: ${SHA256}"

# Clean up
rm -f "$TEMP_DMG"

# Update the formula
sed -i.bak "s|url \".*\"|url \"${DOWNLOAD_URL}\"|" "$FORMULA_FILE"
sed -i.bak "s|version \".*\"|version \"${VERSION}\"|" "$FORMULA_FILE"
sed -i.bak "s|sha256 \".*\"|sha256 \"${SHA256}\"|" "$FORMULA_FILE"

# Remove backup
rm -f "${FORMULA_FILE}.bak"

echo "✓ Homebrew formula updated successfully"
echo "  Version: ${VERSION}"
echo "  Architecture: ${ARCH}"
echo "  SHA256: ${SHA256}"
echo ""
echo "To test the formula:"
echo "  brew install --build-from-source ${FORMULA_FILE}"
echo ""
echo "To commit the changes:"
echo "  git add ${FORMULA_FILE}"
echo "  git commit -m \"chore(homebrew): update formula to v${VERSION}\""
echo "  git push"
