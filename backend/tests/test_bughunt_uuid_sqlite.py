"""TDD bug-hunt: UUID type round-trip on SQLite (R80 follow-up).

`core.models.UUID` binds strings on SQLite but returns ``uuid.UUID`` objects
via ``process_result_value``. With SQLAlchemy 2.0's INSERT..RETURNING on
SQLite, the returned sentinel (uuid.UUID) never matches the bound PK (str) →
KeyError on every insert of models using a UUID PK with a Python-side
string default (e.g. ``boards``, the Kanban models).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def engine():
    from core.database import Base
    from core import models_board  # noqa: F401  (registers Board/BoardColumn/BoardTask)

    eng = create_engine("sqlite:///:memory:", poolclass=None)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    return sessionmaker(bind=engine)()


def test_board_insert_round_trips_uuid_pk(db):
    from core.models_board import Board

    board = Board(name="Sprint 42", slug="sprint-42")
    db.add(board)
    db.commit()

    assert board.id is not None
    assert isinstance(board.id, str)
    uuid.UUID(board.id)

    db.refresh(board)
    assert board.id == str(board.id)


def test_board_task_insert_with_relations(db):
    from core.models_board import Board, BoardColumn, BoardTask

    board = Board(name="B")
    db.add(board)
    db.commit()
    col = BoardColumn(board_id=board.id, name="Todo", position=0)
    db.add(col)
    db.commit()
    task = BoardTask(board_id=board.id, column_id=col.id, title="Write tests")
    db.add(task)
    db.commit()

    assert task.id is not None
    db.refresh(task)
    assert task.title == "Write tests"
    assert task.board_id == board.id


def test_board_query_returns_consistent_ids(db):
    from core.models_board import Board

    ids = [Board(name=f"B{i}") for i in range(3)]
    db.add_all(ids)
    db.commit()

    fetched = db.query(Board).order_by(Board.name).all()
    assert [b.id for b in fetched] == [b.id for b in ids]
