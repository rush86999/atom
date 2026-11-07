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
from sqlalchemy.orm import Session

from core.models import User, UserStatus
from core.models_board import Board

BOARD_NOT_FOUND = "Board not found"
ACTOR_REQUIRED = "Board access requires an authenticated user"
ACTOR_INACTIVE = "Board access requires an active user"
FOREIGN_OWNER = "Cannot create a board for another user"


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


def get_owned_board(
    db: Session,
    board_id: str,
    actor_user_id: Union[str, None],
    *,
    for_update: bool = False,
) -> Board:
    """Resolve a board only when the caller is its current owner.

    ``populate_existing`` re-reads owner_user_id instead of trusting a cached
    identity-map instance, and ``for_update`` (where the database supports it)
    holds the ownership row stable for the duration of a mutation.  Unavailable
    boards intentionally answer 404 so a guessed id cannot distinguish
    "exists but belongs to someone else" from "does not exist".
    """
    actor_id = require_active_actor(db, actor_user_id)

    query = db.query(Board).filter(Board.id == board_id)
    if for_update:
        query = query.with_for_update()
    board = query.populate_existing().first()

    if (
        board is None
        or board.owner_user_id is None
        or str(board.owner_user_id) != actor_id
    ):
        raise HTTPException(status_code=404, detail=BOARD_NOT_FOUND)
    return board
