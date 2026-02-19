"""
Skill Dynamic Loader - Runtime skill loading with hot-reload.

Uses importlib for dynamic module loading and watchdog for file monitoring.
Enables skill updates without service restart.

Key features:
- Load skills from file paths at runtime
- Hot-reload skills within 1s of file change
- Clear sys.modules cache to prevent stale code
- Track loaded skills with version hashes
- Optional file monitoring with watchdog Observer

Reference: Phase 60 RESEARCH.md Pattern 1 "Dynamic Skill Loading with Hot-Reload"
"""

import hashlib
import importlib
import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SkillDynamicLoader:
    """
    Dynamic skill loading with hot-reload capabilities.

    Example:
        loader = SkillDynamicLoader(skills_dir="/path/to/skills")
        module = loader.load_skill("my_skill", "/path/to/my_skill.py")
        result = module.run(inputs={"data": 123})

        # Hot-reload when file changes
        reloaded = loader.reload_skill("my_skill")
    """

    def __init__(self, skills_dir: Optional[str] = None, enable_monitoring: bool = False):
        """
        Initialize dynamic loader.

        Args:
            skills_dir: Directory containing skill files (for monitoring)
            enable_monitoring: Enable file system monitoring for hot-reload
        """
        self.skills_dir = Path(skills_dir) if skills_dir else None
        self.loaded_skills: Dict[str, Dict[str, Any]] = {}
        self.skill_versions: Dict[str, str] = {}
        self._observer = None

        if enable_monitoring and self.skills_dir:
            self._start_file_monitor()

    def load_skill(
        self,
        skill_name: str,
        skill_path: str,
        force_reload: bool = False
    ) -> Optional[Any]:
        """
        Load skill module dynamically from file path.

        Args:
            skill_name: Unique identifier for the skill
            skill_path: Absolute path to skill Python file
            force_reload: Force reload even if already loaded

        Returns:
            Loaded module object or None if loading fails
        """
        # Check if already loaded
        if skill_name in self.loaded_skills and not force_reload:
            logger.debug(f"Skill {skill_name} already loaded, returning cached module")
            return self.loaded_skills[skill_name]["module"]

        # Verify file exists
        path = Path(skill_path)
        if not path.exists():
            logger.error(f"Skill file not found: {skill_path}")
            return None

        # Calculate file hash for version tracking
        file_hash = self._calculate_file_hash(path)

        try:
            # Load module using importlib
            spec = importlib.util.spec_from_file_location(skill_name, skill_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load spec for {skill_name} from {skill_path}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[skill_name] = module
            spec.loader.exec_module(module)

            # Store in loaded skills
            self.loaded_skills[skill_name] = {
                "module": module,
                "path": skill_path,
                "loaded_at": datetime.now(timezone.utc),
                "hash": file_hash
            }
            self.skill_versions[skill_name] = file_hash

            logger.info(f"Loaded skill {skill_name} from {skill_path} (hash: {file_hash[:8]})")
            return module

        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}: {e}")
            # Clean up on error
            if skill_name in sys.modules:
                del sys.modules[skill_name]
            return None

    def reload_skill(self, skill_name: str) -> Optional[Any]:
        """
        Hot-reload skill module without service restart.

        CRITICAL: Clear sys.modules before reload to prevent stale code.
        Reference: Phase 60 RESEARCH.md Pitfall 1 "Stale Module Cache"

        Args:
            skill_name: Name of skill to reload

        Returns:
            Reloaded module or None if reload fails
        """
        if skill_name not in self.loaded_skills:
            logger.warning(f"Skill {skill_name} not loaded, cannot reload")
            return None

        skill_path = self.loaded_skills[skill_name]["path"]
        current_hash = self._calculate_file_hash(Path(skill_path))

        # Check if file actually changed
        if current_hash == self.skill_versions.get(skill_name):
            logger.debug(f"Skill {skill_name} unchanged, skipping reload")
            return self.loaded_skills[skill_name]["module"]

        logger.info(f"Reloading skill {skill_name} (hash: {current_hash[:8]})")

        # Clear module cache (CRITICAL: prevents stale imports)
        if skill_name in sys.modules:
            del sys.modules[skill_name]

        # Reload from file path
        return self.load_skill(skill_name, skill_path, force_reload=True)

    def get_skill(self, skill_name: str) -> Optional[Any]:
        """
        Get currently loaded skill module.

        Args:
            skill_name: Name of skill to retrieve

        Returns:
            Module object or None if not loaded
        """
        return self.loaded_skills.get(skill_name, {}).get("module")

    def unload_skill(self, skill_name: str) -> bool:
        """
        Unload skill and clear from cache.

        Args:
            skill_name: Name of skill to unload

        Returns:
            True if unloaded, False if not found
        """
        if skill_name not in self.loaded_skills:
            return False

        # Clear module cache
        if skill_name in sys.modules:
            del sys.modules[skill_name]

        # Remove from tracking
        del self.loaded_skills[skill_name]
        if skill_name in self.skill_versions:
            del self.skill_versions[skill_name]

        logger.info(f"Unloaded skill {skill_name}")
        return True

    def list_loaded_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        List all currently loaded skills.

        Returns:
            Dict mapping skill names to metadata
        """
        return {
            name: {
                "path": info["path"],
                "loaded_at": info["loaded_at"].isoformat(),
                "hash": info["hash"][:8]
            }
            for name, info in self.loaded_skills.items()
        }

    def check_for_updates(self) -> Dict[str, bool]:
        """
        Check if loaded skills have been modified on disk.

        Returns:
            Dict mapping skill names to update status
        """
        updates = {}

        for skill_name, info in self.loaded_skills.items():
            current_hash = self._calculate_file_hash(Path(info["path"]))
            updates[skill_name] = (current_hash != self.skill_versions.get(skill_name))

        return updates

    def _calculate_file_hash(self, path: Path) -> str:
        """Calculate SHA256 hash of file for version tracking."""
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {path}: {e}")
            return ""

    def _start_file_monitor(self):
        """Start watchdog observer for hot-reload (optional)."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class SkillReloadHandler(FileSystemEventHandler):
                def __init__(self, loader):
                    self.loader = loader

                def on_modified(self, event):
                    if event.src_path.endswith('.py'):
                        path = Path(event.src_path)
                        # Find skill name by path
                        for name, info in self.loader.loaded_skills.items():
                            if info["path"] == event.src_path:
                                logger.info(f"Detected change in {name}, reloading...")
                                self.loader.reload_skill(name)
                                break

            handler = SkillReloadHandler(self)
            self._observer = Observer()
            self._observer.schedule(handler, path=str(self.skills_dir), recursive=True)
            self._observer.start()
            logger.info(f"File monitoring started for {self.skills_dir}")

        except ImportError:
            logger.warning("watchdog not installed, file monitoring disabled")
        except Exception as e:
            logger.error(f"Failed to start file monitoring: {e}")

    def stop_monitoring(self):
        """Stop file monitoring if active."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("File monitoring stopped")


# Global loader instance
_global_loader: Optional[SkillDynamicLoader] = None


def get_global_loader(skills_dir: Optional[str] = None) -> SkillDynamicLoader:
    """Get or create global dynamic loader instance."""
    global _global_loader
    if _global_loader is None:
        _global_loader = SkillDynamicLoader(skills_dir=skills_dir)
    return _global_loader
