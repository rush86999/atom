"""Real Session/SAVEPOINT ownership; no live database or provider calls."""
import pytest
from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from core.agent_decision_write_service import caller_work_pending


class _Base(DeclarativeBase):
    pass


class _Row(_Base):
    __tablename__ = "caller_ownership_probe"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String)


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ownership.db'}")
    _Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([_Row(id=1, value="original"), _Row(id=2, value="inner")])
        db.commit()
    yield factory
    engine.dispose()


@pytest.mark.parametrize("end", ["commit", "rollback", "close"])
def test_outer_flushed_work_survives_savepoint_end(sessions, end):
    with sessions() as db:
        row = db.get(_Row, 1)
        row.value = "caller-owned"
        db.flush()
        savepoint = db.begin_nested()
        getattr(savepoint, end)()
        assert caller_work_pending(db)
        with sessions() as peer:
            assert peer.get(_Row, 1).value == "original"
            assert not caller_work_pending(peer)
        assert row.value == "caller-owned"
        db.commit()
        assert not caller_work_pending(db)
    with sessions() as peer:
        assert peer.get(_Row, 1).value == "caller-owned"


@pytest.mark.parametrize("end", ["commit", "rollback", "close"])
def test_inner_only_work_tracks_commit_or_discard(sessions, end):
    with sessions() as db:
        savepoint = db.begin_nested()
        db.get(_Row, 2).value = "nested-edit"
        db.flush()
        getattr(savepoint, end)()
        assert caller_work_pending(db) is (end == "commit")
        if end != "commit":
            assert db.get(_Row, 2).value == "inner"
        db.rollback()
        assert not caller_work_pending(db)


@pytest.mark.parametrize("end", ["commit", "rollback", "close"])
def test_nested_child_release_cannot_escape_parent_rollback(sessions, end):
    with sessions() as db:
        db.get(_Row, 1).value = "outer-edit"
        db.flush()
        parent = db.begin_nested()
        child = db.begin_nested()
        db.get(_Row, 2).value = "child-edit"
        db.flush()
        child.commit()
        getattr(parent, end)()
        assert caller_work_pending(db)
        if end != "commit":
            assert db.get(_Row, 2).value == "inner"
        db.rollback()
        assert not caller_work_pending(db)
    with sessions() as peer:
        assert peer.get(_Row, 1).value == "original"


def test_clean_savepoint_and_new_transaction_have_no_pending_writes(sessions):
    with sessions() as db:
        with db.begin_nested():
            assert db.get(_Row, 1).value == "original"
        assert not caller_work_pending(db)
        db.get(_Row, 1).value = "discard"
        db.flush()
        db.rollback()
        assert not caller_work_pending(db)
        assert db.get(_Row, 1).value == "original"


def test_begin_nested_implicit_flush_keeps_outer_caller_ownership(sessions):
    with sessions() as db:
        db.get(_Row, 1).value = "implicit-outer"
        savepoint = db.begin_nested()  # SQLAlchemy flushes before SAVEPOINT.
        savepoint.rollback()
        assert caller_work_pending(db)
        with sessions() as peer:
            assert peer.get(_Row, 1).value == "original"
        db.commit()
        assert not caller_work_pending(db)


def test_session_commit_with_open_savepoint_clears_finished_outer_work(sessions):
    with sessions() as db:
        db.get(_Row, 1).value = "outer-committed"
        db.flush()
        db.begin_nested()
        db.get(_Row, 2).value = "inner-committed"
        db.flush()
        db.commit()
        assert not caller_work_pending(db)
    with sessions() as peer:
        assert peer.get(_Row, 1).value == "outer-committed"
        assert peer.get(_Row, 2).value == "inner-committed"


def test_session_close_with_open_savepoint_rolls_back_caller_work(sessions):
    db = sessions()
    db.get(_Row, 1).value = "outer-discarded"
    db.flush()
    db.begin_nested()
    db.get(_Row, 2).value = "inner-discarded"
    db.flush()
    db.close()
    assert not caller_work_pending(db)
    with sessions() as peer:
        assert peer.get(_Row, 1).value == "original"
        assert peer.get(_Row, 2).value == "inner"
