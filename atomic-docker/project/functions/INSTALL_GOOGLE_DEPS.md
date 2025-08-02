# PyRight Compatibility Installation Guide

This guide addresses pyright import resolution errors for Google API dependencies.

## 📋 Prerequisites

Ensure you have Python 3.8+ and the correct virtual environment activated:
```bash
cd /Users/rushiparikh/projects/atom/atom/atomic-docker/project/functions
python3 --version
```

## 🔧 Installation Steps

### 1. Install Google API Dependencies
```bash
pip install -r python_api_service/requirements.txt
```

### 2. Install PyRight-Specific Dependencies
```bash
# Core Google API packages
pip install google-api-python-client>=2.0.0
pip install google-auth-authlib>=1.0.0
pip install google-auth-httplib2>=0.1.0
pip install google-auth-oauthlib>=1.0.0

# PDF processing for Google Drive
pip install PyPDF2>=3.0.0

# Authentication helpers
pip install google-auth
```

### 3. Verify Installation
```bash
python - << 'EOF'
import google.oauth2.credentials
import googleapiclient.discovery
import googleapiclient.errors
import google.auth.transport.requests
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import PyPDF2
print("✅ All Google API dependencies successfully installed")
EOF
```

## 🧪 Test PyRight Compatibility

After installation, test pyright with:

```bash
# If pyright is installed
pyright python_api_service/gdrive_service.py
pyright python_api_service/linkedin_service.py

# Optional: Install pyright if not available
npm install -g pyright
```

## 📝 Development Notes

### Type Checking Configuration
The services use `TYPE_CHECKING` imports for pyright compatibility:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
```

### Resolving Import Errors
If pyright still shows import errors after installation:

1. **Check PyRight configuration** (create `pyproject.toml` in project root):
```toml
[tool.pyright]
pythonVersion = "3.8"
exclude = ["node_modules", "__pycache__", ".venv"]
reportMissingImports = "none"  # Skip for optional dependencies
```

2. **Use virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_api_service/requirements.txt
```

3. **Verify Python path**:
```bash
python -c "import site; print(site.getsitepackages())"
```

## 🚨 Troubleshooting

### Common Issues
1. **Pylick Import errors**: Install the Google API packages globally or in the active virtual environment
2. **Module not found**: Ensure you're running from correct directory with `which python`
3. **Package conflicts**: Use `pip freeze` to check installed versions

### Debug Script
```bash
# test_gdrive.py
python -c "
import sys
print(sys.path)
try:
    from google.oauth2.credentials import Credentials
    print('✅ Google OAuth2 OK')
except ImportError as e:
    print('❌ OAuth2 Error:', e)
"
```

## 🎯 Next Steps

After successful installation:
1. Verify pyright runs without errors
2. Test the google drive service integration
3. Check that all type annotations are properly resolved

The services are designed to function whether or not Google API packages are installed (using graceful fallbacks) while maintaining pyright compatibility.