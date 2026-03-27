# Desktop Testing

Comprehensive testing suite for Atom desktop application (Tauri-based).

## Overview

This directory contains tests for the Atom desktop application built with Tauri. Tests cover:

- **Window Management** - Minimize, maximize, resize, close, title, always on top
- **Native Features** - File system access, dialogs, system tray, notifications
- **Cross-Platform Behavior** - Platform-specific paths, shortcuts, menu bar, decorations

Tests are designed to work across Windows, macOS, and Linux with graceful degradation when Tauri runtime is unavailable.

## Prerequisites

### Required

- **Python 3.11+** - For running pytest
- **pytest** - Test framework: `pip install pytest`
- **Rust & Cargo** - For building Tauri app: https://www.rust-lang.org/tools/install

### Platform-Specific Dependencies

#### macOS
No additional dependencies required. Tauri works out of the box.

#### Linux
Install WebView dependencies:
```bash
# Ubuntu/Debian
sudo apt install libwebkit2gtk-4.0-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev

# Fedora
sudo dnf install webkit2gtk3-devel gtk3-devel libappindicator-gtk3-devel

# Arch Linux
sudo pacman -S webkit2gtk gtk3 libappindicator-gtk3
```

#### Windows
Install [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (usually pre-installed on Windows 10+).

### Optional - For Running Tests

- **TAURI_CI=true** - Set environment variable to enable Tauri tests in CI
- **TAURI_APP_PATH** - Set to Tauri app binary path if auto-detection fails

## Installation

```bash
# Install pytest
pip install pytest

# (Optional) Install in development environment
cd backend
pip install -e .
```

## Running Tests

### Run All Desktop Tests

```bash
# From project root
pytest desktop/tests/ -v

# With coverage
pytest desktop/tests/ --cov=desktop --cov-report=html
```

### Run Specific Test Files

```bash
# Window management tests
pytest desktop/tests/test_window_management.py -v

# Native features tests
pytest desktop/tests/test_native_features.py -v

# Cross-platform tests
pytest desktop/tests/test_cross_platform.py -v
```

### Run Specific Tests

```bash
# Run specific test
pytest desktop/tests/test_window_management.py::TestWindowMinimize::test_window_minimize -v

# Run tests matching pattern
pytest desktop/tests/ -k "minimize" -v

# Run tests for specific platform (requires TAURI_CI=true)
TAURI_CI=true pytest desktop/tests/test_cross_platform.py::TestPlatformMenuBar::test_platform_menu_bar_macos -v
```

### Run Tests on Specific Platform

```bash
# macOS tests (will skip on other platforms)
pytest desktop/tests/ -v -k "macos"

# Windows tests (will skip on other platforms)
pytest desktop/tests/ -v -k "windows"

# Linux tests (will skip on other platforms)
pytest desktop/tests/ -v -k "linux"
```

## Test Categories

### 1. Window Management Tests (`test_window_management.py`)

Tests for Tauri window operations:

- **WINM-01**: Window minimize/unminimize
- **WINM-02**: Window maximize/unmaximize
- **WINM-03**: Window close (app continues running)
- **WINM-04**: Window resize
- **WINM-05**: Window title change
- **WINM-06**: Window always on top
- **WINM-07**: Window position change
- **WINM-08**: Window hide/show

**Total**: 8 tests

### 2. Native Features Tests (`test_native_features.py`)

Tests for Tauri native feature integration:

- **NFS-01**: File system read text
- **NFS-02**: File system write text
- **NFS-03**: File system read binary
- **NFS-04**: File system exists check
- **NFS-05**: File system remove
- **NFS-06**: File open dialog
- **NFS-07**: File save dialog
- **NFS-08**: Message dialog
- **NFS-09**: System tray icon
- **NFS-10**: System tray menu
- **NFS-11**: System tray menu actions
- **NFS-12**: Native notification send
- **NFS-13**: Native notification with icon

**Total**: 13 tests

### 3. Cross-Platform Tests (`test_cross_platform.py`)

Tests for platform-specific behavior:

- **XP-01**: Platform-specific app data paths
- **XP-02**: Platform-specific cache paths
- **XP-03**: Platform-specific config paths
- **XP-04**: Platform-specific quit shortcuts
- **XP-05**: Platform-specific close shortcuts
- **XP-06**: Platform-specific preferences shortcuts
- **XP-07**: macOS menu bar
- **XP-08**: Windows menu bar
- **XP-09**: Linux menu bar
- **XP-10**: macOS window decorations
- **XP-11**: Windows window decorations
- **XP-12**: Linux window decorations
- **XP-13**: macOS startup behavior
- **XP-14**: Windows startup behavior
- **XP-15**: Linux startup behavior

**Total**: 15 tests

## Fixtures

### Core Fixtures

#### `platform_info`
Provides platform information for testing.

**Returns**:
```python
{
    "platform": "darwin" | "linux" | "windows",
    "is_test": True,
    "arch": "x86_64" | "arm64",
    "tauri_available": bool
}
```

**Usage**:
```python
def test_something(platform_info):
    assert platform_info["platform"] == "darwin"
```

#### `tauri_app`
Builds and spawns Tauri app for testing.

**Behavior**:
- Checks `TAURI_CI=true` environment variable
- Builds Tauri app if needed (`cargo build`)
- Spawns Tauri app process
- Yields `TauriApp` wrapper
- Cleanup: terminates app after tests

**Usage**:
```python
def test_something(tauri_app):
    assert tauri_app is not None
    assert tauri_app.is_running
```

#### `tauri_window`
Gets main window handle for Tauri app.

**Returns**:
```python
{
    "id": "main",
    "title": "Atom",
    "width": 1280,
    "height": 720,
    "is_visible": True,
    "is_minimized": False,
    "is_maximized": False,
    "is_always_on_top": False,
    "x": 100,
    "y": 100
}
```

**Usage**:
```python
def test_window_resize(tauri_window):
    tauri_window["width"] = 1200
    tauri_window["height"] = 800
    assert tauri_window["width"] == 1200
```

#### `tauri_app_handle`
Gets AppHandle for Tauri app.

**Returns**:
```python
{
    "app_id": "com.atom.desktop",
    "app_name": "Atom",
    "version": "1.0.0",
    "fs_api": {...},
    "dialog_api": {...},
    "notification_api": {...},
    "tray_api": {...}
}
```

**Usage**:
```python
def test_file_system(tauri_app_handle):
    assert tauri_app_handle["fs_api"]["read_text"] is True
```

#### `tauri_test_data_dir`
Creates temporary test data directory.

**Behavior**:
- Creates `test_read.txt` with "Hello, Tauri!"
- Creates `test_config.json` with JSON data
- Creates `test_binary.bin` with binary data

**Usage**:
```python
def test_file_read(tauri_app_handle, tauri_test_data_dir):
    test_file = tauri_test_data_dir / "test_read.txt"
    content = test_file.read_text()
    assert content == "Hello, Tauri!"
```

## Platform-Specific Behavior

### macOS

**Paths**:
- App data: `~/Library/Application Support/Atom/`
- Cache: `~/Library/Caches/Atom/`
- Config: `~/Library/Preferences/` or `~/Library/Application Support/Atom/`

**Shortcuts**:
- Quit: `Cmd+Q`
- Close Window: `Cmd+W`
- Preferences: `Cmd+,`

**Window Decorations**:
- Red button (close)
- Yellow button (minimize)
- Green button (maximize/fullscreen)

**Menu Bar**:
- Apple menu (About, Preferences, Services)
- App menu (File, Edit, View, Help)

### Linux

**Paths**:
- App data: `~/.config/atom/` or `~/.local/share/atom/`
- Cache: `~/.cache/atom/`
- Config: `~/.config/atom/`

**Shortcuts**:
- Quit: `Ctrl+Q`
- Close Window: `Alt+F4` or `Ctrl+F4`
- Preferences: `Ctrl+,`

**Window Decorations**:
- Follows desktop environment theme (GNOME/KDE)
- Standard close, minimize, maximize buttons

**Menu Bar**:
- File menu (New, Open, Save, Quit)
- Edit menu (Undo, Redo, Cut, Copy, Paste)
- Help menu (Documentation, About)

### Windows

**Paths**:
- App data: `%APPDATA%\Atom\` or `%LOCALAPPDATA%\Atom\`
- Cache: `%LOCALAPPDATA%\Atom\cache\`
- Config: `%APPDATA%\Atom\config\`

**Shortcuts**:
- Quit: `Win+Alt+Q` or `Ctrl+Q`
- Close Window: `Alt+F4`
- Preferences: `Ctrl+,`

**Window Decorations**:
- Close button (X)
- Minimize button (-)
- Maximize/Restore button ([])

**Menu Bar**:
- File menu (New, Open, Save, Exit)
- Edit menu (Undo, Redo, Cut, Copy, Paste)
- Help menu (Documentation, About)

## Building Tauri App

### Debug Build

```bash
cd desktop/src-tauri
cargo build
```

Binary location:
- macOS/Linux: `desktop/src-tauri/target/debug/atom`
- Windows: `desktop/src-tauri/target/debug/atom.exe`

### Release Build

```bash
cd desktop/src-tauri
cargo build --release
```

Binary location:
- macOS/Linux: `desktop/src-tauri/target/release/atom`
- Windows: `desktop/src-tauri/target/release/atom.exe`

### Run Tauri App in Development

```bash
cd desktop
npm run tauri dev
```

This starts Tauri app with hot-reload for frontend development.

## Troubleshooting

### Build Failures

**Issue**: `error: linking with cc failed`

**Solution**: Install platform-specific dependencies (see Prerequisites).

**Issue**: `error: Tauri API not found`

**Solution**: Ensure `tauri.conf.json` exists and is valid.

### Test Failures

**Issue**: `pytest.skip: Tauri app not available`

**Solution**: Set `TAURI_CI=true` environment variable:
```bash
TAURI_CI=true pytest desktop/tests/ -v
```

**Issue**: `pytest.skip: Tauri app binary not found`

**Solution**: Build Tauri app first:
```bash
cd desktop/src-tauri
cargo build
```

Or set `TAURI_APP_PATH`:
```bash
TAURI_APP_PATH=/path/to/atom pytest desktop/tests/ -v
```

**Issue**: `pytest.skip: Test requires macOS platform`

**Solution**: This is expected when running on different platforms. Tests skip gracefully.

### Missing Dependencies

**Issue**: `ModuleNotFoundError: No module named 'pytest'`

**Solution**: Install pytest:
```bash
pip install pytest
```

**Issue**: `ImportError: cannot import name 'pytest'`

**Solution**: Ensure Python 3.11+ is installed:
```bash
python --version  # Should be 3.11+
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Desktop Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [macos-latest, ubuntu-latest, windows-latest]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      
      - name: Install Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install pytest
      
      - name: Install Linux dependencies
        if: matrix.os == 'ubuntu-latest'
        run: sudo apt-get install -y libwebkit2gtk-4.0-dev libgtk-3-dev
      
      - name: Build Tauri app
        run: cd desktop/src-tauri && cargo build
      
      - name: Run desktop tests
        env:
          TAURI_CI: true
        run: pytest desktop/tests/ -v
```

## Test Architecture

### Mocking Strategy

Current tests use mock objects for Tauri APIs. In production, these would be replaced with actual Tauri IPC calls:

```python
# Current (mocked)
tauri_window["is_minimized"] = True

# Production (with Tauri IPC)
await tauri_invoke("window_minimize")
```

### Graceful Degradation

Tests use `pytest.mark.skipif` to skip when:
- Tauri runtime unavailable (`TAURI_CI != true`)
- Platform-specific feature not available
- Native API not implemented

This allows tests to pass in standard CI while being available for platform-specific testing.

## Contributing

When adding new tests:

1. Use appropriate fixtures (`tauri_app`, `tauri_window`, `tauri_app_handle`)
2. Add test ID (e.g., `WINM-09`) for tracking
3. Document platform-specific behavior in docstrings
4. Use `pytest.skip` for unimplemented features
5. Update this README with new test categories

## Resources

- [Tauri Documentation](https://tauri.app/v1/guides/)
- [Tauri API Reference](https://tauri.app/v1/api/js/)
- [pytest Documentation](https://docs.pytest.org/)
- [Rust Documentation](https://www.rust-lang.org/docs)

---

**Total Tests**: 36 tests (8 window management + 13 native features + 15 cross-platform)

**Test Coverage**: Window operations, native features, platform-specific behavior

**Platforms**: Windows, macOS, Linux
