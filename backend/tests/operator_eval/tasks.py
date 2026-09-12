"""Operator eval tasks — verifiable end states against the local site.

Each task: id, goal (what the operator is told), start_url, and verify()
against the site's server-side STATE + the loop result. Verification is
state-based where possible (the site records what actually happened) and
summary-based where the deliverable is information (the code must appear
in the final summary).
"""

from test_site import STATE


def _reset_state():
    STATE.update({
        "form": None, "form_submissions": 0, "form_errors": 0,
        "logged_in": False, "logins": 0, "visited": [],
    })


TASKS = [
    {
        "id": "form_fill",
        "goal": "Go to the form page, fill name='Ada Lovelace', "
                "email='ada@example.com', company='Analytical Engines', "
                "and submit the form.",
        "start_url": "/",
        "verify": lambda result: (
            (STATE.get("form") or {}).get("name") == "Ada Lovelace"
            and STATE["form_submissions"] == 1
        ),
    },
    {
        "id": "find_code",
        "goal": "Find the API secret code in the reference documentation "
                "(docs). Report the code in your final summary.",
        "start_url": "/",
        "verify": lambda result: "ATOM-7741" in (result.get("summary") or ""),
    },
    {
        "id": "login_flow",
        "goal": "Log in to the site (credentials are shown on the login "
                "page) and confirm you reach the dashboard.",
        "start_url": "/login",
        "verify": lambda result: bool(STATE.get("logged_in")),
    },
    {
        "id": "search_and_click",
        "goal": "Search for 'pricing' and open the first search result. "
                "Report the pricing secret word in your summary.",
        "start_url": "/search?q=pricing",
        "verify": lambda result: (
            "/docs/2" in STATE.get("visited", [])
            and "quokka" in (result.get("summary") or "").lower()
        ),
    },
    {
        "id": "ordered_navigation",
        "goal": "Visit docs 1, then docs 2, then docs 3, in that order.",
        "start_url": "/",
        "verify": lambda result: (
            STATE.get("visited", []).count("/docs/1") >= 1
            and STATE["visited"].count("/docs/2") >= 1
            and STATE["visited"].count("/docs/3") >= 1
        ),
    },
    {
        "id": "extract_headline",
        "goal": "Report the top headline shown on the site index page in "
                "your final summary.",
        "start_url": "/",
        "verify": lambda result: "OPERATOR EVAL DAILY"
                                  in (result.get("summary") or "").upper(),
    },
    {
        "id": "scroll_find",
        "goal": "On the long page, find the code at the very bottom and "
                "report it in your final summary.",
        "start_url": "/long",
        "verify": lambda result: "LONGPAGE-99" in (result.get("summary") or ""),
    },
    {
        "id": "form_validation",
        "goal": "Submit the form on the form page with ONLY the name field "
                "filled ('Grace'). Report what the page says in response.",
        "start_url": "/form",
        "verify": lambda result: STATE.get("form_errors", 0) >= 1,
    },
]
