"""Personal-wedge starter templates (bottom-up pathway).

The Personal Edition wedge ships pre-built solo-operator templates. These tests
lock the contract every starter template must satisfy:

1. Loads cleanly through the real ``WorkflowTemplate`` model (dependency graph
   validated by pydantic).
2. Beginner complexity + ``personal-edition``/``solo-operator`` tags — the
   wedge must be low-friction by definition.
3. Every template contains a HITL approval step — governed-by-design is the
   product promise; a starter that sends without review would break it.
4. No credential-shaped keys anywhere in the template JSON (P5
   ``strip_credentials`` denylist philosophy applied to shipped content).
5. Declared duration equals the sum of its steps.

These are content-contract tests: they run against the repository's actual
``backend/workflow_templates/personal_*.json`` files so adding/removing a
starter template updates expectations automatically.
"""

import json
from pathlib import Path

import pytest

from core.workflow_template_system import TemplateComplexity, WorkflowTemplate

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "workflow_templates"
PERSONAL_FILES = sorted(TEMPLATES_DIR.glob("personal_*.json"))

# P5 blueprint-sanitizer denylist philosophy: credential-shaped keys never ship.
_CREDENTIAL_KEY_DENYLIST = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "private_key",
    "authorization",
)


def _iter_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k).lower(), v
            yield from _iter_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_keys(item)


def _load_template(path: Path) -> WorkflowTemplate:
    with open(path) as f:
        return WorkflowTemplate(**json.load(f))


def test_personal_starters_exist() -> None:
    """The bottom-up wedge ships with at least three solo-operator starters."""
    assert len(PERSONAL_FILES) >= 3


@pytest.mark.parametrize("path", PERSONAL_FILES, ids=lambda p: p.name)
def test_template_loads_through_real_model(path: Path) -> None:
    """Each file validates as a WorkflowTemplate (step deps checked by pydantic)."""
    template = _load_template(path)
    assert template.template_id.startswith("template_personal_")
    assert len(template.steps) >= 3


@pytest.mark.parametrize("path", PERSONAL_FILES, ids=lambda p: p.name)
def test_wedge_is_beginner_and_tagged(path: Path) -> None:
    """Low-friction by contract: beginner complexity + personal/solo tags."""
    template = _load_template(path)
    assert template.complexity == TemplateComplexity.BEGINNER
    tags = set(template.tags)
    assert "personal-edition" in tags
    assert "solo-operator" in tags


@pytest.mark.parametrize("path", PERSONAL_FILES, ids=lambda p: p.name)
def test_every_starter_has_hitl_approval_gate(path: Path) -> None:
    """Governed-by-design: nothing reaches a THIRD PARTY without an approval step.

    Self-notifications (digests/pings to the operator, declared via
    ``"audience": "self"``) are exempt — that's what autopilot is for.
    """
    template = _load_template(path)
    approval_steps = {s.step_id for s in template.steps if s.step_type == "approval"}
    assert approval_steps, f"{template.name} has no approval gate"

    for step in template.steps:
        if step.action in ("send_email", "send_message", "send_dm"):
            params = step.parameters if isinstance(step.parameters, dict) else {}
            if params.get("audience") == "self":
                continue
            assert set(step.depends_on) & approval_steps, (
                f"{step.step_id} sends outward without passing the approval gate"
            )


@pytest.mark.parametrize("path", PERSONAL_FILES, ids=lambda p: p.name)
def test_no_credential_shaped_keys(path: Path) -> None:
    """Starter templates carry configuration, never secrets."""
    with open(path) as f:
        data = json.load(f)
    for key in _iter_keys(data):
        for banned in _CREDENTIAL_KEY_DENYLIST:
            assert banned not in key, f"{path.name}: credential-shaped key '{key}'"


@pytest.mark.parametrize("path", PERSONAL_FILES, ids=lambda p: p.name)
def test_declared_duration_matches_steps(path: Path) -> None:
    """Honest time estimates: declared total == sum of step estimates."""
    template = _load_template(path)
    assert template.calculate_estimated_duration() > 0
    step_sum = sum(s.estimated_duration for s in template.steps)
    assert template.estimated_total_duration == step_sum


@pytest.mark.parametrize("path", PERSONAL_FILES, ids=lambda p: p.name)
def test_prerequisites_declare_integrations(path: Path) -> None:
    """First-run friction is surfaced up front: dependencies listed for humans too."""
    template = _load_template(path)
    services_in_steps = {
        s.service for s in template.steps if s.service and s.service != "workflow"
    }
    assert template.prerequisites, f"{template.name}: no prerequisites listed"
    assert template.dependencies, f"{template.name}: no dependency integrations listed"
    # Services referenced by steps should appear in the declared dependencies.
    missing = {s for s in services_in_steps - {"agent", "governance"} } - set(
        template.dependencies
    )
    assert not missing, f"{template.name}: steps use undeclared services {missing}"
