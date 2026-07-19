from __future__ import annotations
import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class SandboxTransaction:
    """Manages transactional file state for Level 5 DMM (Synthetically Closed) sandboxes.
    
    Provides copy-on-write snapshotting of a target directory. If an action fails
    or is aborted, changes can be rolled back to restore the original state.
    """
    
    def __init__(self, target_dir: str | Path):
        self.target_dir = Path(target_dir).resolve()
        self.snapshot_dir: Optional[Path] = None
        self._active = False

    def __enter__(self) -> SandboxTransaction:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            logger.warning(f"Aborting sandbox transaction on {self.target_dir} due to exception: {exc_val}")
            self.rollback()
        else:
            self.commit()

    def start(self) -> None:
        """Create a snapshot copy of the target directory."""
        if not self.target_dir.exists():
            self.target_dir.mkdir(parents=True, exist_ok=True)
            
        temp_parent = self.target_dir.parent / ".sandbox_snapshots"
        temp_parent.mkdir(parents=True, exist_ok=True)
        
        self.snapshot_dir = Path(tempfile.mkdtemp(dir=temp_parent))
        
        for item in self.target_dir.iterdir():
            if item.name == ".sandbox_snapshots":
                continue
            dest = self.snapshot_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest, follow_symlinks=False)
                
        self._active = True
        logger.info(f"Started sandbox transaction on {self.target_dir}. Snapshot saved to {self.snapshot_dir}")

    def commit(self) -> None:
        """Discard the snapshot and keep the modifications."""
        if not self._active:
            return
        
        self._cleanup_snapshot()
        self._active = False
        logger.info(f"Committed sandbox transaction on {self.target_dir}")

    def rollback(self) -> None:
        """Restore the target directory to the snapshot state."""
        if not self._active or not self.snapshot_dir or not self.snapshot_dir.exists():
            return
            
        for item in self.target_dir.iterdir():
            if item.name == ".sandbox_snapshots":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
                
        for item in self.snapshot_dir.iterdir():
            dest = self.target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest, follow_symlinks=False)
                
        self._cleanup_snapshot()
        self._active = False
        logger.info(f"Rolled back sandbox transaction on {self.target_dir}")

    def _cleanup_snapshot(self) -> None:
        """Remove the temporary snapshot directory."""
        if self.snapshot_dir and self.snapshot_dir.exists():
            shutil.rmtree(self.snapshot_dir)
            self.snapshot_dir = None
