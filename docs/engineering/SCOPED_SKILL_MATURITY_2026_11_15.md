# Scoped maturity enforcement for executable skills

Skill execution already received the authenticated tenant and workspace from both the public skills API and the normal agent action. Its maturity lookup nevertheless used a governance object constructed for the default workspace. A STUDENT in another workspace could be missed and continue through the existing system fallback.

Execution now uses governance bound to a supplied tenant/workspace. Calls without either scope keep the existing cached governance object and legacy system behavior. Reviewed-artifact authorization, receipt bindings and sandbox code are unchanged. The public API retains HTTP 400 for the known STUDENT refusal and explains that Python skills require INTERN or higher; unrelated validation and internal errors retain their generic response.

## Regression boundaries

- The real in-process skills API denies a scoped STUDENT before sandbox invocation or a SkillExecution row, while an INTERN in the same scope can execute the approved skill.
- A joined test creates an agent through the public custom API, requests and approves a qualification review, promotes it, opens a fresh database session, and consumes its approved skill through the normal GenericAgent loop. The final answer derives from the tool observation and the execution receipt is bound to the agent, workspace and reviewed artifact. Unapproved and foreign-scope attempts are denied before the sandbox.
- Separate response controls keep unrelated validation/internal errors redacted.

Training evidence rows are synthetic fixtures. Model decisions, scanner and sandbox are deterministic doubles. These tests do not establish ordinary training producers, learned capability, live model or skill quality, a real Docker run, app restart or browser readiness. The original 143 claims and 18 goals remain the completion scope.

## Verification

Run from backend in a fresh TESTING=1 scratch environment with explicit local database, data, BYOK and memory paths:

```sh
python -m pytest tests/test_goal6_skill_maturity_boundary.py tests/test_goal6_ordinary_skill_join.py tests/test_reviewed_executable_skill.py tests/test_reviewed_executable_agent_consumption.py tests/test_reviewed_executable_skill_agent_dispatch.py tests/test_covpush_w116_skill_registry.py tests/test_covpush_skill_registry.py tests/test_governance_maturity_case_fix.py tests/test_skill_registry_service.py -q
```

An independent source-exact comparison of the previous execute_skill method reproduced STUDENT execution through the public API. The scoped fix denied it and preserved INTERN execution. The first wider draft failed two legacy controls; retaining cached governance for calls without scope corrected both without weakening those tests. Independent caller qualification then passed 137 tests under kernel-blocked networking with an actual denied-socket preflight. This preceded the two additional unrelated-error response controls. The final shipping-path and CI-contract selection, including those controls, independently passed 633 tests in 97.82 seconds under the same network boundary. The historical vulnerable-method counterprobe is retained as local evidence rather than a Git-history dependency in shipping tests.

Both new test modules join the existing normal reviewed-skill dispatch CI step. Every preexisting selection is preserved.
