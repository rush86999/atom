from __future__ import annotations
import time
import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class SandboxTransaction:
    """Manages transactional file state for Level 5 DMM (Synthetically Closed) sandboxes.
    
    Provides copy-on-write snapshotting of a target directory and enforces resource limits
    (execution timeouts, file modification caps). If an action fails or breaches caps,
    changes are rolled back to restore the original pre-execution state.
    """
    
    def __init__(
        self,
        target_dir: str | Path,
        timeout_seconds: Optional[float] = None,
        max_bytes: Optional[int] = None,
    ):
        self.target_dir = Path(target_dir).resolve()
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.snapshot_dir: Optional[Path] = None
        self.start_time: Optional[float] = None
        self._active = False

    def __enter__(self) -> SandboxTransaction:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            logger.warning(f"Aborting sandbox transaction on {self.target_dir} due to exception: {exc_val}")
            self.rollback()
        else:
            try:
                self.check_resource_limits()
                self.commit()
            except Exception as e:
                logger.warning(f"Aborting sandbox transaction on {self.target_dir} due to resource cap breach: {e}")
                self.rollback()
                raise

    def start(self) -> None:
        """Create a snapshot copy of the target directory."""
        if not self.target_dir.exists():
            self.target_dir.mkdir(parents=True, exist_ok=True)
            
        temp_parent = self.target_dir.parent / ".sandbox_snapshots"
        temp_parent.mkdir(parents=True, exist_ok=True)
        
        self.snapshot_dir = Path(tempfile.mkdtemp(dir=temp_parent))
        self.start_time = time.time()
        
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

    def check_resource_limits(self) -> None:
        """Validate that execution time and workspace disk size do not breach specified caps."""
        if not self._active:
            return
            
        if self.timeout_seconds is not None and self.start_time is not None:
            elapsed = time.time() - self.start_time
            if elapsed > self.timeout_seconds:
                raise TimeoutError(f"Sandbox transaction timed out: elapsed {elapsed:.2f}s > limit {self.timeout_seconds:.2f}s")
                
        if self.max_bytes is not None and self.target_dir.exists():
            total_size = sum(f.stat().st_size for f in self.target_dir.rglob('*') if f.is_file() and ".sandbox_snapshots" not in f.parts)
            if total_size > self.max_bytes:
                raise MemoryError(f"Sandbox transaction exceeded disk size cap: total {total_size} bytes > limit {self.max_bytes} bytes")

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
