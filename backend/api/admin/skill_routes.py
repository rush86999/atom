from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, List, Any
from core.models import User
from core.admin_endpoints import get_super_admin
from core.skill_builder_service import skill_builder_service, SkillMetadata
from atom_security.analyzers.static import StaticAnalyzer

router = APIRouter(tags=["Admin Skills"])

class CreateSkillRequest(BaseModel):
    name: str
    description: str
    instructions: str
    capabilities: List[str] = []
    scripts: Dict[str, str]  # filename -> content

@router.post("/api/admin/skills")
async def create_new_skill(
    request: CreateSkillRequest,
    admin: User = Depends(get_super_admin)
):
    """
    Create a new standardized skill package (Skill Skill).
    """
    try:
        # Use the admin's tenant ID
        # In a real SaaS, this might be the admin's organization or a specific target tenant
        # For now, we assume the admin creates skills for their own tenant context
        tenant_id = str(admin.tenant_id) if admin.tenant_id else "default"
        
        # Proactive Security Audit
        try:
            from atom_security.analyzers.static import StaticAnalyzer
            from atom_security.analyzers.llm import LLMAnalyzer
            
            # Static Scan
            static_analyzer = StaticAnalyzer()
            combined_content = f"{request.instructions}\n" + "\n".join(request.scripts.values())
            static_findings = static_analyzer.scan_content(combined_content)
            
            # Optional LLM Scan (BYOK or Local)
            llm_findings = []
            if os.getenv("ATOM_SECURITY_ENABLE_LLM_SCAN", "false").lower() == "true":
                try:
                    llm_analyzer = LLMAnalyzer(mode=os.getenv("ATOM_SECURITY_LLM_MODE", "local"))
                    llm_findings = await llm_analyzer.analyze(request.name, combined_content)
                except Exception as e:
                    print(f"LLM Scan failed: {e}")

            all_findings = static_findings + llm_findings
            critical_findings = [f.dict() for f in all_findings if f.severity.value in ["HIGH", "CRITICAL"]]
            
            if critical_findings:
                raise HTTPException(
                    status_code=403, 
                    detail={
                        "message": "Skill rejected due to security policy violations.",
                        "findings": critical_findings
                    }
                )
        except HTTPException:
            raise
        except Exception as scan_error:
            # Log but don't block if security module fails
            print(f"Security scan error: {scan_error}")

        metadata = SkillMetadata(
            name=request.name,
            description=request.description,
            instructions=request.instructions,
            capabilities=request.capabilities,
            author=admin.email or "Admin"
        )
        
        result = skill_builder_service.create_skill_package(
            tenant_id=tenant_id,
            metadata=metadata,
            scripts=request.scripts
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
