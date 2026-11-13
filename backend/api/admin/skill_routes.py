import logging
import os
from typing import Any, Dict, List, Optional

from atom_security.analyzers.static import StaticAnalyzer
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.admin_endpoints import get_platform_admin  # was get_super_admin — see 2026-09-08b role-journey pass
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.personal_scope import resolve_tenant_id
from core.skill_builder_service import (
    SkillBuilderService,
    SkillMetadata,
    SkillPathError,
    normalize_skill_name,
    skill_builder_service,
)
from core.skill_package_delete_service import delete_skill_package_verified

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/admin/skills", tags=["Admin Skills"])

class CreateSkillRequest(BaseModel):
    name: str
    description: str
    instructions: str
    capabilities: List[str] = []
    scripts: Dict[str, str]  # filename -> content


def _tenant_id(admin: User) -> str:
    """Tenant scope of the acting admin, via the shared resolver.

    The stored ``users.tenant_id`` is authoritative; ``resolve_tenant_id``
    keeps the Personal-Edition fallback the create route already relied on.
    """
    return str(resolve_tenant_id(admin))


@router.post("", include_in_schema=False)
@router.post("/")
async def create_new_skill(
    request: CreateSkillRequest,
    admin: User = Depends(get_platform_admin)
):
    """
    Create a new standardized skill package (Skill Skill).
    """
    try:
        # Use the admin's tenant ID
        # In a real SaaS, this might be the admin's organization or a specific target tenant
        # For now, we assume the admin creates skills for their own tenant context
        tenant_id = _tenant_id(admin)

        # Proactive Security Audit
        try:
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
                    logger.error(f"LLM Scan failed: {e}")

            all_findings = static_findings + llm_findings
            critical_findings = [f.dict() for f in all_findings if f.severity.value in ["HIGH", "CRITICAL"]]

            if critical_findings:
                raise router.permission_denied_error(
                    action="create_skill",
                    resource="Skill",
                    details={
                        "message": "Skill rejected due to security policy violations.",
                        "findings": critical_findings
                    }
                )
        except HTTPException:
            raise
        except Exception as scan_error:
            # Log but don't block if security module fails
            logger.warning(f"Security scan error: {scan_error}")

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
            raise router.validation_error("skill_creation", result["message"])

        return router.success_response(
            data=result,
            message="Skill created successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise router.internal_error("Internal error")


@router.get("/")
async def list_skill_packages(
    admin: User = Depends(get_platform_admin),
):
    """List the acting tenant's published packages.

    Read-only and tenant-scoped. Staging and quarantine directories are hidden:
    they are not consumable packages.
    """
    builder = SkillBuilderService()
    try:
        packages = builder.list_skill_packages(_tenant_id(admin))
    except SkillPathError as exc:
        raise router.validation_error("skills_root", str(exc))
    except Exception as exc:  # noqa: BLE001 — unreadable is not "none"
        logger.error("Skill package listing failed: %s", type(exc).__name__)
        raise router.internal_error("Skill packages could not be listed")
    return router.success_list_response(
        packages, total=len(packages), message="Skill packages")


@router.delete("/{skill_id}")
async def delete_skill_package(
    skill_id: str,
    operation_id: Optional[str] = None,
    admin: User = Depends(get_platform_admin),
    db: Session = Depends(get_db),
):
    """Delete one tenant skill package with a durable deletion receipt.

    The tenant scope is always the acting admin's stored tenant; ``skill_id``
    selects a package *inside* that tenant and is resolved with exact path
    containment. The response contract mirrors verified document deletion:
    ``verified``/``already_applied``/``no_change`` succeed, while
    ``committed_unverified``/``effect_unknown`` are 503 with
    ``replay=do_not_repeat``.
    """
    result = delete_skill_package_verified(
        db=db, actor=admin, name=skill_id, operation_id=operation_id)

    status_value = str(result.get("status") or "")
    if status_value == "refused":
        if int(result.get("http_status") or 0) == 404:
            raise router.not_found_error(
                "Skill package", normalize_skill_name(skill_id))
        raise HTTPException(
            status_code=int(result.get("http_status") or 422),
            detail={
                "error": {
                    "code": result.get("error_code") or "VALIDATION_ERROR",
                    "message": result.get("error") or "Request refused",
                },
                "field": result.get("field"),
                "verification": result.get("verification"),
            },
        )
    if status_value == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": result.get("error_code") or "OPERATION_CONFLICT",
                    "message": result.get("error") or "Conflict",
                },
                "verification": result.get("verification"),
            },
        )
    if status_value in ("committed_unverified", "effect_unknown"):
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": (
                        "SKILL_PACKAGE_EFFECT_UNKNOWN"
                        if status_value == "effect_unknown"
                        else "SKILL_PACKAGE_DELETE_UNVERIFIED"),
                    "message": result.get("message")
                    or "The skill package deletion outcome is uncertain.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "target_id": result.get("target_id"),
                "data": result.get("data"),
            },
        )
    if status_value == "not_applied":
        raise HTTPException(
            status_code=int(result.get("http_status") or 409),
            detail={
                "error": {
                    "code": result.get("error_code")
                    or "SKILL_PACKAGE_DELETE_NOT_APPLIED",
                    "message": result.get("error")
                    or "The skill package deletion did not apply.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
            },
        )

    # Verified/already-applied envelopes carry the verification inside
    # ``data`` (the receipt helper attaches it there); refused/partial
    # envelopes carry it at the top level. Preserve whichever exists.
    verification = (
        result.get("verification")
        or (result.get("data") or {}).get("verification"))
    return router.success_response(
        data=result.get("data"),
        message=result.get("message") or "Skill package deleted",
        metadata={
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id"),
            "target_id": result.get("target_id"),
            "verification": verification,
        },
    )
