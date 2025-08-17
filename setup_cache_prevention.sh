#!/bin/bash
# Setup script to prevent Python cache conflicts in git
# Run this once to configure repository-wide cache prevention

echo "🔧 Setting up cache conflict prevention for the repository..."

# Create enhanced .gitignore section for Python cache prevention
cat >> .gitignore << 'EOF'

# === CACHE CONFLICT PREVENTION ===
# Systematically prevent .pyc, __pycache__, and build artifacts
**/__pycache__/
**/*.py[ocd]
**/*.pyd
**/*.so
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
**/.hypothesis/
**/.coverage*
**/coverage.xml
**/.DS_Store
**/._*
**/Thumbs.db
**/ehthumbs.db
**/*.tmp
**/*.backup
**/*.orig
**/*.rej

# Build artifacts (systematically exclude)
**/build/
**/develop-eggs/
**/dist/
**/downloads/
**/eggs/
**/.eggs/
**/lib/
**/lib64/
**/parts/
**/sdist/
**/var/
**/wheels/
**/share/python-wheels/
**/*.egg-info/
**/.installed.cfg

# Development tool caches
**/.pip-cache/
**/.cache/
**/.parcel-cache/
**/.next/cache/
**/node_modules/.cache/
**/dist/prod/
EOF

# Check if git hooks directory exists and set up the hook
if [ -d ".git/hooks" ]; then
    echo "📁 Setting up pre-commit hook in .git/hooks..."

    # Create the pre-commit hook
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Pre-commit hook to prevent Python cache conflicts

echo "🔧 Preventing cache conflicts..."

# Function to safely remove cache files
cleanup_cache() {
    local files_removed=0

    # Remove all staged cache files
    local cached_ignore=$(git ls-files --cached -i -X .gitignore | grep -E '\.(pyc|__pycache__|\.pyo|\.pyd)$' || true)
    if [ -n "$cached_ignore" ]; then
        echo "⚠️  Found staged cache files - removing from git:"
        echo "$cached_ignore"
        git rm --cached $(echo "$cached_ignore") >/dev/null 2>&1
        files_removed=1
    fi

    # Clean up __pycache__ directories and files
    local cache_dirs=$(find . -type d -name "__pycache__" -not -path "./.git/*" 2>/dev/null || true)
    local pyc_files=$(find . -type f -name "*.pyc" -not -path "./.git/*" 2>/dev/null || true)

    if [ -n "$cache_dirs" ] || [ -n "$pyc_files" ]; then
        echo "🧹 Cleaning __pycache__ directories and .pyc files..."
        find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -not -path "./.git/*" -delete 2>/dev/null || true
        find . -type f -name "*.pyo" -not -path "./.git/*" -delete 2>/dev/null || true
        files_removed=1
    fi

    # Clean development tool caches
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true

    return $files_removed
}

# If cache files were removed, warn but allow commit
if cleanup_cache; then
    echo "✅ Cache files cleaned - commit can proceed"
fi

# Verify no cache files are accidentally staged
if git diff --cached --name-only | grep -E '\.(pyc|__pycache__)$'; then
    echo "❌ Cache files detected in commit - please remove them first"
    echo "Run: find . -name '__pycache__' -type d -delete && find . -name '*.pyc' -delete"
    exit 1
fi

exit 0
EOF

    chmod +x .git/hooks/pre-commit
    echo "✅ Pre-commit hook installed in .git/hooks/pre-commit"
else
    echo "⚠️  Git hooks directory not found, skipping auto-installation"
fi

# Update gitattributes to avoid binary conflicts
cat > .gitattributes << 'EOF'
# Prevent merge conflicts for generated files
*.pyc binary
*.pyo binary
*.pyd binary
*.so binary
__pycache__/ export-ignore
*.log export-ignore

# Ensure consistent line endings
*.py text eol=lf
*.jsx text eol=lf
*.tsx text eol=lf
*.js text eol=lf
*.ts text eol=lf

# Binary files
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.woff binary
*.woff2 binary
*.ttf binary
EOF

echo "✅ Enhanced .gitattributes for better merge handling"

# Clean current workspace of any cache files
echo "🧹 Cleaning current workspace..."
find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -not -path "./.git/*" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -not -path "./.git/*" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".next/cache" -exec rm -rf {} + 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true

echo "🎯 Cache conflict prevention setup complete!"
echo ""
echo "📋 Instructions:"
echo "1. Run this script: ./setup_cache_prevention.sh"
echo "2. If you don't have .git/hooks, manually add the hook scripts"
echo "3. Consider installing pre-commit framework for team-wide enforcement"
echo "4. Cache conflicts are now prevented automatically ✅"

echo ""
echo "🔧 Next steps:"
echo "- Install pre-commit if you want a more comprehensive solution:"
echo "  pip install pre-commit"
echo "  pre-commit install"
echo "  pre-commit run --all-files"
