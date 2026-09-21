"""Operator eval tasks — verifiable end states against the local site.

Each task: id, goal (what the operator is told), start_url, and
verify(result, site) against the site's PROTECTED evidence + WORLD ground
truth + the loop result. Verification is evidence-based where possible (the
site records what actually happened) and summary-based where the deliverable
is information (the value must appear in the final summary).

Rev 2 hardening (ENV_HARNESS_ADOPTION_PLAN §1b):
- verifiers read the site INSTANCE (world values + evidence), never a
  module-global, so parameterized task families and concurrent runs work;
- form_fill now verifies ALL THREE requested fields + the submission count
  (previously: name only — email/company outcomes were unverified);
- form_validation now verifies the error count AND that the summary reports
  the actual error message the page showed (previously: error counter only —
  the requested report was unverified), with the message read back from
  evidence so world/mutation changes to the copy stay verifier-consistent.
"""

from test_site import EvalSite, default_world


def _reset_site(site: EvalSite) -> None:
    """Fresh task start: base world restored, evidence cleared, rules off."""
    site.control_reset()


def _verify_ordered_navigation(result, site: EvalSite) -> bool:
    """Docs 1, 2, 3 visited IN THAT ORDER — the goal says 'in that order',
    so presence alone is not a pass; first-visit positions must ascend."""
    visited = site.evidence.get("visited", [])
    targets = ("/docs/1", "/docs/2", "/docs/3")
    if not all(p in visited for p in targets):
        return False
    positions = [visited.index(p) for p in targets]
    return positions == sorted(positions)


def _summary(result) -> str:
    return (result or {}).get("summary") or ""


BASE_TASKS = [
    {
        "id": "form_fill",
        "goal": "Go to the form page, fill name='Ada Lovelace', "
                "email='ada@example.com', company='Analytical Engines', "
                "and submit the form.",
        "start_url": "/",
        "verify": lambda result, site: (
            (site.evidence.get("form") or {}).get("name") == "Ada Lovelace"
            and (site.evidence.get("form") or {}).get("email") == "ada@example.com"
            and (site.evidence.get("form") or {}).get("company") == "Analytical Engines"
            and site.evidence["form_submissions"] == 1
        ),
    },
    {
        "id": "find_code",
        "goal": "Find the API secret code in the reference documentation "
                "(docs). Report the code in your final summary.",
        "start_url": "/",
        "verify": lambda result, site: (
            site.world["docs"]["3"]["api_code"] in _summary(result)
        ),
    },
    {
        "id": "login_flow",
        "goal": "Log in to the site (credentials are shown on the login "
                "page) and confirm you reach the dashboard.",
        "start_url": "/login",
        "verify": lambda result, site: bool(site.evidence.get("logged_in")),
    },
    {
        "id": "search_and_click",
        "goal": "Search for 'pricing' and open the first search result. "
                "Report the pricing secret word in your summary.",
        "start_url": "/search?q=pricing",
        "verify": lambda result, site: (
            "/docs/2" in site.evidence.get("visited", [])
            and site.world["docs"]["2"]["secret_word"] in _summary(result).lower()
        ),
    },
    {
        "id": "ordered_navigation",
        "goal": "Visit docs 1, then docs 2, then docs 3, in that order.",
        "start_url": "/",
        "verify": _verify_ordered_navigation,
    },
    {
        "id": "extract_headline",
        "goal": "Report the top headline shown on the site index page in "
                "your final summary.",
        "start_url": "/",
        "verify": lambda result, site: (
            site.world["headline"] in _summary(result).upper()
        ),
    },
    {
        "id": "scroll_find",
        "goal": "On the long page, find the code at the very bottom and "
                "report it in your final summary.",
        "start_url": "/long",
        "verify": lambda result, site: (
            site.world["longpage_code"] in _summary(result)
        ),
    },
    {
        "id": "form_validation",
        "goal": "Submit the form on the form page with ONLY the name field "
                "filled ('Grace'). Report what the page says in response.",
        "start_url": "/form",
        "verify": lambda result, site: (
            site.evidence.get("form_errors", 0) >= 1
            and bool(site.evidence.get("last_form_error"))
            and site.evidence["last_form_error"].lower() in _summary(result).lower()
        ),
    },
]


def get_task(task_id: str) -> dict:
    for task in BASE_TASKS:
        if task["id"] == task_id:
            return task
    raise KeyError(f"unknown task {task_id!r}")


# Backwards-compatible alias for existing callers that do `from tasks import TASKS`.
TASKS = BASE_TASKS

# Verifier sanity: the base world must satisfy every summary-based ground
# truth these checks read (guards an accidental schema drift).
_base = default_world()
assert _base["docs"]["3"]["api_code"], "base world lost api_code"
assert _base["docs"]["2"]["secret_word"], "base world lost secret_word"
assert _base["longpage_code"] and _base["headline"], "base world lost codes"
