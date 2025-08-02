# IDE PyRight Setup Guide

This guide will help you resolve pyright errors by properly configuring your IDE and Python environment.

## 🔧 Step 1: Create Virtual Environment

```bash
# From project root
cd /Users/rushiparikh/projects/atom/atom

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows

# Ensure pip is up to date
pip install --upgrade pip
```

## 🔧 Step 2: Install Google API Dependencies

```bash
# Install all required dependencies
pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 PyPDF2

# Or install from requirements
pip install -r atomic-docker/project/functions/python_api_service/requirements.txt
```

## 🔧 Step 3: Verify Installation

```bash
python -c "
import sys
print('Python executable:', sys.executable)
print('Python version:', sys.version)

try:
    import google.oauth2.credentials
    import googleapiclient.discovery
    import googleapiclient.errors
    import google.auth.transport.requests
    import PyPDF2
    print('✅ All Google API packages successfully imported!')
except ImportError as e:
    print('❌ Import error:', e)
    sys.exit(1)
"
```

## 🔧 Step 4: Configure IDE Settings

### VS Code:
1. **Install PyRight extension** if not already installed
2. **Open Command Palette** → `Python: Select Interpreter`
3. **Choose**: `.venv/bin/python` (should detect automatically)
4. **Create `.vscode/settings.json`**:
```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.analysis.typeCheckingMode": "standard",
  "python.analysis.diagnosticSeverityOverrides": {
    "reportMissingImports": "none"
  }
}
```

### PyCharm:
1. **File** → **Settings** → **Python Interpreter**
2. **Add Interpreter** → **Existing environment** → Select `.venv/bin/python`
3. **Install packages** via interpreter settings

## 🔧 Step 5: PyRight Configuration

Create or update `pyproject.toml` in project root:

```toml
[tool.pyright]
include = ["atomic-docker/project/functions"]
exclude = ["**/node_modules/**", "**/.venv/**", "**/__pycache__/**"]
pythonVersion = "3.8"
typeCheckingMode = "standard"
reportMissingImports = "none"
```

## 🔧 Step 6: Environment Verification Script

Save this as `test_installation.py` in your project root:

```python
#!/usr/bin/env python3
"""
Test script to verify pyright compatibility
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
functions_dir = project_root / "atomic-docker" / "project" / "functions"

# Test imports
test_modules = [
    "google.oauth2.credentials",
    "googleapiclient.discovery", 
    "googleapiclient.errors",
    "google.auth.transport.requests",
    "googleapiclient.http",
    "PyPDF2"
]

print("Testing PyRight compatibility...")
print(f"Project root: {project_root}")
print(f"Python executable: {sys.executable}\n")

for module in test_modules:
    try:
        __import__(module)
        print(f"✅ {module}")
    except ImportError as e:
        print(f"❌ {module}: {e}")
        print("   Run: pip install google-api-python-client google-auth PyPDF2")

print("\n✏️  Next steps:")
print("1. Activate venv: source .venv/bin/activate")
print("2. Run python test_installation.py to verify")
print("3. Restart your IDE after configuration")
```

## 🔧 Step 7: Troubleshooting Common Issues

### Issue: "Import ... could not be resolved"
**Solution**: Ensure virtual environment is activated and packages installed:
```bash
source .venv/bin/activate
pip list | grep google
```

### Issue: VS Code shows red underlines
**Solution**: Reload window after setting interpreter:
1. Close VS Code
2. Reopen from project root
3. Check bottom-left Python interpreter (should show .venv)

### Issue: PyCharm doesn't recognize packages
**Solution**: 
1. **File** → **Invalidate Caches**
2. **Restart IDE**
3. Check Python interpreter setting

## 🎯 Quick Setup Commands

Copy and paste these commands:

```bash
# One-time setup
cd /Users/rushiparikh/projects/atom/atom
python3 -m venv .venv
source .venv/bin/activate
pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 PyPDF2
python test_installation.py
```

After following these steps, your IDE should no longer show pyright import errors for Google API packages.