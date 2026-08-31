"""
E2E user journey: fork an agent chat conversation at a specific message.

"Sometimes you want to take a conversation in a different direction without
wrecking the thread you already have." The journey:

1. User opens a chat with an existing multi-turn history.
2. Hovers an earlier assistant reply and clicks "Fork from here".
3. Lands in a brand-new session containing everything up to and including
   that reply — later turns are gone from the fork, intact in the original.
4. The fork survives a page refresh.

The conversation is seeded directly as durable SQL rows (the store the chat
page reads) so the journey exercises the fork mechanics, not LLM latency.

Run with: pytest backend/tests/e2e_ui/tests/test_journey_chat_fork.py -v

Preconditions (see JOURNEY_TESTS.md): backend on :8001, frontend on :3001,
DATABASE_URL matching the backend DB.
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest  # noqa: F401  (fixtures resolve via conftest)
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import ChatPage
from tests.e2e_ui.tests.test_agent_chat import (
    create_authenticated_page,
    create_test_user,
)
from core.models import ChatMessage as ChatMessageModel
from core.models import ChatSession as ChatSessionModel


def _seed_conversation(db_session: Session, session_id: str, user_id: str, marker: str):
    """Seed a ChatSession + 2 exchanges (4 rows); returns message ids in order."""
    db_session.add(ChatSessionModel(
        id=session_id,
        user_id=user_id,
        title=f"Journey Chat {marker}",
        message_count=4,
    ))
    base = datetime.now(timezone.utc)
    ids = []
    for i, (role, content) in enumerate([
        ("user", f"first question {marker}"),
        ("assistant", f"first answer {marker}"),
        ("user", f"second question {marker}"),
        ("assistant", f"second answer {marker}"),
    ]):
        mid = f"{session_id}-msg-{i}"
        ids.append(mid)
        db_session.add(ChatMessageModel(
            id=mid,
            conversation_id=session_id,
            tenant_id="default",
            role=role,
            content=content,
            created_at=base.replace(microsecond=i * 1000),
        ))
    db_session.commit()
    return ids


def test_fork_from_message_journey(browser, db_session: Session):
    """Fork at the FIRST assistant reply: fork keeps turns 1-2, drops 3-4,
    original keeps everything, and the fork survives a refresh."""
    unique_id = str(uuid.uuid4())[:8]
    email = f"chat_fork_{unique_id}@example.com"
    password = "ChatFork123!"

    user = create_test_user(db_session, email, password)

    session_id = f"sess-journey-fork-{unique_id}"
    marker = f"jfork{unique_id}"
    _seed_conversation(db_session, session_id, user.id, marker)

    page = create_authenticated_page(browser, user, password)
    # Point the chat page at the seeded session (it restores the last-active
    # session id from localStorage on mount).
    page.evaluate(f"() => localStorage.setItem('atom_chat_session_id', '{session_id}')")

    chat_page = ChatPage(page)
    chat_page.navigate()
    page.wait_for_selector('[data-testid="assistant-message"]', timeout=15000)

    # A fresh user can land with a modal open (e.g. onboarding) that
    # intercepts pointer events — dismiss whatever dialog is showing so the
    # message hover can reach its target.
    for _ in range(3):
        dialog = page.locator("#dialog-content")
        if not dialog.count() or not dialog.first.is_visible():
            break
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

    # Journey step: fork from the FIRST assistant reply. The button is
    # hover-revealed on the message's action row.
    first_reply = chat_page.assistant_message.filter(has_text=f"first answer {marker}").first
    first_reply.hover()
    # nth(0): multiple fork buttons exist (one per reply); the first belongs
    # to the earliest assistant message in the list.
    chat_page.fork_message_button.first.click()

    # The fork POST is async — while it's in flight the ORIGINAL session is
    # still rendered (which would also satisfy the content checks below), so
    # first wait for the active-session pointer to move to the fork.
    page.wait_for_function(
        """(sourceSid) => {
            const active = localStorage.getItem('atom_chat_session_id');
            return active && active !== sourceSid;
        }""",
        arg=session_id,
        timeout=20000,
    )

    # The page remounts the chat onto the fork and refetches history, so the
    # list can flash "Loading history..." — poll until the SETTLED list
    # contains the forked-point reply and not the loading state.
    page.wait_for_function(
        """([marker]) => {
            const list = document.querySelector('[data-testid="message-list"]');
            if (!list) return false;
            const text = list.innerText;
            return text.includes(`first answer ${marker}`)
                && !text.includes('Loading history');
        }""",
        arg=[marker],
        timeout=20000,
    )
    all_text = chat_page.message_list.inner_text()
    assert f"first answer {marker}" in all_text, "fork should keep the forked-point reply"
    assert f"second answer {marker}" not in all_text, "fork must drop turns after the fork point"

    # The active session pointer switched to the fork (not the original).
    active_sid = page.evaluate("() => localStorage.getItem('atom_chat_session_id')")
    assert active_sid and active_sid != session_id, (
        f"expected a new fork session id, still pointing at {active_sid}"
    )

    # The fork survives a refresh (durable rows, not just UI state).
    page.reload()
    page.wait_for_selector('[data-testid="assistant-message"]', timeout=15000)
    refreshed_text = ChatPage(page).message_list.inner_text()
    assert f"first answer {marker}" in refreshed_text
    assert f"second answer {marker}" not in refreshed_text

    # The ORIGINAL session is untouched: reopen it directly.
    page.evaluate(f"() => localStorage.setItem('atom_chat_session_id', '{session_id}')")
    page.reload()
    page.wait_for_selector('[data-testid="assistant-message"]', timeout=15000)
    original_text = ChatPage(page).message_list.inner_text()
    assert f"second answer {marker}" in original_text, "original session must keep later turns"
    assert f"first answer {marker}" in original_text
