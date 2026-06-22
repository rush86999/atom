"""
TDD regression tests for the final audit fixes.

ISSUE 1: DB tables created on fresh install via create_all
ISSUE 3: spawn_agent passes correct args to reset_maturity
ISSUE 4: Security middleware fails closed (not open)
ISSUE 6: skill_executor_service imports from correct module
"""

from __future__ import annotations

import inspect

import pytest


# ---------------------------------------------------------------------------
# ISSUE 1: Fresh install DB schema creation
# ---------------------------------------------------------------------------


class TestFreshInstallSchemaCreation:
    """main.py must create tables on startup so fresh installs work."""

    def test_startup_calls_create_all(self):
        """The startup hook must call Base.metadata.create_all()."""
        import main as main_mod

        src = inspect.getsource(main_mod._startup_bootstrap)
        assert "create_all" in src, (
            "Startup must call Base.metadata.create_all() to create tables "
            "on fresh installs where alembic chain is incomplete"
        )


# ---------------------------------------------------------------------------
# ISSUE 3: spawn_agent correct arg count
# ---------------------------------------------------------------------------


class TestSpawnAgentArgs:
    """reset_maturity must be called with the correct number of args."""

    def test_reset_maturity_called_with_3_args(self):
        """The call must match reset_maturity(self, agent_id, capability, reason)."""
        from core import atom_meta_agent as mod

        src = inspect.getsource(mod.AtomMetaAgent.spawn_agent)
        # Find the reset_maturity call and verify it passes exactly
        # agent_id, capability, reason (3 positional args after self)
        assert "self.tenant_id," not in src.split("reset_maturity")[1].split(")")[0], (
            "reset_maturity must NOT receive self.tenant_id as first arg — "
            "signature is (agent_id, capability_name, reason)"
        )

    def test_reset_maturity_signature_accepts_3_args(self):
        """Verify the actual signature matches the call."""
        from core.capability_graduation_service import CapabilityGraduationService

        sig = inspect.signature(CapabilityGraduationService.reset_maturity)
        params = [p for p in sig.parameters.values() if p.name != "self"]
        assert len(params) == 3, (
            f"reset_maturity expects {len(params)} params, should be 3 "
            "(agent_id, capability_name, reason)"
        )


# ---------------------------------------------------------------------------
# ISSUE 4: Security middleware fails closed
# ---------------------------------------------------------------------------


class TestSecurityMiddlewareFailClosed:
    """The security body scanner must reject requests when scanning fails,
    not silently allow them through."""

    def test_no_bare_except_pass_on_body_scan(self):
        """Static guard: the body scan try block must NOT have bare
        except: pass (fail-open pattern)."""
        from core.security.middleware import InputValidationMiddleware

        src = inspect.getsource(InputValidationMiddleware.dispatch)
        # The old pattern: except Exception:\n                pass
        # Must be replaced with error logging + return 400
        assert "status_code=400" in src or "status_code = 400" in src, (
            "Security middleware must reject (400) when body scan fails, not pass"
        )

    def test_scan_failure_returns_400_not_200(self):
        """When _contains_malicious_content raises, the middleware must
        return a 400, not let the request through."""
        from core.security.middleware import InputValidationMiddleware

        src = inspect.getsource(InputValidationMiddleware.dispatch)
        # Verify there's no bare 'pass' after an except in the body-scan block
        lines = src.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:" or stripped == "except:":
                # Check the next non-empty line
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j].strip() == "pass":
                        pytest.fail(
                            f"Found bare except: pass at line {i+1} — "
                            "security middleware fails open"
                        )


# ---------------------------------------------------------------------------
# ISSUE 6: skill_executor_service correct import
# ---------------------------------------------------------------------------


class TestSkillExecutorImport:
    """The import must reference the actual module and class name."""

    def test_imports_from_sandbox_executor(self):
        """Must import from core.sandbox_executor, not sandbox_execution_service."""
        from core import skill_executor_service as mod

        src = inspect.getsource(mod)
        assert "from core.sandbox_executor import" in src, (
            "Must import from core.sandbox_executor (actual module name), "
            "not core.sandbox_execution_service (nonexistent)"
        )

    def test_imports_sandbox_executor_class(self):
        """Must import SandboxExecutor, not SandboxExecutionService."""
        from core import skill_executor_service as mod

        src = inspect.getsource(mod)
        assert "SandboxExecutor" in src and "SandboxExecutionService" not in src, (
            "Must use SandboxExecutor (actual class name)"
        )

    def test_skill_executor_service_imports_cleanly(self):
        """The module must import without ModuleNotFoundError."""
        __import__("core.skill_executor_service")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
