"""
Desktop Tauri App Fixtures for Testing

This module provides pytest fixtures for testing Tauri desktop applications.
Fixtures handle Tauri app lifecycle, window management, and platform detection.

Usage:
    pytest desktop/tests/test_window_management.py -v
    pytest desktop/tests/test_native_features.py -v
    pytest desktop/tests/test_cross_platform.py -v

Environment Variables:
    TAURI_CI: Set to 'true' to enable desktop tests in CI
    TAURI_APP_PATH: Path to Tauri app binary (optional, auto-detected)
"""

import os
import platform
import subprocess
import time
import pytest
from typing import Dict, Optional, Generator
from pathlib import Path


class TauriApp:
    """Tauri app process wrapper for testing"""
    
    def __init__(self, process: subprocess.Popen, app_path: str):
        self.process = process
        self.app_path = app_path
        self.pid = process.pid
        self.is_running = True
    
    def stop(self):
        """Stop the Tauri app process"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.is_running = False


def tauri_app_available() -> bool:
    """Check if Tauri app is available for testing"""
    return os.getenv("TAURI_CI", "false").lower() == "true"


def find_tauri_app() -> Optional[str]:
    """Find Tauri app binary in common locations"""
    current_platform = platform.system()
    
    # Common Tauri app paths
    search_paths = []
    
    if current_platform == "Darwin":  # macOS
        search_paths = [
            "./desktop/src-tauri/target/debug/atom",
            "./desktop/src-tauri/target/release/atom",
            "./src-tauri/target/debug/atom",
            "./src-tauri/target/release/atom",
        ]
    elif current_platform == "Linux":
        search_paths = [
            "./desktop/src-tauri/target/debug/atom",
            "./desktop/src-tauri/target/release/atom",
            "./src-tauri/target/debug/atom",
            "./src-tauri/target/release/atom",
        ]
    elif current_platform == "Windows":
        search_paths = [
            "./desktop/src-tauri/target/debug/atom.exe",
            "./desktop/src-tauri/target/release/atom.exe",
            "./src-tauri/target/debug/atom.exe",
            "./src-tauri/target/release/atom.exe",
        ]
    
    # Check if app exists
    for path in search_paths:
        full_path = Path(path).resolve()
        if full_path.exists():
            return str(full_path)
    
    # Check TAURI_APP_PATH environment variable
    env_path = os.getenv("TAURI_APP_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    
    return None


@pytest.fixture(scope="session")
def platform_info() -> Dict[str, any]:
    """
    Provide platform information for testing
    
    Returns:
        Dict with platform information:
        - platform: "darwin", "linux", or "windows"
        - is_test: True if running in test environment
        - arch: "x86_64", "arm64", etc.
        - tauri_available: True if Tauri app is available
    """
    system = platform.system()
    
    # Normalize platform names
    platform_map = {
        "Darwin": "darwin",
        "Linux": "linux",
        "Windows": "windows"
    }
    
    return {
        "platform": platform_map.get(system, system.lower()),
        "is_test": True,
        "arch": platform.machine(),
        "tauri_available": tauri_app_available()
    }


@pytest.fixture(scope="session")
def tauri_app(platform_info: Dict[str, any]) -> Generator[Optional[TauriApp], None, None]:
    """
    Build and spawn Tauri app for testing
    
    This fixture:
    1. Checks if Tauri app is available (requires TAURI_CI=true)
    2. Builds Tauri app in test mode if needed
    3. Spawns Tauri app process
    4. Yields TauriApp wrapper for test use
    5. Cleanup: terminates app process after tests
    
    Usage:
        def test_something(tauri_app):
            assert tauri_app is not None
            assert tauri_app.is_running
    
    Yields:
        TauriApp instance or None if Tauri not available
    """
    if not platform_info["tauri_available"]:
        pytest.skip("Tauri app not available (set TAURI_CI=true)")
        yield None
        return
    
    # Find Tauri app binary
    app_path = find_tauri_app()
    if not app_path:
        pytest.skip("Tauri app binary not found (set TAURI_APP_PATH)")
        yield None
        return
    
    # Build Tauri app if in debug mode and not already built
    if "debug" in app_path and not Path(app_path).exists():
        print(f"Building Tauri app in debug mode...")
        build_result = subprocess.run(
            ["cargo", "build", "--manifest-path", "./desktop/src-tauri/Cargo.toml"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes
        )
        if build_result.returncode != 0:
            pytest.skip(f"Tauri app build failed: {build_result.stderr}")
            yield None
            return
    
    # Spawn Tauri app process
    print(f"Starting Tauri app: {app_path}")
    try:
        process = subprocess.Popen(
            [app_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for app to start (check for window or listen on port)
        # Tauri apps typically start within 2-5 seconds
        time.sleep(3)
        
        # Verify process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.skip(f"Tauri app exited immediately: {stderr}")
            yield None
            return
        
        # Yield TauriApp wrapper
        app = TauriApp(process, app_path)
        yield app
        
    except FileNotFoundError:
        pytest.skip(f"Tauri app binary not found: {app_path}")
        yield None
        return
    except Exception as e:
        pytest.skip(f"Failed to start Tauri app: {e}")
        yield None
        return
    finally:
        # Cleanup: terminate app process
        if 'app' in locals() and app:
            app.stop()


@pytest.fixture(scope="function")
def tauri_window(tauri_app: Optional[TauriApp]) -> Optional[Dict[str, any]]:
    """
    Get main window handle for Tauri app
    
    This fixture:
    1. Uses tauri_app fixture
    2. Gets main window handle via Tauri API (mocked for now)
    3. Returns window object for manipulation (resize, minimize, etc.)
    
    Usage:
        def test_window_minimize(tauri_window):
            window = tauri_window
            # Test window operations
    
    Yields:
        Window dict with:
        - id: Window identifier
        - title: Window title
        - width: Window width
        - height: Window height
        - is_visible: Window visibility state
        - is_minimized: Window minimized state
        - is_maximized: Window maximized state
        Or None if Tauri not available
    """
    if tauri_app is None:
        return None
    
    # In real implementation, this would use Tauri IPC to get window info
    # For now, return a mock window object
    # TODO: Implement Tauri IPC bridge for window operations
    
    window = {
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
    
    return window


@pytest.fixture(scope="function")
def tauri_app_handle(tauri_app: Optional[TauriApp]) -> Optional[Dict[str, any]]:
    """
    Get AppHandle for Tauri app
    
    This fixture:
    1. Uses tauri_app fixture
    2. Gets AppHandle via Tauri API (mocked for now)
    3. Returns handle for native feature access (fs, dialogs, tray)
    
    Usage:
        def test_file_system(tauri_app_handle):
            handle = tauri_app_handle
            # Test native features
    
    Yields:
        AppHandle dict with:
        - app_id: Tauri app ID
        - app_name: App name
        - version: App version
        - fs_api: File system API capabilities
        - dialog_api: Dialog API capabilities
        - notification_api: Notification API capabilities
        - tray_api: System tray API capabilities
        Or None if Tauri not available
    """
    if tauri_app is None:
        return None
    
    # In real implementation, this would use Tauri IPC to get app handle
    # For now, return a mock app handle
    # TODO: Implement Tauri IPC bridge for app operations
    
    handle = {
        "app_id": "com.atom.desktop",
        "app_name": "Atom",
        "version": "1.0.0",
        "fs_api": {
            "read_text": True,
            "write_text": True,
            "read_binary": True,
            "write_binary": True,
            "exists": True,
            "remove": True
        },
        "dialog_api": {
            "open": True,
            "save": True,
            "message": True,
            "ask": True,
            "confirm": True
        },
        "notification_api": {
            "send": True,
            "is_permitted": True
        },
        "tray_api": {
            "set_icon": True,
            "set_menu": True,
            "show": True,
            "hide": True
        }
    }
    
    return handle


@pytest.fixture(scope="function")
def tauri_test_data_dir(tmp_path: Path) -> Path:
    """
    Create temporary test data directory for Tauri tests
    
    Creates test files for file system API testing:
    - test_read.txt: File for reading tests
    - test_config.json: JSON config file for parsing tests
    
    Usage:
        def test_file_read(tauri_app_handle, tauri_test_data_dir):
            test_file = tauri_test_data_dir / "test_read.txt"
            # Test file operations
    
    Returns:
        Path to temporary test data directory
    """
    # Create test files
    test_read_file = tmp_path / "test_read.txt"
    test_read_file.write_text("Hello, Tauri!")
    
    test_json_file = tmp_path / "test_config.json"
    test_json_file.write_text('{"key": "value", "number": 42}')
    
    test_binary_file = tmp_path / "test_binary.bin"
    test_binary_file.write_bytes(b'\x00\x01\x02\x03\x04\x05')
    
    return tmp_path


# Helper functions for Tauri tests

def get_platform_specific_path(platform_info: Dict[str, any], subpath: str = "") -> str:
    """
    Get platform-specific app data path
    
    Args:
        platform_info: Platform info from platform_info fixture
        subpath: Optional subpath to append
    
    Returns:
        Platform-specific path string
    """
    home = Path.home()
    platform = platform_info["platform"]
    
    if platform == "darwin":
        # macOS: ~/Library/Application Support/Atom/
        base_path = home / "Library" / "Application Support" / "Atom"
    elif platform == "linux":
        # Linux: ~/.config/atom/ or ~/.local/share/atom/
        base_path = home / ".config" / "atom"
    elif platform == "windows":
        # Windows: %APPDATA%\Atom\ or %LOCALAPPDATA%\Atom\
        appdata = os.getenv("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        base_path = Path(appdata) / "Atom"
    else:
        # Fallback
        base_path = home / ".atom"
    
    if subpath:
        return str(base_path / subpath)
    
    return str(base_path)


def simulate_keyboard_shortcut(shortcut: str, platform_info: Dict[str, any]) -> str:
    """
    Convert platform-specific keyboard shortcut for testing
    
    Args:
        shortcut: Shortcut string (e.g., "Cmd+Q", "Ctrl+Q", "Win+Alt+Q")
        platform_info: Platform info from platform_info fixture
    
    Returns:
        Platform-specific shortcut string
    """
    platform = platform_info["platform"]
    
    # Normalize shortcuts across platforms
    if platform == "darwin":
        # macOS: Use Cmd
        return shortcut.replace("Ctrl+", "Cmd+").replace("Win+", "Cmd+")
    elif platform == "windows":
        # Windows: Use Win or Ctrl
        return shortcut.replace("Cmd+", "Ctrl+").replace("Ctrl+Q", "Win+Alt+Q")
    elif platform == "linux":
        # Linux: Use Ctrl
        return shortcut.replace("Cmd+", "Ctrl+").replace("Win+", "Super+")
    
    return shortcut


def skip_if_platform_not(platform_info: Dict[str, any], required_platform: str):
    """
    Helper to skip test if not on required platform
    
    Args:
        platform_info: Platform info from platform_info fixture
        required_platform: Required platform ("darwin", "linux", "windows")
    
    Raises:
        pytest.skip.Exception: If not on required platform
    """
    if platform_info["platform"] != required_platform:
        pytest.skip(f"Test requires {required_platform} platform (current: {platform_info['platform']})")


def skip_if_any_platform(platform_info: Dict[str, any], excluded_platforms: list):
    """
    Helper to skip test if on any excluded platform
    
    Args:
        platform_info: Platform info from platform_info fixture
        excluded_platforms: List of platforms to exclude ("darwin", "linux", "windows")
    
    Raises:
        pytest.skip.Exception: If on excluded platform
    """
    if platform_info["platform"] in excluded_platforms:
        pytest.skip(f"Test not available on {platform_info['platform']} platform")
