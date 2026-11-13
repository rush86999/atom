"""Build portable "Skill Skill" packages under one anchored workspace root.

A package is a directory ``{workspace_root}/{tenant_id}/skills/{safe_name}/``
holding ``SKILL.md`` plus scripts. Two defects lived here before WA-069:

1. ``workspace_root`` defaulted to ``"./data/workspaces"`` — a *relative* path
   resolved against the launch CWD. Root-launched and ``backend/``-launched
   processes therefore read and wrote different skill stores (the repo's
   documented path-anchoring bug class). Roots now resolve through
   ``core.local_paths.resolve_local_path`` (backend-anchored) and honour the
   existing ``ATOM_WORKSPACE_SKILLS_ROOT`` / ``ATOM_DATA_DIR`` overrides that
   ``core.reviewed_improvement`` already documented.
2. Creation ``mkdir``'d the final package directory and then wrote the
   manifest and scripts into it. An interrupted or failing write left a
   partial package that every retry then refused as "already exists" and that
   tenant-skill consumers (``agent_evolution_loop``, ``evolution_engine``)
   kept reading. Creation now stages the package beside the final path and
   publishes it with one atomic ``os.replace``.

The same containment rules back deletion: tenant ids are single path segments,
the resolved package/trash paths must stay inside the tenant skills directory,
and symlinks are never followed or removed. ``core.skill_package_delete_service``
owns the receipt/replay contract; this module only proves and performs the
filesystem effect.
"""
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.local_paths import resolve_local_path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

logger = logging.getLogger(__name__)

ROOT_ENV = "ATOM_WORKSPACE_SKILLS_ROOT"
DATA_DIR_ENV = "ATOM_DATA_DIR"
DEFAULT_ROOT = "data/workspaces"
SKILLS_DIR_NAME = "skills"
TRASH_DIR_NAME = ".skill-trash"
STAGING_PREFIX = ".staging-"
MANIFEST_NAME = "SKILL.md"
_MAX_COUNTED_FILES = 5000


class SkillPathError(ValueError):
    """A tenant/package path escaped the configured skills root."""


def normalize_skill_name(name: Any) -> str:
    """Canonical package directory name (same rule create has always used)."""
    return "".join(
        c for c in str(name or "") if c.isalnum() or c in ("-", "_")).lower()


def _validate_tenant_segment(tenant_id: Any) -> str:
    """Tenant ids are one path segment; never a traversal or a separator."""
    value = str(tenant_id or "").strip()
    if not value:
        raise SkillPathError("tenant id must be non-empty")
    if value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
        raise SkillPathError("tenant id is not a safe path segment")
    return value


def resolve_workspace_root(explicit: Optional[str] = None) -> Path:
    """Resolve the skills workspace root, anchored to backend unless overridden.

    Precedence (explicit argument → ``ATOM_WORKSPACE_SKILLS_ROOT`` →
    ``ATOM_DATA_DIR``/workspaces → ``backend/data/workspaces``) matches
    ``core.reviewed_improvement._default_builder`` so every caller shares one
    store. The environment is read per resolution, which keeps a module-level
    instance honouring a scratch root configured by a test or a restarted
    acceptance backend.
    """
    if explicit is not None and str(explicit).strip():
        return resolve_local_path(str(explicit))
    configured = os.getenv(ROOT_ENV)
    if configured is not None and configured.strip():
        return resolve_local_path(configured)
    data_dir = os.getenv(DATA_DIR_ENV)
    if data_dir is not None and data_dir.strip():
        return resolve_local_path(data_dir) / "workspaces"
    return resolve_local_path(DEFAULT_ROOT)


def _contained(path: Path, base: Path, label: str) -> Path:
    """Resolve ``path`` and require it to live at/under ``base``."""
    resolved = path.resolve()
    base_resolved = base.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise SkillPathError(
            f"{label} escapes the configured skills root") from exc
    return resolved


def _count_files(directory: Path) -> int:
    count = 0
    try:
        for entry in directory.rglob("*"):
            if entry.is_symlink() or not entry.is_file():
                continue
            count += 1
            if count >= _MAX_COUNTED_FILES:
                return count
    except OSError:
        return count
    return count


