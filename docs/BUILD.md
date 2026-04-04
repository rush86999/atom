# Atom Build Guide

This guide explains how to build Atom from source, including both frontend (Next.js) and backend (Python) components.

## Quick Start

```bash
# Frontend build
cd frontend-nextjs
npm install
npm run build

# Backend build
cd backend
pip install -e .
# OR for production package:
python -m build
```

## Prerequisites

### System Requirements

- **Operating System**: macOS, Linux, or Windows (WSL2 recommended)
- **Disk Space**: 5GB free minimum (10GB recommended for node_modules and Python packages)
- **Memory**: 8GB RAM minimum (16GB recommended)

### Software Requirements

#### Frontend
- **Node.js**: 20.x (verify with `node --version`)
- **npm**: 10.x (verify with `npm --version`)

#### Backend
- **Python**: 3.11+ (tested with 3.11, 3.14) - verify with `python3 --version`
- **pip**: Latest version - verify with `pip --version`
- **build**: Python build tool - install with `pip install build`
- **virtualenv** (optional but recommended): `pip install virtualenv`

### Installing Prerequisites

#### macOS
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Node.js
brew install node

# Install Python 3.11+
brew install python@3.11
```

#### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Python build tools
pip3 install --upgrade pip
pip3 install build
```

#### Windows (WSL2)
```bash
# Enable WSL2 (requires Windows 10/11)
wsl --install

# After WSL2 is installed, follow Ubuntu instructions above
```

## Frontend Build

### Location
`frontend-nextjs/`

### Development Build

For local development with hot-reload:

```bash
cd frontend-nextjs
npm install
npm run dev
```

The development server starts on `http://localhost:3000`

### Production Build

Create optimized production bundle:

```bash
cd frontend-nextjs
npm install
npm run build
```

The production build:
- Creates `.next/` directory with optimized assets
- Minifies JavaScript and CSS
- Optimizes images and fonts
- Generates static pages where possible

**Build Time**: ~10-15 minutes (first build), ~2-5 minutes (incremental)

### Run Production Build

After building, start the production server:

```bash
cd frontend-nextjs
npm run start
```

Or use the production start script:

```bash
cd frontend-nextjs
npm run prod:start
```

### Frontend Build Scripts

| Script | Purpose |
|--------|---------|
| `npm run dev` | Start development server with hot-reload |
| `npm run build` | Create production build |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |
| `npm run test` | Run Jest tests |
| `npm run test:coverage` | Run tests with coverage report |
| `npm run type-check` | Run TypeScript type checking |
| `npm run analyze` | Analyze bundle size |

### Troubleshooting Frontend Build

#### SWC Binary Error
```
Failed to load SWC binary for darwin/x64
```

**Solution**: Install the correct SWC binary for your platform
```bash
# Check Next.js version
npm list next

# Install matching SWC package (example for Next.js 16.2.2)
npm install @next/swc-darwin-x64@16.2.2
# OR for Linux:
npm install @next/swc-linux-x64@16.2.2
```

#### Version Mismatch Error
```
Error: Mismatching @next/swc version
```

**Solution**: Ensure all `@next/swc-*` packages match Next.js version exactly
```bash
# Remove all SWC packages
npm uninstall @next/swc-*

# Reinstall (will auto-install correct versions)
npm install
```

#### Minification/Truncation Error
```
ReferenceError: [truncated variable] is not defined
```

**Solution**: This is typically a SWC minification bug. Clear cache and rebuild:
```bash
# Clear Next.js cache
rm -rf .next

# Clear npm cache
rm -rf node_modules/.cache

# Rebuild
npm run build
```

#### Source File Corruption Error
```
Error: Unexpected token in source file
```

**Solution**: Check for corrupted source files (plan 247-02 fixed `AgentWorkflowGenerator.tsx:730`):
```bash
# Check for obvious syntax errors
npm run type-check

# If found, fix the corrupted line and rebuild
```

#### Out of Memory Error
```
JavaScript heap out of memory
```

**Solution**: Increase Node.js memory limit
```bash
# Development (already configured in package.json)
NODE_OPTIONS='--max-old-space-size=4096' npm run dev

# Build
NODE_OPTIONS='--max-old-space-size=4096' npm run build
```

#### Module Not Found Error
```
Module not found: Can't resolve '@my/module'
```

**Solution**: Reinstall dependencies
```bash
rm -rf node_modules package-lock.json
npm install
```

## Backend Build

### Location
`backend/`

### Development Setup

Install in editable mode (for local development):

```bash
cd backend

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .
```

This:
- Installs all dependencies from `setup.py`
- Creates symlinks to source code (changes take effect immediately)
- Registers `atom-os` CLI command

### Production Build

Create distributable Python packages:

```bash
cd backend

# Ensure build tools are installed
pip install build twine

# Build package
python -m build
```

This creates:
- `dist/atom_os-0.1.0-py3-none-any.whl` - Binary distribution
- `dist/atom-os-0.1.0.tar.gz` - Source distribution

**Build Time**: ~1-2 minutes

### Verification

Verify backend syntax and imports:

```bash
# Check syntax of all Python files
python3 -m py_compile backend/**/*.py

# Collect tests (verifies imports work)
cd backend
python3 -m pytest --collect-only

# Run basic import test
python3 -c "from core.agent_governance_service import AgentGovernanceService"
```

### Backend Build Scripts

| Command | Purpose |
|---------|---------|
| `pip install -e .` | Install in editable mode (development) |
| `python -m build` | Create distributable packages (production) |
| `python3 -m py_compile <file>` | Check syntax of specific file |
| `pytest --collect-only` | Verify test suite can be loaded |

