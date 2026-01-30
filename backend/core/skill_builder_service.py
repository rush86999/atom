import os
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SkillMetadata(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "User"
    capabilities: List[str] = []
    instructions: str = ""

class SkillBuilderService:
    """
    Service to build standard "Skill Skill" packages.
    Creates structured folders with SKILL.md and scripts.
    """
    
    def __init__(self, workspace_root: str = "./data/workspaces"):
        self.workspace_root = Path(workspace_root).resolve()
    
    def _get_tenant_skills_dir(self, tenant_id: str) -> Path:
        """Get skills directory for a tenant."""
        skills_dir = self.workspace_root / tenant_id / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        return skills_dir

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
        try:
            # 1. Validate Safe Name
            safe_name = "".join([c for c in metadata.name if c.isalnum() or c in ('-', '_')]).lower()
            if not safe_name:
                raise ValueError("Invalid skill name")
                
            skill_dir = self._get_tenant_skills_dir(tenant_id) / safe_name
            
            if skill_dir.exists():
                raise ValueError(f"Skill '{safe_name}' already exists")
                
            skill_dir.mkdir(parents=True, exist_ok=True)
            
            # 2. Generate SKILL.md
            frontmatter = {
                "name": metadata.name,
                "description": metadata.description,
                "version": metadata.version,
                "author": metadata.author,
                "capabilities": metadata.capabilities
            }
            
            skill_md_content = "---\n" + yaml.dump(frontmatter) + "---\n\n"
            skill_md_content += f"# {metadata.name}\n\n"
            skill_md_content += f"{metadata.description}\n\n"
            skill_md_content += "## Instructions\n"
            skill_md_content += f"{metadata.instructions}\n\n"
            skill_md_content += "## Scripts\n"
            for script_name in scripts.keys():
                skill_md_content += f"- `{script_name}`\n"
            
            (skill_dir / "SKILL.md").write_text(skill_md_content)
            
            # 3. Save Scripts
            saved_scripts = []
            for filename, content in scripts.items():
                # Basic validation for filename
                if ".." in filename or "/" in filename:
                    continue # Skip unsafe filenames
                    
                script_path = skill_dir / filename
                script_path.write_text(content)
                saved_scripts.append(filename)
                
            return {
                "success": True,
                "message": f"Skill '{metadata.name}' created successfully",
                "path": str(skill_dir),
                "scripts": saved_scripts
            }
            
        except Exception as e:
            logger.error(f"Failed to create skill package: {e}")
            return {
                "success": False,
                "message": str(e)
            }

skill_builder_service = SkillBuilderService()
