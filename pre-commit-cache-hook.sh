#!/bin/bash
# Pre-commit hook to prevent Python cache conflicts
# Place in .git/hooks/pre-commit or use with pre-commit framework

echo "🔧 Cleaning Python cache files to prevent conflicts..."

# Remove all Python cache files from staging area
git rm -rf --cached $(git ls-files --cached -i -X .gitignore 2>/dev/null | grep -E '\.(pyc|__pycache__|\.pyo|\.pyd)$' || true) >/dev/null 2>&1 || true

# Clean up __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type f -name "*.pyd" -delete 2>/dev/null || true

# Clean up other development cache directories
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true

# Clean npm/yarn cache files that might cause issues
find . -name "node_modules/.cache" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".next/cache" -type d -exec rm -rf {} + 2>/dev/null || true

# Clean macOS system files
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "._*" -delete 2>/dev/null || true
find . -name "Thumbs.db" -delete 2>/dev/null || true
find . -name "ehthumbs.db" -delete 2>/dev/null || true

echo "✅ Cache files cleaned successfully - preventing future conflicts"

# Ensure .gitignore patterns are committed
git add .gitignore 2>/dev/null || true

exit 0
