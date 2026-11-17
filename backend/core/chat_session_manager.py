#!/usr/bin/env python3
"""
Chat Session Manager for ATOM
Manages chat session metadata (Hybrid: DB + JSON fallback)
"""

from datetime import datetime, timezone
import contextlib
import json
import logging
import math
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import String, cast, desc, text, update
from sqlalchemy.orm import Session

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None

# Conditional Import to avoid circular dependencies if simple script
try:
    from core.database import SessionLocal, get_db_session
    from core.models import ChatMessage, ChatSession
    DB_AVAILABLE = True
except ImportError:
    SessionLocal = None
    ChatSession = None
    ChatMessage = None
    DB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Sessions file path (Fallback). ANCHORED to ATOM_DATA_DIR when set (the
# scratch-world isolation contract, same class as the LanceDB/BYOK stores):
# a fallback store must belong to the world that wrote it - an unanchored
# path made every scratch world share (and overwrite) the dev sessions
# file on completed turns.
SESSIONS_FILE = os.path.join(
    os.environ.get("ATOM_DATA_DIR")
    or os.path.dirname(os.path.dirname(__file__)),
    "chat_sessions.json")

#: Every DB metadata write replaces the whole JSON snapshot under an exact
#: snapshot condition (`UPDATE ... WHERE metadata_json = <pre-read snapshot>`).
#: A concurrent commit makes the condition miss, so the writer re-reads and
#: re-merges instead of overwriting the other writer's keys. The bounded loop
#: below is the established optimistic-concurrency pattern (SQLAlchemy version
#: counters; PostgreSQL READ COMMITTED statement re-check).
_METADATA_CAS_ATTEMPTS = 8
_METADATA_CAS_RETRY_SLEEP = 0.005
#: Internal version/diagnostic token. It changes on every successful manager
#: write, but correctness does NOT depend on it: whole-snapshot equality also
#: catches direct ORM writers that never touch this key.
_METADATA_REVISION_KEY = "_metadata_revision"
_MISSING = object()

#: File-mode cross-process lock. `flock`/`msvcrt` advisory locks are released
#: by the kernel on process exit, and a stable sibling `.lock` file is the
#: gate. The thread RLock/depth map makes nested writer→helper calls reuse the
#: outer OS lock instead of trying a second flock on a fresh descriptor.
_FILE_LOCK_TIMEOUT_SECONDS = 10.0
_FILE_LOCK_POLL_SECONDS = 0.01
_FILE_LOCKS_GUARD = threading.Lock()
_FILE_LOCKS: Dict[str, threading.RLock] = {}
_FILE_LOCK_STATE = threading.local()


def _file_thread_lock(lock_path: str) -> threading.RLock:
    with _FILE_LOCKS_GUARD:
        lock = _FILE_LOCKS.get(lock_path)
        if lock is None:
            lock = threading.RLock()
            _FILE_LOCKS[lock_path] = lock
        return lock


@contextlib.contextmanager
def _interprocess_file_lock(
    lock_path: str,
    *,
    timeout: float = _FILE_LOCK_TIMEOUT_SECONDS,
):
    """Hold a cross-process exclusive advisory lock for a JSON store.

    Yields True when the lock is held, False when it could not be acquired
    before the deadline (the caller must report a truthful write failure and
    must not modify the store). The lock file is stable and intentional; it is
    never unlinked (removing it would split the lock namespace).

    `flock(2)` / `msvcrt.locking` are the standard advisory primitives; the
    repo already uses the same pattern in `core/lance_write_lock.py` and
    `core/task_lifecycle._creation_guard`.
    """
    real_path = os.path.realpath(os.path.abspath(lock_path))
    thread_lock = _file_thread_lock(real_path)
    with thread_lock:
        depths = getattr(_FILE_LOCK_STATE, "depths", None)
        if depths is None:
            depths = {}
            _FILE_LOCK_STATE.depths = depths
        depth = depths.get(real_path, 0)
        if depth > 0:
            depths[real_path] = depth + 1
            try:
                yield True
            finally:
                depths[real_path] = depth
            return

        fd = None
        acquired = False
        try:
            parent = os.path.dirname(real_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            fd = os.open(real_path, os.O_RDWR | os.O_CREAT, 0o644)
            if os.fstat(fd).st_size == 0:
                try:
                    os.write(fd, b"\0")
                except OSError:
                    pass
            deadline = time.monotonic() + max(0.1, float(timeout))
            while True:
                try:
                    if fcntl is not None:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                        break
                    if msvcrt is not None:  # pragma: no cover - Windows
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                        acquired = True
                        break
                    # No OS coordination exists. Do not claim a cross-process
                    # lock; fail closed so file-mode callers report not-saved.
                    logger.error(
                        "no OS advisory file-lock primitive is available; "
                        "refusing file-mode write without cross-process "
                        "coordination")
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        logger.error(
                            "sessions file lock timeout: %s", real_path)
                        break
                    time.sleep(_FILE_LOCK_POLL_SECONDS)
        except Exception as exc:  # noqa: BLE001 — truthful lock failure
            logger.error("sessions file lock unavailable: %s", exc)
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            yield False
            return
        if not acquired:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            yield False
            return
        depths[real_path] = 1
        try:
            yield True
        finally:
            depths[real_path] = 0
            try:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                elif msvcrt is not None:  # pragma: no cover - Windows
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass


class ChatSessionManager:
    """Manages chat session metadata with DB support"""
    
    def __init__(self, sessions_file: str = None, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self.sessions_file = sessions_file or SESSIONS_FILE
        
        # Determine persistence mode
        self.persistence_mode = os.getenv("CHAT_PERSISTENCE_MODE", "HYBRID").upper()
        
        # Determine if we should use DB
        self.use_db = False
        
        if self.persistence_mode == "STRICT_DB":
            if not (DB_AVAILABLE and SessionLocal):
                raise RuntimeError("CHAT_PERSISTENCE_MODE is STRICT_DB but database dependencies are missing!")
            
            # Verify connection
            try:
                with get_db_session() as db:
                    # Simple connection test
                    self.use_db = True
                    logger.info("ChatSessionManager initialized in STRICT_DB mode.")
            except Exception as e:
                raise RuntimeError(f"CHAT_PERSISTENCE_MODE is STRICT_DB but database connection failed: {e}")
                
        elif DB_AVAILABLE and SessionLocal:
             # Check if we can actually connect (simple check)
             try:
                 # Optional: Add logic to force file mode via env var if needed
                 if os.getenv("ATOM_CHAT_STORAGE", "auto") != "file":
                     self.use_db = True
             except Exception:
                 logger.warning("DB available but configuration check failed. Defaulting to file.")
        
        # Initialize file fallback ONLY if not in strict mode
        if not self.use_db and self.persistence_mode != "STRICT_DB":
             self._ensure_file()
        elif not self.use_db and self.persistence_mode == "STRICT_DB":
             # Should be unreachable due to exception above, but safety check
             raise RuntimeError("Failed to initialize DB in STRICT_DB mode")

    def _ensure_file(self):
        """Ensure sessions file exists"""
        if not os.path.exists(self.sessions_file):
            self._save_sessions_file([])
    
    def _load_sessions_file_checked(self):
        """Load the JSON store and report whether the read actually succeeded.

        Returns ``(sessions, readable)``. ``readable=False`` means the store
        exists but could not be parsed/read; callers that are deciding whether
        durable state is ABSENT must not turn that into an empty list.
        """
        if not os.path.exists(self.sessions_file):
            return [], True
        try:
            with open(self.sessions_file, 'r') as f:
                loaded = json.load(f)
            if not isinstance(loaded, list):
                logger.error("Sessions file is not a list")
                return [], False
            return loaded, True
        except Exception as e:
            logger.error(f"Failed to load sessions file: {e}")
            return [], False

    def _load_sessions_file(self) -> List[Dict[str, Any]]:
        """Load all sessions from file (legacy helper: unreadable -> [])."""
        sessions, _readable = self._load_sessions_file_checked()
        return sessions
            
    def _load_sessions(self) -> List[Dict[str, Any]]:
        """Load sessions from DB if available, else file"""
        if self.use_db:
             # Warning: This loads ALL sessions. Use carefully.
            with get_db_session() as db:
                try:
                    sessions = db.query(ChatSession).all()
                    return [{
                        "session_id": s.id,
                        "user_id": s.user_id,
                        "title": s.title, # Added title
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "last_active": s.updated_at.isoformat() if s.updated_at else None,
                        "history": [], # Heavy payload skipped
                        "metadata": s.metadata_json or {}
                    } for s in sessions]
                except Exception as e:
                    logger.error(f"DB Load All Sessions failed: {e}")
                finally:
                    db.close()
                
        return self._load_sessions_file()
    
    def _save_sessions_file(
        self, sessions: List[Dict[str, Any]], *, locked: bool = False
    ) -> bool:
        """Atomically replace the JSON store; Returns True on success.

        The write itself always goes through a unique temp file + fsync +
        ``os.replace``. Callers that already hold the interprocess lock pass
        ``locked=True``; all other callers acquire it here so a concurrent
        process cannot collide on the temp path or interleave a partial write.
        """
        if locked:
            return self._write_sessions_file_unlocked(sessions)
        with _interprocess_file_lock(
                self.sessions_file + ".lock") as acquired:
            if not acquired:
                return False
            return self._write_sessions_file_unlocked(sessions)

    def _write_sessions_file_unlocked(
        self, sessions: List[Dict[str, Any]]
    ) -> bool:
        try:
            directory = os.path.dirname(self.sessions_file) or "."
            os.makedirs(directory, exist_ok=True)
            fd, temp_file = tempfile.mkstemp(
                prefix=f".{os.path.basename(self.sessions_file)}.",
                suffix=".tmp",
                dir=directory,
            )
            try:
                os.close(fd)
                with open(temp_file, "w") as f:
                    json.dump(sessions, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_file, self.sessions_file)
                try:
                    dir_fd = os.open(directory, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    pass
                return True
            finally:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except OSError:
                        pass
        except Exception as e:
            logger.error(f"Failed to save sessions file: {e}")
            return False

    def create_session(
        self,
        user_id: str,
        metadata: Dict[str, Any] = None,
        session_id: str = None,
        channel_id: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> str:
        """Create a new chat session."""
        if not session_id:
            session_id = str(uuid.uuid4())

        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
                try:
                    new_session = ChatSession(
                        id=session_id,
                        user_id=user_id,
                        metadata_json=metadata or {},
                        # R72 Workstream I — bind the session to its source
                        # channel/thread so context never leaks cross-channel.
                        channel_id=channel_id,
                        thread_id=thread_id,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        message_count=0
                    )
                    db.add(new_session)
                    db.commit()
                    logger.info(f"Created DB session: {session_id}")
                    return session_id
                except Exception as e:
                    if self.persistence_mode == "STRICT_DB":
                        logger.error(f"DB Create Session failed in STRICT_DB mode: {e}")
                        db.rollback()
                        raise RuntimeError(f"Database write failed in STRICT_DB mode: {e}")

                    logger.error(f"DB Create Session failed: {e}. Falling back to file.")
                    db.rollback()
                    # Fallthrough to file
                finally:
                    db.close()

        if self.persistence_mode == "STRICT_DB":
             raise RuntimeError("Critical Error: DB flow passed but no session returned")

        # 2. File Path (Fallback or Primary)
        with _interprocess_file_lock(
                self.sessions_file + ".lock") as acquired:
            if not acquired:
                logger.error(
                    "session %s was not persisted: file lock unavailable",
                    session_id)
                return session_id
            sessions = self._load_sessions_file()
            file_metadata = dict(metadata or {})
            if channel_id:
                file_metadata["channel_id"] = channel_id
            if thread_id:
                file_metadata["thread_id"] = thread_id
            session = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": timestamp,
                "last_active": timestamp,
                "metadata": file_metadata,
                "message_count": 0,
                "history": []
            }
            sessions.append(session)
            self._save_sessions_file(sessions, locked=True)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
                try:
                    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                    if session:
                        # Fetch chat history from ChatMessage table
                        messages = db.query(ChatMessage)\
                            .filter(ChatMessage.conversation_id == session_id)\
                            .order_by(desc(ChatMessage.created_at))\
                            .limit(100)\
                            .all()

                        history = [
                            {
                                "role": msg.role,
                                "content": msg.content,
                                "created_at": msg.created_at.isoformat() if msg.created_at else None
                            }
                            for msg in messages
                        ]

                        return {
                            "session_id": session.id,
                            "user_id": session.user_id,
                            "created_at": session.created_at.isoformat() if session.created_at else None,
                            "last_active": session.updated_at.isoformat() if session.updated_at else None,
                            "metadata": session.metadata_json or {},
                            "message_count": session.message_count,
                            # R72 Workstream I — surface channel/thread binding.
                            "channel_id": session.channel_id,
                            "thread_id": session.thread_id,
                            "history": history
                        }
                except Exception as e:
                    if self.persistence_mode == "STRICT_DB":
                        logger.error(f"DB Get Session failed in STRICT_DB mode: {e}")
                        raise RuntimeError(f"Database read failed in STRICT_DB mode: {e}")
                    logger.warning(f"DB Get Session failed: {e}")
                finally:
                    db.close()

        if self.persistence_mode == "STRICT_DB":
            return None # Do not fall back to file implementation

        # File fallback
        sessions = self._load_sessions_file()
        return next((s for s in sessions if s['session_id'] == session_id), None)
    
    def read_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """Read the authoritative metadata snapshot for one session.

        Returns ``{"readable", "found", "metadata", "error"}``.  A read
        failure is reported as ``readable=False`` and is NEVER collapsed into
        ``found=False``: callers that decide whether durable state is absent
        (clear/cancel/resume) must distinguish "the store said no" from "the
        store did not answer".

        In DB mode the database is authoritative.  A successful row read with
        no row falls back to the JSON store only because HYBRID mode treats a
        legacy file-only session as a real session; a DB *exception* does not
        fall back (a stale file must not shadow a merely unreachable DB).
        """
        result: Dict[str, Any] = {
            "readable": True,
            "found": False,
            "metadata": {},
            "revision": "",
        }
        if not session_id:
            return result
        if self.use_db:
            try:
                with get_db_session() as db:
                    row = db.query(ChatSession).filter(
                        ChatSession.id == session_id).first()
                    if row is not None:
                        metadata = dict(row.metadata_json or {})
                        result.update({
                            "found": True,
                            "metadata": metadata,
                            "revision": str(
                                metadata.get(_METADATA_REVISION_KEY) or ""),
                        })
                        return result
            except Exception as e:  # noqa: BLE001 — report unreadable
                logger.warning(
                    f"DB metadata read failed for {session_id}: {e}")
                return {
                    "readable": False,
                    "found": False,
                    "metadata": {},
                    "revision": "",
                    "error": str(e),
                }
            if self.persistence_mode == "STRICT_DB":
                return result

        # File path (file-primary mode, or a legacy file-only HYBRID session).
        sessions, readable = self._load_sessions_file_checked()
        if not readable:
            return {
                "readable": False,
                "found": False,
                "metadata": {},
                "revision": "",
                "error": "sessions file unreadable",
            }
        for session in sessions:
            if session.get("session_id") == session_id:
                metadata = dict(session.get("metadata") or {})
                result.update({
                    "found": True,
                    "metadata": metadata,
                    "revision": str(
                        metadata.get(_METADATA_REVISION_KEY) or ""),
                })
                return result
        return result

    @staticmethod
    def _expected_scalar_matches(actual: Any, wanted: Any) -> bool:
        """Exact JSON-scalar equality for one CAS precondition.

        Typed, never SQL-text-coerced: ``True`` is not ``1``, ``1`` is not
        ``"1"``, and ``None`` matches only a missing key or JSON ``null``
        (not an empty string). This is evaluated in Python against the same
        snapshot used to build the merged patch, so it behaves identically on
        SQLite and PostgreSQL.
        """
        if wanted is None:
            return actual is _MISSING or actual is None
        if isinstance(wanted, bool):
            return isinstance(actual, bool) and actual is wanted
        if isinstance(wanted, int) and not isinstance(wanted, bool):
            return (isinstance(actual, int) and not isinstance(actual, bool)
                    and actual == wanted)
        if isinstance(wanted, float):
            return (isinstance(actual, float) and math.isfinite(wanted)
                    and actual == wanted)
        if isinstance(wanted, str):
            return isinstance(actual, str) and actual == wanted
        return False

    @classmethod
    def _expected_matches(
        cls, metadata: Dict[str, Any], expected: Dict[str, Any]
    ) -> bool:
        for key, wanted in expected.items():
            if not isinstance(key, str):
                return False
            if not cls._expected_scalar_matches(
                    metadata.get(key, _MISSING), wanted):
                return False
        return True

    @staticmethod
    def _valid_expected(expected: Optional[Dict[str, Any]]) -> bool:
        """The honest CAS contract: JSON scalars only, finite floats."""
        if expected is None:
            return True
        if not isinstance(expected, dict):
            return False
        for key, value in expected.items():
            if not isinstance(key, str):
                return False
            if isinstance(value, (dict, list, tuple, set, bytes)):
                return False
            if isinstance(value, float) and not math.isfinite(value):
                return False
            if value is not None and not isinstance(
                    value, (str, int, float, bool)):
                return False
        return True

    @staticmethod
    def _read_snapshot_from_db(db, session_id: str):
        """Read parsed metadata plus the exact stored JSON representation.

        Returns ``(status, metadata, raw_snapshot)``:

        * ``raw_snapshot is None``  -> SQL NULL;
        * ``raw_snapshot == "null"`` -> a JSON literal null;
        * otherwise the stored JSON text/canonical JSONB text.

        The raw representation is what the conditional UPDATE compares, so a
        compact/pretty/escaped/numeric-key-order-preserving raw SQL value is
        handled exactly without guessing how SQLAlchemy would re-serialize the
        Python dict. A JSON literal null and SQL NULL are distinct even though
        the ORM decodes both to Python ``None``.
        """
        try:
            row = db.execute(
                text(
                    "SELECT CAST(metadata_json AS TEXT) FROM "
                    f"{ChatSession.__tablename__} WHERE id = :session_id"
                ),
                {"session_id": session_id},
            ).first()
            if row is None:
                return "missing", {}, None
            raw_snapshot = row[0]
            if raw_snapshot is None:
                # SQL NULL: distinct from a JSON literal null below.
                return "found", {}, None
            try:
                parsed = json.loads(raw_snapshot)
            except Exception:  # noqa: BLE001 — invalid stored JSON
                logger.warning(
                    "session %s metadata is not valid JSON", session_id)
                return "error", {}, None
            if parsed is None:
                # JSON literal null: the raw text (e.g. "null") is the guard.
                current: Dict[str, Any] = {}
            elif isinstance(parsed, dict):
                current = dict(parsed)
            else:
                # Session metadata is a JSON object contract.
                logger.warning(
                    "session %s metadata is not a JSON object", session_id)
                return "error", {}, None
            return "found", current, raw_snapshot
        except Exception as e:  # noqa: BLE001 — report unreadable
            logger.warning(
                f"DB metadata read failed for {session_id}: {e}")
            return "error", {}, None

    def _read_metadata_snapshot(self, session_id: str):
        """Read one committed metadata snapshot, then end the read txn."""
        try:
            with get_db_session() as db:
                return self._read_snapshot_from_db(db, session_id)
        except Exception as e:  # noqa: BLE001 — report unreadable
            logger.warning(
                f"DB metadata read failed for {session_id}: {e}")
            return "error", {}, None

    @staticmethod
    def _metadata_update_statement(
        session_id: str,
        raw_snapshot: Optional[str],
        merged: Dict[str, Any],
    ):
        """Whole-snapshot conditional UPDATE (optimistic CAS).

        The WHERE binds the ENTIRE exact stored snapshot, not one key and not
        a re-serialized Python dict:

        * SQL NULL        -> ``metadata_json IS NULL``;
        * JSON literal null -> ``CAST(metadata_json AS TEXT) = 'null'``;
        * JSON object     -> ``CAST(metadata_json AS TEXT) = <exact text>``.

        On SQLite ``CAST(... AS TEXT)`` returns the bytes-as-text exactly as
        stored (compact, pretty, escaped unicode, `1.50`, key order). On
        PostgreSQL JSONB the cast is the canonical JSONB text and JSONB
        equality semantics remain in force. Any concurrent commit changes the
        stored representation (or the JSONB value), so the condition misses;
        the caller re-reads and re-merges. There is no OR-widening and no
        single-key guard that could overwrite a concurrent change.
        """
        conditions = [ChatSession.id == session_id]
        if raw_snapshot is None:
            conditions.append(ChatSession.metadata_json.is_(None))
        else:
            conditions.append(
                cast(ChatSession.metadata_json, String) == raw_snapshot)
        return update(ChatSession).where(
            *conditions,
        ).values(
            metadata_json=merged,
            updated_at=datetime.now(timezone.utc),
        ).execution_options(synchronize_session=False)

    def _conditional_metadata_update(
        self,
        session_id: str,
        current: Dict[str, Any],
        raw_snapshot: Optional[str],
        merged: Dict[str, Any],
    ) -> str:
        """Execute one CAS attempt. Returns saved|conflict|error.

        ``current`` is carried for diagnostics/test interleaving; the SQL
        guard uses ``raw_snapshot``.
        """
        from sqlalchemy.exc import OperationalError

        try:
            with get_db_session() as db:
                statement = self._metadata_update_statement(
                    session_id, raw_snapshot, merged)
                db.expire_all()
                written = db.execute(statement)
                db.expire_all()
                db.commit()
                return (
                    "saved" if int(written.rowcount or 0) == 1
                    else "conflict")
        except OperationalError as e:  # SQLite busy / peer commit contention
            logger.debug("metadata CAS contention: %s", e)
            return "conflict"
        except Exception as e:  # noqa: BLE001 — truthful failure
            logger.warning(f"DB metadata update failed: {e}")
            return "error"

    @classmethod
    def merge_in_session(
        cls,
        db,
        session_id: str,
        metadata: Dict[str, Any],
        *,
        expected: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> bool:
        """CAS-merge metadata using a caller-owned SQLAlchemy session.

        Shared API for an existing direct ORM metadata writer (currently
        ``AgentContextResolver.set_session_agent``). It never reads/copies the
        metadata and re-assigns the whole dict; it reads the exact stored
        snapshot, applies only the caller's patch, and writes it back behind
        the same whole-snapshot guard. A concurrent commit therefore makes
        this return False instead of clobbering the other writer.

        The caller owns the session/transaction. On write/commit failure the
        helper rolls back and returns False; it never falls back to the file
        store (this path is for a caller that has a ChatSession row).
        """
        if not session_id or not isinstance(metadata, dict):
            return False
        if not cls._valid_expected(expected):
            logger.error(
                "refusing unsupported in-session metadata CAS for %s",
                session_id)
            return False
        try:
            status, current, raw_snapshot = cls._read_snapshot_from_db(
                db, session_id)
            if status != "found":
                return False
            if expected and not cls._expected_matches(current, expected):
                return False
            merged = dict(current)
            merged.update(metadata)
            merged[_METADATA_REVISION_KEY] = uuid.uuid4().hex
            statement = cls._metadata_update_statement(
                session_id, raw_snapshot, merged)
            written = db.execute(
                statement.execution_options(synchronize_session=False))
            if int(written.rowcount or 0) != 1:
                # A newer snapshot won; do not retry with stale local state.
                return False
            if commit:
                db.commit()
            return True
        except Exception as e:  # noqa: BLE001 — truthful failure
            logger.warning("in-session metadata CAS failed: %s", e)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
            return False

    def _db_metadata_cas(
        self,
        session_id: str,
        metadata: Dict[str, Any],
        expected: Optional[Dict[str, Any]],
    ):
        """Bounded read/check/merge/CAS loop. Returns (status, merged)."""
        for attempt in range(_METADATA_CAS_ATTEMPTS):
            status, current, raw_snapshot = self._read_metadata_snapshot(
                session_id)
            if status != "found":
                return status, None
            if expected and not self._expected_matches(current, expected):
                # A stale precondition loses; no blind overwrite.
                return "refused", None
            merged = dict(current)
            merged.update(metadata)
            # Reserved internal token: the caller cannot pin/spoof it. It is
            # diagnostic only; correctness rests on the snapshot equality.
            merged[_METADATA_REVISION_KEY] = uuid.uuid4().hex
            result = self._conditional_metadata_update(
                session_id, current, raw_snapshot, merged)
            if result == "saved":
                return "saved", merged
            if result == "error":
                return "error", None
            time.sleep(min(
                0.05, _METADATA_CAS_RETRY_SLEEP * (attempt + 1)))
        return "conflict", None

    def _file_metadata_cas(
        self,
        session_id: str,
        metadata: Dict[str, Any],
        expected: Optional[Dict[str, Any]],
    ) -> bool:
        """File-mode patch under the cross-process lock.

        The lock is held across read → expected check → merge → atomic
        replace, so two cold processes cannot both satisfy one saved revision
        or lose each other's unrelated keys.
        """
        with _interprocess_file_lock(
                self.sessions_file + ".lock") as acquired:
            if not acquired:
                return False
            sessions, readable = self._load_sessions_file_checked()
            if not readable:
                return False
            for row in sessions:
                if row.get("session_id") != session_id:
                    continue
                current = dict(row.get("metadata") or {})
                if expected and not self._expected_matches(
                        current, expected):
                    return False
                merged = dict(current)
                merged.update(metadata)
                merged[_METADATA_REVISION_KEY] = uuid.uuid4().hex
                row["metadata"] = merged
                row["last_active"] = datetime.now(
                    timezone.utc).isoformat()
                return self._save_sessions_file(sessions, locked=True)
            return False

    def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any],
        *,
        expected: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Atomically merge a JSON patch into durable session metadata.

        The patch is a shallow JSON-object merge (old 2-arg behavior): keys in
        ``metadata`` replace the current value, and a value of ``None`` is
        written as JSON ``null`` — it is NOT dropped as RFC 7386 JSON Merge
        Patch would. Unrelated committed keys are preserved.

        ``expected`` is an optional compare-and-swap precondition. Values are
        matched with exact JSON-scalar typing in Python:
        ``str``/``int``/``float``/``bool``/``None``; ``None`` matches a missing
        key or JSON ``null``. Composite values and non-finite floats are
        refused. The check is re-evaluated on every retry, so a stale
        precondition loses instead of overwriting a newer value.

        DB mode reads a snapshot, releases the read transaction, then commits
        the merged snapshot with ``UPDATE ... WHERE metadata_json = <snapshot>``.
        A concurrent commit makes the WHERE miss; the writer re-reads and
        re-merges (bounded retries). PostgreSQL READ COMMITTED re-evaluates the
        conditional UPDATE against the committed row; SQLite serializes writers
        and returns no row for the stale snapshot. File mode holds a stable
        sibling ``.lock`` via ``flock``/``msvcrt`` across the same window.

        Returns True only when the authoritative store confirmed the commit.
        A failed commit/lock/read (or an exhausted CAS loop) returns False and
        leaves the caller's in-memory state to make its own truthful decision.
        """
        if not session_id or not isinstance(metadata, dict):
            return False
        if not self._valid_expected(expected):
            logger.error(
                "refusing unsupported metadata CAS expectation for %s",
                session_id)
            return False

        if self.use_db:
            status, merged = self._db_metadata_cas(
                session_id, metadata, expected)
            if status == "saved":
                if (self.persistence_mode != "STRICT_DB"
                        and merged is not None):
                    self._mirror_metadata_to_file(session_id, merged)
                return True
            if status != "missing":
                return False
            if self.persistence_mode == "STRICT_DB":
                return False
            # Clean no-row in HYBRID: a legacy file-only session may exist.

        return self._file_metadata_cas(session_id, metadata, expected)

    def _mirror_metadata_to_file(
        self, session_id: str, metadata: Dict[str, Any]
    ) -> None:
        """Best-effort HYBRID mirror; the DB already committed the authority.

        The DB snapshot is authoritative, so the mirror writes that complete
        snapshot (including the internal revision token) under the same
        cross-process lock. A mirror failure cannot turn a committed DB write
        into a reported failure.
        """
        try:
            with _interprocess_file_lock(
                    self.sessions_file + ".lock") as acquired:
                if not acquired:
                    return
                sessions, readable = self._load_sessions_file_checked()
                if not readable:
                    return
                for row in sessions:
                    if row.get("session_id") != session_id:
                        continue
                    row["metadata"] = dict(metadata)
                    row["last_active"] = datetime.now(
                        timezone.utc).isoformat()
                    self._save_sessions_file(sessions, locked=True)
                    return
        except Exception as e:  # noqa: BLE001 — mirror is not authority
            logger.debug(f"metadata mirror skipped for {session_id}: {e}")

    def update_session_activity(self, session_id: str, history: List[Dict] = None, last_message: str = None):
        """Update session's last_active timestamp and history"""
        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
                try:
                    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                    if session:
                        session.updated_at = datetime.now(timezone.utc)
                        if history is not None:
                            session.message_count = len(history)
                            # Ideally, messages are stored in ChatMessage table separately.
                            # This manager focuses on the Session Metadata.
                        db.commit()
                        return # Success
                except Exception as e:
                    if self.persistence_mode == "STRICT_DB":
                        logger.error(f"DB Update Session failed in STRICT_DB mode: {e}")
                        raise RuntimeError(f"Database update failed in STRICT_DB mode: {e}")
                    logger.error(f"DB Update Session failed: {e}")
                finally:
                    db.close()
                db.close()
        
        if self.persistence_mode == "STRICT_DB":
            return # Do not fall back to file implementation

        # 2. File Path
        with _interprocess_file_lock(
                self.sessions_file + ".lock") as acquired:
            if not acquired:
                logger.error(
                    "session activity not persisted for %s: file lock "
                    "unavailable", session_id)
                return
            sessions = self._load_sessions_file()
            updated = False
            for session in sessions:
                if session['session_id'] == session_id:
                    session['last_active'] = datetime.now(
                        timezone.utc).isoformat()
                    if history is not None:
                        session['history'] = history
                        session['message_count'] = len(history)
                    if last_message:
                        session['last_message'] = last_message
                    updated = True
                    break

            if not updated:
                 # Auto-recover for file mode
                 new_session = {
                    "session_id": session_id,
                    "user_id": "default",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_active": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "recovered"},
                    "message_count": len(history) if history else 0,
                    "history": history or []
                }
                 sessions.append(new_session)

            self._save_sessions_file(sessions, locked=True)
    
    def list_user_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List all sessions for a user (most recent first)"""
        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
                try:
                    # Query DB
                    sessions = db.query(ChatSession)\
                                 .filter(ChatSession.user_id == user_id)\
                                 .order_by(desc(ChatSession.updated_at))\
                                 .limit(limit)\
                                 .all()

                    # Convert DB sessions to dicts
                    results = [{
                        "session_id": s.id,
                        "user_id": s.user_id,
                        "title": s.title,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "last_active": s.updated_at.isoformat() if s.updated_at else None,
                        "metadata": s.metadata_json or {},
                        "message_count": s.message_count,
                        "history": [] # Lightweight list
                    } for s in sessions]

                    # STRICT_DB: Return only DB results
                    if self.persistence_mode == "STRICT_DB":
                        return results

                    # HYBRID MERGE: Also load from file and append any missing ones
                    # This handles the case where we switched to DB mode but have old file sessions
                    try:
                        file_sessions = self._load_sessions_file()
                        db_ids = {r["session_id"] for r in results}

                        # Filter for this user and not in DB
                        legacy_sessions = [
                            s for s in file_sessions
                            if s.get("user_id") == user_id and s.get("session_id") not in db_ids
                        ]

                        # Sort legacy sessions
                        legacy_sessions.sort(key=lambda x: x.get('last_active', ''), reverse=True)

                        # Append (respecting limit if needed, though we might go over)
                        results.extend(legacy_sessions)

                        # Re-sort combined results
                        results.sort(key=lambda x: x.get('last_active', '') or '', reverse=True)

                        return results[:limit]

                    except Exception as e:
                        logger.warning(f"Hybrid merge failed: {e}")
                        return results # Return at least DB results
                except Exception as e:
                    logger.error(f"DB List Sessions failed: {e}")

        # 2. File Path
        sessions = self._load_sessions_file()
        user_sessions = [s for s in sessions if s.get('user_id') == user_id]
        user_sessions.sort(key=lambda x: x.get('last_active', ''), reverse=True)
        return user_sessions[:limit]
    
    def rebind_session_owner(self, session_id: str, new_user_id: str) -> bool:
        """Durably re-point a legacy session at its reclaiming user.

        Updates BOTH persistence stores — the DB row (if present) and the
        startup JSON file — so the rebind survives a restart. The orchestrator
        reloads sessions from the file at boot, so a memory-only (or DB-only)
        rebind would revert the session to placeholder ownership and make it
        claimable by a different caller again (Greptile review of PR #582).
        Returns True if the new owner was durably recorded in at least one
        store.
        """
        db_updated = False
        file_updated = False

        # 1. Database row (if the session lives in the DB).
        if self.use_db:
            try:
                with get_db_session() as db:
                    row = db.query(ChatSession).filter(
                        ChatSession.id == session_id
                    ).first()
                    if row is not None:
                        row.user_id = str(new_user_id)
                        db.commit()
                        db_updated = True
            except Exception as e:
                logger.warning(f"DB rebind failed for session {session_id}: {e}")

        # 2. JSON file record (the store the orchestrator reloads at startup).
        try:
            with _interprocess_file_lock(
                    self.sessions_file + ".lock") as acquired:
                if not acquired:
                    logger.warning(
                        "File rebind skipped for %s: lock unavailable",
                        session_id)
                    return db_updated
                sessions = self._load_sessions_file()
                for s in sessions:
                    if s.get("session_id") == session_id:
                        s["user_id"] = str(new_user_id)
                        file_updated = self._save_sessions_file(
                            sessions, locked=True)
                        break
        except Exception as e:
            logger.warning(f"File rebind failed for session {session_id}: {e}")

        return db_updated or file_updated

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        deleted = False
        
        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
                try:
                    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                    if session:
                        db.delete(session)
                        db.commit()
                        deleted = True
                except Exception as e:
                    logger.error(f"DB Delete Session failed: {e}")
                finally:
                    db.close()
                
        # 2. File Path (Always try to clean up file too, just in case)
        with _interprocess_file_lock(
                self.sessions_file + ".lock") as acquired:
            if not acquired:
                logger.error(
                    "File delete skipped for %s: lock unavailable",
                    session_id)
                return deleted
            sessions = self._load_sessions_file()
            initial_count = len(sessions)
            sessions = [s for s in sessions if s['session_id'] != session_id]
            if len(sessions) < initial_count:
                deleted = self._save_sessions_file(
                    sessions, locked=True) or deleted

        return deleted

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Rename a session"""
        
        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
                try:
                    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                    if session:
                        session.title = new_title
                        session.updated_at = datetime.now(timezone.utc)
                        db.commit()
                        # We continue to file sync for hybrid safety if desired,
                        # but usually for true hybrid we just rely on DB if active.
                        # For now, let's keep them in sync if file exists.
                except Exception as e:
                    logger.error(f"DB Rename Session failed: {e}")
                    return False
                finally:
                    db.close()

        # 2. File Path (Always try to sync file for consistency in hybrid mode)
        with _interprocess_file_lock(
                self.sessions_file + ".lock") as acquired:
            if not acquired:
                logger.error(
                    "File rename skipped for %s: lock unavailable", session_id)
                return self.use_db
            sessions = self._load_sessions_file()
            updated = False
            for session in sessions:
                if session['session_id'] == session_id:
                    session['title'] = new_title
                    session['last_active'] = datetime.now(
                        timezone.utc).isoformat()
                    updated = True
                    break

            if updated:
                self._save_sessions_file(sessions, locked=True)

        return updated or self.use_db # Return true if either DB or File updated successfully


# Global instance
chat_session_manager = ChatSessionManager()

def get_chat_session_manager(workspace_id: str = "default") -> ChatSessionManager:
    """Get workspace-aware chat session manager instance"""
    return ChatSessionManager(workspace_id=workspace_id)
