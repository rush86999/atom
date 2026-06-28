from __future__ import annotations

"""
Board task state machine.

The canonical status set is :class:`BoardStatus`. The legal-transition graph is
:data:`STATUS_GRAPH`. ``IllegalBoardTransition`` is raised (and caught by the
HTTP layer) when a PATCH tries an invalid move; the API converts it into
HTTP 422 with the set of allowed next states in the body.
"""

from typing import Final


class BoardStatus:
    """String constants for the six BoardTask statuses.

    Stored as String in the DB for Alembic simplicity — using an actual
    PG ENUM would force a migration every time we add a status. Validation
    lives here, not in the column type.
    """

    BACKLOG: Final[str] = "backlog"
    TODO: Final[str] = "todo"
    IN_PROGRESS: Final[str] = "in_progress"
    IN_REVIEW: Final[str] = "in_review"
    BLOCKED: Final[str] = "blocked"
    DONE: Final[str] = "done"

    ALL: Final[tuple[str, ...]] = (
        BACKLOG,
        TODO,
        IN_PROGRESS,
        IN_REVIEW,
        BLOCKED,
        DONE,
    )


# Directed graph of legal forward/sideways transitions.
STATUS_GRAPH: Final[dict[str, frozenset[str]]] = {
    BoardStatus.BACKLOG: frozenset({BoardStatus.TODO, BoardStatus.BLOCKED}),
    BoardStatus.TODO: frozenset(
        {BoardStatus.IN_PROGRESS, BoardStatus.BLOCKED, BoardStatus.BACKLOG}
    ),
    BoardStatus.IN_PROGRESS: frozenset(
        {BoardStatus.IN_REVIEW, BoardStatus.DONE, BoardStatus.BLOCKED, BoardStatus.TODO}
    ),
    BoardStatus.IN_REVIEW: frozenset(
        {
            BoardStatus.IN_PROGRESS,
            BoardStatus.DONE,
            BoardStatus.BLOCKED,
            BoardStatus.TODO,
        }
    ),
    BoardStatus.BLOCKED: frozenset(
        {BoardStatus.TODO, BoardStatus.IN_PROGRESS, BoardStatus.IN_REVIEW}
    ),
    BoardStatus.DONE: frozenset({BoardStatus.TODO}),  # reopen only
}


class IllegalBoardTransition(Exception):
    """Raised when a status transition is not in :data:`STATUS_GRAPH`."""

    def __init__(self, current: str, requested: str, allowed_next: frozenset[str]):
        self.current = current
        self.requested = requested
        self.allowed_next = allowed_next
        super().__init__(
            f"Illegal board task transition: {current!r} -> {requested!r}. "
            f"Allowed next states: {sorted(allowed_next)}"
        )


def assert_transition(current: str, requested: str) -> None:
    """Raise :class:`IllegalBoardTransition` unless ``current -> requested`` is legal."""
    if requested not in BoardStatus.ALL:
        raise IllegalBoardTransition(current, requested, STATUS_GRAPH.get(current, frozenset()))

    if current == requested:
        return

    allowed = STATUS_GRAPH.get(current, frozenset())
    if requested not in allowed:
        raise IllegalBoardTransition(current, requested, allowed)


def is_transition_allowed(current: str, requested: str) -> bool:
    """Non-throwing variant of :func:`assert_transition`."""
    try:
        assert_transition(current, requested)
        return True
    except IllegalBoardTransition:
        return False


def allowed_next_statuses(current: str) -> frozenset[str]:
    """Return the set of legal forward/sideways transitions from ``current``."""
    return STATUS_GRAPH.get(current, frozenset())
