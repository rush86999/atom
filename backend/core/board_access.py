from __future__ import annotations

"""Authoritative access checks for Kanban boards.

A board is reachable only by the user recorded in ``Board.owner_user_id``.
There is no board membership / sharing relation in the schema, so ownership is
the supported collaboration boundary.  Do not add implicit tenant-wide or
administrator bypasses here: the single-tenant product still has real per-user
ownership.

Both the board service and the comment/decomposition consumers route through
this module so there is exactly one place where the current owner and the
actor's active status are resolved.
"""

from typing import Union

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from core.models import User, UserStatus
from core.models_board import Board

BOARD_NOT_FOUND = "Board not found"
ACTOR_REQUIRED = "Board access requires an authenticated user"
ACTOR_INACTIVE = "Board access requires an active user"
FOREIGN_OWNER = "Cannot create a board for another user"
AUTHORITY_CHANGED = "Board authority changed concurrently. Refresh and retry."


def require_active_actor(
    db: Session, actor_user_id: Union[str, None]
) -> str:
    """Return the actor id only when it is an existing, active user.

    The lookup deliberately refreshes the identity-map copy: a token can be
    issued to an account that is deactivated before the mutation lands, and the
    account state must be authoritative at the moment of the write.
    """
    if not actor_user_id:
        raise HTTPException(status_code=403, detail=ACTOR_REQUIRED)

    actor_id = str(actor_user_id)
    actor = (
        db.query(User)
        .filter(User.id == actor_id)
        .populate_existing()
        .first()
    )
    if (
        actor is None
        or actor.status != UserStatus.ACTIVE
        or actor.is_active is False
    ):
        raise HTTPException(status_code=403, detail=ACTOR_INACTIVE)
    return actor_id


def _raise_claim_failure(
    db: Session, board_id: Union[str, None], actor_id: str
) -> None:
    """Explain why a failed claim was rejected.

    The claim statements deliberately answer with a single row-count so the
    authorization decision happens inside the same write transaction as the
    effect.  This read-only follow-up only selects the public error contract
    (inactive actor -> 403, missing/foreign board -> 404); it never authorizes a
    write and runs after the failed claim has already denied the request.
    """
    actor = (
        db.query(User)
        .filter(User.id == actor_id)
        .populate_existing()
        .first()
    )
    if (
        actor is None
        or actor.status != UserStatus.ACTIVE
        or actor.is_active is False
    ):
        raise HTTPException(status_code=403, detail=ACTOR_INACTIVE)

    if board_id is not None:
        board = (
            db.query(Board)
            .filter(Board.id == board_id)
            .populate_existing()
            .first()
        )
        if (
            board is None
            or board.owner_user_id is None
            or str(board.owner_user_id) != actor_id
        ):
            raise HTTPException(status_code=404, detail=BOARD_NOT_FOUND)

    raise HTTPException(status_code=409, detail=AUTHORITY_CHANGED)


def claim_active_actor(db: Session, actor_user_id: Union[str, None]) -> str:
    """Atomically claim an active actor row for a mutation.

    The first statement of every board mutation is a conditional no-op UPDATE
    rather than the SELECT used by read authorization.  This closes the
    check-then-write window: an account deactivated after the earlier read but
    before the first write is observed by this statement, and databases that
    support row locking hold the user row until the mutation commits.  The
    assignments deliberately target the same values so a successful claim does
    not change the account record.
    """
    if not actor_user_id:
        raise HTTPException(status_code=403, detail=ACTOR_REQUIRED)

    actor_id = str(actor_user_id)
    result = db.execute(
        update(User)
        .where(
            User.id == actor_id,
            User.status == UserStatus.ACTIVE.value,
            User.is_active.is_(True),
        )
        .values(updated_at=User.updated_at)
    )
    if result.rowcount != 1:
        _raise_claim_failure(db, None, actor_id)
    return actor_id


def claim_owned_board(
    db: Session, board_id: str, actor_user_id: Union[str, None]
) -> Board:
    """Claim ownership of ``board_id`` inside the caller's write transaction.

    This is the mutation counterpart of :func:`get_owned_board`.  It first
    claims the actor row (so a concurrent deactivation cannot land between the
    check and the effect) and then performs a conditional no-op UPDATE on the
    board row.  The board update matches only the current owner, re-reading
    ``owner_user_id`` under the write transaction instead of trusting the
    earlier authorization SELECT.  A zero row-count means a peer transferred
    ownership or the board disappeared before our first DML, so the effect is
    refused before it is written.
    """
    actor_id = claim_active_actor(db, actor_user_id)
    result = db.execute(
        update(Board)
        .where(
            Board.id == board_id,
            Board.owner_user_id == actor_id,
        )
        .values(version_id=Board.version_id, updated_at=Board.updated_at)
    )
    if result.rowcount != 1:
        _raise_claim_failure(db, board_id, actor_id)

    board = (
        db.query(Board)
        .filter(Board.id == board_id)
        .populate_existing()
        .first()
    )
    if board is None or str(board.owner_user_id) != actor_id:
        _raise_claim_failure(db, board_id, actor_id)
    return board


def get_owned_board(
    db: Session,
    board_id: str,
    actor_user_id: Union[str, None],
    *,
    for_update: bool = False,
) -> Board:
    """Resolve a board only when the caller is its current owner.

    ``populate_existing`` re-reads owner_user_id instead of trusting a cached
    identity-map instance.  With ``for_update`` the mutation claim above is
    used instead of ``SELECT ... FOR UPDATE``: SQLite ignores row-locking
    clauses, so a check-then-insert sequence still had a real race there.
    Unavailable boards intentionally answer 404 so a guessed id cannot
    distinguish "exists but belongs to someone else" from "does not exist".
    """
    if for_update:
        return claim_owned_board(db, board_id, actor_user_id)

    actor_id = require_active_actor(db, actor_user_id)

    board = (
        db.query(Board)
        .filter(Board.id == board_id)
        .populate_existing()
        .first()
    )

    if (
        board is None
        or board.owner_user_id is None
        or str(board.owner_user_id) != actor_id
    ):
        raise HTTPException(status_code=404, detail=BOARD_NOT_FOUND)
    return board
