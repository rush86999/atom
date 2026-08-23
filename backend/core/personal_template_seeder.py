"""Personal-wedge starter template seeding.

The Personal→Team pathway ships three solo-operator starter templates as JSON
files in ``backend/workflow_templates/personal_*.json``. The visual editor and
marketplace UI read templates from the *database* ORM model
(``core.models.WorkflowTemplate``) — not the file-based
``WorkflowTemplateManager`` — so without this seeder the starters never reach
the surface that matters for first-run onboarding.

Idempotent by design: existing rows (by primary key = ``template_id``) are
left untouched, so user modifications survive restarts. Never raises —
seeding is content convenience, not a boot requirement.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PERSONAL_TEMPLATE_GLOB = "personal_*.json"


def _templates_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "workflow_templates"


def _load_personal_files() -> List[Dict[str, Any]]:
    """Load raw personal-starter template dicts from disk (sorted, deterministic)."""
    out: List[Dict[str, Any]] = []
    for path in sorted(_templates_dir().glob(PERSONAL_TEMPLATE_GLOB)):
        try:
            with open(path) as f:
                data = json.load(f)
            if data.get("template_id"):
                out.append(data)
        except Exception as e:  # noqa: BLE001 - one bad file must not block boot
            logger.error(f"Skipping unreadable starter template {path.name}: {e}")
    return out


def _orm_row_from_starter(data: Dict[str, Any], author_id: str) -> Dict[str, Any]:
    """Map a file-based starter dict onto the WorkflowTemplate ORM columns.

    The ORM model is intentionally narrower than the pydantic template system
    (no complexity/tags/steps_schema columns), so richer fields are packed
    into ``input_schema`` where the UI can still read them.
    """
    from core.workflow_template_system import WorkflowTemplate as _PydanticTemplate

    template = _PydanticTemplate(**data)
    return {
        "id": template.template_id,
        "tenant_id": None,  # global starter content, visible across tenants
        "author_id": author_id,
        "name": template.name,
        "description": template.description,
        "category": template.category.value if hasattr(template.category, "value") else str(template.category),
        "icon": "personal",
        "steps": [s.model_dump(by_alias=True) for s in template.steps],
        "input_schema": {
            "parameters": [p.model_dump() for p in template.inputs],
            "output_schema": template.output_schema,
            "tags": template.tags,
            "dependencies": template.dependencies,
            "prerequisites": template.prerequisites,
            "complexity": template.complexity.value
            if hasattr(template.complexity, "value")
            else str(template.complexity),
        },
        "is_public": True,
        "is_approved": True,
        "version": template.version,
        "usage_count": 0,
        "rating": 0.0,
        "rating_count": 0,
    }


def seed_personal_templates(db) -> int:
    """Insert any missing personal starter templates into the DB. Returns count.

    Idempotent: skips ids already present (never overwrites user edits).
    Fails soft: logs and returns 0 on any error — boot must not depend on it.
    """
    try:
        from core.models import User, WorkflowTemplate as ORMTemplate

        starters = _load_personal_files()
        if not starters:
            return 0

        # Starter rows need an author (NOT NULL FK); attribute them to the
        # earliest user (the bootstrap admin in practice).
        author = db.query(User).order_by(User.created_at.asc()).first()
        if author is None:
            logger.info("Personal template seeding skipped: no users exist yet")
            return 0

        existing_ids = {
            row.id
            for row in db.query(ORMTemplate.id)
            .filter(
                ORMTemplate.id.in_([s.get("template_id") for s in starters])
            )
            .all()
        }

        inserted = 0
        for data in starters:
            template_id = data["template_id"]
            if template_id in existing_ids:
                continue
            db.add(ORMTemplate(**_orm_row_from_starter(data, author_id=author.id)))
            inserted += 1

        if inserted:
            db.commit()
            logger.info(f"Seeded {inserted} personal starter template(s)")
        return inserted
    except Exception as e:  # noqa: BLE001 - fail-soft by contract
        logger.error(f"Personal template seeding failed (non-fatal): {e}")
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return 0