class SkillMetadata(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "User"
    capabilities: List[str] = Field(default_factory=list)
    instructions: str = ""


class SkillBuilderService:
    """
    Service to build standard "Skill Skill" packages.
    Creates structured folders with SKILL.md and scripts.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self._explicit_root = (
            str(workspace_root) if str(workspace_root or "").strip() else None)

    @property
    def workspace_root(self) -> Path:
        """Anchored root, re-resolved per access so env overrides apply."""
        return resolve_workspace_root(self._explicit_root)

    @workspace_root.setter
    def workspace_root(self, value: Any) -> None:
        # Kept for callers/tests that assigned the attribute directly.
        self._explicit_root = str(value) if str(value or "").strip() else None

    # -- paths -----------------------------------------------------------
    def tenant_dir(self, tenant_id: str) -> Path:
        """The tenant's own directory, proven to be a direct child of root."""
        tenant = _validate_tenant_segment(tenant_id)
        root = self.workspace_root
        candidate = _contained(root / tenant, root, "tenant path")
        if candidate.parent != root:
            raise SkillPathError("tenant path is not a direct child of root")
        return candidate

    def tenant_skills_dir(self, tenant_id: str, *, create: bool = False) -> Path:
        """Get the skills directory for a tenant.

        ``create=False`` never touches the filesystem, so delete/replay paths
        cannot resurrect an empty tenant tree as a side effect.
        """
        tenant_dir = self.tenant_dir(tenant_id)
        skills_path = tenant_dir / SKILLS_DIR_NAME
        # A symlinked ``skills`` directory is never legitimate — refuse it
        # instead of resolving deletions onto whatever it points at.
        if skills_path.is_symlink():
            raise SkillPathError("skills path is a symlink")
        skills_dir = _contained(skills_path, tenant_dir, "skills path")
        if create:
            tenant_dir.mkdir(parents=True, exist_ok=True)
            skills_dir.mkdir(parents=True, exist_ok=True)
            # Re-prove after creation: a racing symlink swap must not pass.
            if skills_path.is_symlink():
                raise SkillPathError("skills path is a symlink")
            _contained(skills_dir, tenant_dir, "skills path")
        return skills_dir

    def _get_tenant_skills_dir(self, tenant_id: str) -> Path:
        """Back-compat helper used by the evolution consumers (creates)."""
        return self.tenant_skills_dir(tenant_id, create=True)

    def package_dir(self, tenant_id: str, name: str) -> Path:
        """Exact package directory for a name; no creation, no traversal.

        The final component is kept lexical (unresolved). Resolving it would
        turn a symlinked package name into its target, so deleting the link
        would delete a package the caller did not name.
        """
        safe_name = normalize_skill_name(name)
        if not safe_name:
            raise SkillPathError("skill name has no addressable characters")
        skills_dir = self.tenant_skills_dir(tenant_id, create=False)
        package = skills_dir / safe_name
        if package.parent != skills_dir:
            raise SkillPathError("skill package path is not a direct child")
        return package

    def quarantine_dir(self, tenant_id: str, name: str) -> Path:
        """Directory a package is atomically renamed to before it is purged.

        Hidden from the tenant ``skills/`` listing on purpose: an interrupted
        delete must stop being consumable the moment the rename lands. The
        trash root and entry stay lexical for the same reason as
        :meth:`package_dir`.
        """
        safe_name = normalize_skill_name(name)
        if not safe_name:
            raise SkillPathError("skill name has no addressable characters")
        tenant_dir = self.tenant_dir(tenant_id)
        trash_path = tenant_dir / TRASH_DIR_NAME
        if trash_path.is_symlink():
            raise SkillPathError("trash path is a symlink")
        trash_root = _contained(trash_path, tenant_dir, "trash path")
        entry = trash_root / safe_name
        if entry.parent != trash_root:
            raise SkillPathError("trash entry path is not a direct child")
        return entry

    # -- reads -----------------------------------------------------------
    def list_skill_packages(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List the tenant's published packages (never staging/trash)."""
        skills_dir = self.tenant_skills_dir(tenant_id, create=False)
        try:
            entries = sorted(skills_dir.iterdir(), key=lambda p: p.name)
        except FileNotFoundError:
            return []
        packages: List[Dict[str, Any]] = []
        for entry in entries:
            if entry.is_symlink() or not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue
            scripts = sorted(
                child.name for child in entry.iterdir()
                if child.is_file() and not child.is_symlink())
            packages.append({
                "name": entry.name,
                "has_manifest": (entry / MANIFEST_NAME).is_file(),
                "files": scripts,
                "modified_at": stat.st_mtime,
            })
        return packages

    def skill_package_state(self, tenant_id: str, name: str) -> Dict[str, Any]:
        """Read-only state used by deletion/replay: present/absent/unsafe."""
        package = self.package_dir(tenant_id, name)
        trash = self.quarantine_dir(tenant_id, name)
        if package.is_symlink():
            package_state = "unsafe"
        elif package.is_dir():
            package_state = "present"
        elif package.exists():
            package_state = "unsafe"
        else:
            package_state = "absent"
        if trash.is_symlink():
            trash_state = "unsafe"
        elif trash.is_dir():
            trash_state = "present"
        elif trash.exists():
            trash_state = "unsafe"
        else:
            trash_state = "absent"
        return {
            "package": package,
            "trash": trash,
            "package_state": package_state,
            "trash_state": trash_state,
            "file_count": (
                _count_files(package) if package_state == "present" else 0),
        }

    # -- create ----------------------------------------------------------
    def create_skill_package(
        self,
        tenant_id: str,
        metadata: SkillMetadata,
        scripts: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Create a new skill package.

        Args:
            tenant_id: Tenant ID
            metadata: Skill metadata (name, description, etc.)
            scripts: Dictionary of filename -> content (e.g., {'script.py': 'print("hi")'})

        Returns:
            Dict with success status and path
        """
        staging: Optional[Path] = None
        try:
            # 1. Validate Safe Name
            safe_name = normalize_skill_name(metadata.name)
            if not safe_name:
                raise ValueError("Invalid skill name")

            skills_dir = self.tenant_skills_dir(tenant_id, create=True)
            skill_dir = self.package_dir(tenant_id, safe_name)

            if skill_dir.exists():
                raise ValueError(f"Skill '{safe_name}' already exists")

            # 2. Stage beside the final path so a failure/interrupt never
            #    publishes a half-written package.
            staging = skills_dir / f"{STAGING_PREFIX}{uuid.uuid4().hex}"
            staging.mkdir(parents=False, exist_ok=False)
            _contained(staging, skills_dir, "staging path")

            frontmatter = {
                "name": metadata.name,
                "description": metadata.description,
                "version": metadata.version,
                "author": metadata.author,
                "capabilities": metadata.capabilities
            }

            if YAML_AVAILABLE:
                skill_md_content = "---\n" + yaml.dump(frontmatter) + "---\n\n"
            else:
                skill_md_content = "# Skill Metadata (YAML fallback)\n"
                for k, v in frontmatter.items():
                    skill_md_content += f"- {k}: {v}\n"
                skill_md_content += "\n"
            skill_md_content += f"# {metadata.name}\n\n"
            skill_md_content += f"{metadata.description}\n\n"
            skill_md_content += "## Instructions\n"
            skill_md_content += f"{metadata.instructions}\n\n"
            skill_md_content += "## Scripts\n"
            for script_name in scripts.keys():
                skill_md_content += f"- `{script_name}`\n"

            (staging / MANIFEST_NAME).write_text(
                skill_md_content, encoding="utf-8")

            # 3. Save Scripts
            saved_scripts = []
            for filename, content in scripts.items():
                if not self._is_safe_script_name(filename):
                    continue  # Skip unsafe filenames

                script_path = staging / filename
                script_path.write_text(content, encoding="utf-8")
                saved_scripts.append(filename)

            # 4. Publish atomically. A concurrent creator that won the race
            #    leaves our staging directory to be discarded below.
            if skill_dir.exists():
                raise ValueError(f"Skill '{safe_name}' already exists")
            os.replace(staging, skill_dir)
            staging = None

            return {
                "success": True,
                "message": f"Skill '{metadata.name}' created successfully",
                "name": safe_name,
                "path": str(skill_dir),
                "scripts": saved_scripts
            }

        except Exception as e:
            logger.error(f"Failed to create skill package: {e}")
            return {
                "success": False,
                "message": str(e)
            }
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _is_safe_script_name(filename: Any) -> bool:
        """One plain filename; never a traversal, separator or the manifest."""
        name = str(filename or "")
        if not name or name in (".", ".."):
            return False
        if name.lower() == MANIFEST_NAME.lower():
            return False
        if ".." in name or "/" in name or "\\" in name or "\x00" in name:
            return False
        return Path(name).name == name


skill_builder_service = SkillBuilderService()