### Troubleshooting Backend Build

#### Syntax Error
```
SyntaxError: expected 'except' or 'finally' block
File "asana_service.py", line 148
```

**Solution**: Check for unmatched try-except blocks
```bash
# Find syntax errors
python3 -m py_compile backend/integrations/asana_service.py

# Use Python AST parser for detailed error
python3 -m ast backend/integrations/asana_service.py

# Fix unmatched blocks (plan 247-01 fixed this)
```

#### Import Error
```
ModuleNotFoundError: No module named 'core'
```

**Solution**: Install package in editable mode
```bash
cd backend
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="/path/to/atom/backend:$PYTHONPATH"
```

#### Build Tool Missing
```
/usr/bin/python3: No module named build
```

**Solution**: Install build tools
```bash
pip install --upgrade pip
pip install build twine
```

#### Dependency Conflict
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed
```

**Solution**: Use virtual environment
```bash
# Create fresh virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

#### Python Version Too Old
```
ERROR: Package 'atom-os' requires a different Python: 3.9.x not in '>=3.11'
```

**Solution**: Upgrade Python
```bash
# macOS
brew install python@3.11

# Ubuntu
sudo apt install python3.11

# Verify
python3.11 --version
```

## Full Build (Both Components)

To build both frontend and backend in one sequence:

```bash
#!/bin/bash
set -e  # Exit on error

echo "=== Building Atom ==="

# Frontend
echo "Building frontend..."
cd frontend-nextjs
npm install
npm run build
cd ..

# Backend
echo "Building backend..."
cd backend
python3 -m build
cd ..

echo "=== Build complete! ==="
```

Save as `build-all.sh`, make executable with `chmod +x build-all.sh`, and run with `./build-all.sh`.

## Continuous Integration

The CI/CD pipeline automatically builds on:
- Every push to `main` branch
- Pull requests to `main`
- Manual trigger via GitHub Actions

### CI Build Workflow

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build frontend
        run: |
          cd frontend-nextjs
          npm install
          npm run build
      - name: Build backend
        run: |
          cd backend
          python -m build
```

See `.github/workflows/` for complete CI configuration.

## Build Times

| Component | First Build | Incremental Build |
|-----------|-------------|-------------------|
| Frontend  | ~10-15 min  | ~2-5 min          |
| Backend   | ~1-2 min    | ~10-30 sec        |
| Both      | ~12-17 min  | ~3-7 min          |

**Factors affecting build time**:
- CPU cores and clock speed
- SSD vs HDD storage
- Network speed (for dependency downloads)
- Operating system file system performance

## Environment Variables

### Frontend Environment

Required for frontend builds:

```bash
# See frontend-nextjs/.env.example
cp frontend-nextjs/.env.example frontend-nextjs/.env.local

# Edit .env.local with your values
NEXT_PUBLIC_API_URL=http://localhost:8000
# ... other variables
```

### Backend Environment

Required for backend builds:

```bash
# See backend/.env.example
cp backend/.env.example backend/.env

# Edit .env with your values
DATABASE_URL=sqlite:///./atom_dev.db
OPENAI_API_KEY=sk-...
# ... other variables
```

## Platform-Specific Notes

### macOS
- Homebrew is the recommended package manager
- Python 3 from Homebrew is recommended over system Python
- Xcode Command Line Tools required: `xcode-select --install`

### Linux
- System Python may be too old, install Python 3.11+ via deadsnakes PPA
- Node.js 20.x from NodeSource repository
- Virtual environment strongly recommended

### Windows (WSL2)
- WSL2 is required for native compatibility
- Avoid native Windows builds (use WSL2)
- Git for Windows and WSL2 git integration recommended

## Next Steps

After building successfully:

- **Run Tests**: See `TESTING.md` (if exists) or run `pytest backend/` and `npm test` (frontend)
- **Development Setup**: See `DEVELOPMENT.md` (if exists)
- **Deployment**: See `backend/docs/DEPLOYMENT_RUNBOOK.md`
- **Local Development**: Use Personal Edition (see `docs/PERSONAL_EDITION.md`)

## Additional Resources

- **Frontend Docs**: `frontend-nextjs/README.md` (if exists)
- **Backend Docs**: `backend/docs/`
- **Deployment**: `backend/docs/DEPLOYMENT_RUNBOOK.md`
- **Operations**: `backend/docs/OPERATIONS_GUIDE.md`
- **Troubleshooting**: `backend/docs/TROUBLESHOOTING.md`
- **Personal Edition**: `docs/PERSONAL_EDITION.md`

## Common Issues and Solutions

### Issue: "Cannot build - out of disk space"
**Solution**: Clean up build artifacts
```bash
# Frontend
rm -rf frontend-nextjs/.next frontend-nextjs/node_modules

# Backend
rm -rf backend/dist backend/build backend/*.egg-info

# Then rebuild selectively
```

### Issue: "Build works locally but fails in CI"
**Solution**: Check for environment-specific dependencies
```bash
# Compare local vs CI Python versions
python3 --version

# Check for local-only dependencies
pip list | grep -i "my-local-package"
```

### Issue: "Incremental build not working"
**Solution**: Clear all caches
```bash
# Frontend
rm -rf frontend-nextjs/.next frontend-nextjs/node_modules/.cache

# Backend
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

---

**Last Updated**: 2026-04-03
**Maintained By**: Atom Development Team
**Related Docs**: CLAUDE.md, README.md, backend/docs/
