import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

WORLD = Path('/Users/rushiparikh/projects/atom-conversation-context-world')
FRONTEND = 'http://127.0.0.1:3130'
PASSWORD = 'journey-pass'
OUT = WORLD / 'chat-context-journey-full.json'
LESSON_TEXT = f'Use the Customer-A licensed rates method (browser {int(time.time())}).'

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    )
    page = browser.new_page(viewport={'width': 1440, 'height': 1200})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    page.goto(f'{FRONTEND}/login', wait_until='domcontentloaded')
    page.get_by_test_id('login-email-input').fill('admin@example.com')
    page.get_by_test_id('login-password-input').fill(PASSWORD)
    page.get_by_test_id('login-submit-button').click()
    page.wait_for_url('**/dashboard', timeout=90000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed','1')")

    # 1. Teach/promote the scoped method through /learning.
    page.goto(f'{FRONTEND}/learning', wait_until='domcontentloaded')
    page.get_by_test_id('learning-thread-select').wait_for(timeout=60000)
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('[data-testid=learning-thread-select] option')).some(o => o.value === 'thread-learn')",
        timeout=60000)
    page.get_by_test_id('learning-thread-select').select_option(value='thread-learn')
    page.get_by_test_id('learning-new-draft').wait_for(timeout=60000)
    page.get_by_test_id('learning-new-draft').click()
    page.get_by_test_id('learning-draft-form').wait_for(timeout=60000)
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('[data-testid=learning-employee-select] option')).some(o => o.value === 'agent-browser-final')",
        timeout=60000)
    page.get_by_test_id('learning-employee-select').select_option(value='agent-browser-final')
    page.get_by_test_id('learning-lesson-input').fill(LESSON_TEXT)
    page.get_by_test_id('learning-operation-select').select_option(value='multiply_sum')
    page.get_by_test_id('learning-concept-1').fill('quantity')
    page.get_by_test_id('learning-column-1').fill('Qty')
    page.get_by_test_id('learning-unit-1').fill('units')
    page.get_by_test_id('learning-concept-2').fill('unit_price')
    page.get_by_test_id('learning-column-2').fill('Price')
    page.get_by_test_id('learning-unit-2').fill('USD')
    page.get_by_test_id('learning-customer-input').fill('Customer-A')
    page.get_by_test_id('learning-qualification-input').fill('licensed')
    page.get_by_test_id('learning-draft-button').click()
    page.get_by_test_id('learning-proposed-lesson').wait_for(timeout=60000)
    page.get_by_test_id('learning-confirm').click()
    page.get_by_test_id('learning-promote').wait_for(timeout=60000)
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=learning-promote]').disabled",
        timeout=60000)
    page.get_by_test_id('learning-promote').click()
    page.wait_for_timeout(1500)

    token = page.evaluate(
        "() => localStorage.getItem('auth_token') || localStorage.getItem('token')")
    candidates = page.evaluate(
        "async (t) => (await fetch('/api/conversation-learning/threads/thread-learn/candidates', {headers:{Authorization:'Bearer '+t}})).json()",
        token)
    match = next(
        item for item in candidates['candidates']
        if LESSON_TEXT in str(item.get('candidate', {}).get('proposed_lesson') or '')
    )
    candidate = match['candidate']
    lesson_id = candidate['promoted_entry_id']
    candidate_id = candidate['candidate_id']
    assert lesson_id, candidate
    page.screenshot(path=str(WORLD / 'chat-context-promoted.png'), full_page=True)

    # 2. Add a general lesson through the normal /teach interface.
    page.evaluate("localStorage.removeItem('atom_chat_session_id')")
    page.goto(f'{FRONTEND}/chat?agent_id=agent-browser-final', wait_until='domcontentloaded')
    page.get_by_test_id('agent-chat-input').wait_for(timeout=60000)
    page.get_by_test_id('chat-agent-identity').wait_for(timeout=60000)
    page.get_by_test_id('agent-chat-input').fill(
        '/teach Always cite the source workbook.')
    page.get_by_test_id('send-message-button').click()
    page.wait_for_selector(
        '[data-testid="teaching-saved"], [data-testid="teaching-duplicate"]',
        timeout=60000)
    general_notice = page.locator(
        '[data-testid="teaching-saved"], [data-testid="teaching-duplicate"]'
    ).first.inner_text()

    # 3. Ask an unfamiliar calculation WITHOUT qualification. The request
    # itself names Customer-A; only qualification should be requested.
    page.get_by_test_id('agent-chat-input').fill(
        'Use the pricing method for the Customer-A order with Qty 2 and Price 7.50.')
    with page.expect_response(
            lambda r: '/api/chat/message' in r.url, timeout=60000) as clarify_info:
        page.get_by_test_id('send-message-button').click()
    clarify = clarify_info.value.json()
    page.wait_for_function(
        "() => document.body.innerText.includes('Before I can apply the taught method')",
        timeout=60000)
    clarify_text = page.locator('[data-testid="message-list"]').inner_text()
    session_id = page.evaluate(
        "() => localStorage.getItem('atom_chat_session_id')")
    clarify_meta = (clarify.get('metadata') or {}).get(
        'teaching_clarification') or {}
    required = clarify_meta.get('required_context') or []
    refs = [item.get('id') for item in (clarify_meta.get('lesson_refs') or [])]
    assert clarify.get('outcome') == 'partial', clarify
    assert [row.get('key') for row in required] == ['qualification'], required
    assert lesson_id in refs, refs
    assert 'Always cite the source workbook.' in (clarify.get('memory_context') or '')
    assert '1.75' not in clarify.get('message', '')

    # 4. Answer the visible clarification in the same conversation.
    page.get_by_test_id('agent-chat-input').fill('licensed')
    with page.expect_response(
            lambda r: '/api/chat/message' in r.url, timeout=60000) as answer_info:
        page.get_by_test_id('send-message-button').click()
    answer = answer_info.value.json()
    page.wait_for_function(
        "() => document.body.innerText.includes('Using the taught method from lesson')",
        timeout=60000)
    result_text = page.locator('[data-testid="message-list"]').inner_text()
    execution = (answer.get('metadata') or {}).get('teaching_execution') or {}
    assert answer.get('outcome') == 'completed', answer
    assert execution.get('lesson_id') == lesson_id, execution
    assert execution.get('lesson_revision') == 1, execution
    assert execution.get('operation') == 'multiply_sum', execution
    assert execution.get('operands', {}).get('quantity', {}).get('value') == '2', execution
    assert execution.get('operands', {}).get('unit_price', {}).get('value') == '7.50', execution
    assert execution.get('value') == '15', execution
    assert execution.get('unit') == 'USD', execution
    assert '1.75' not in answer.get('message', ''), answer
    assert f'lesson {lesson_id} rev 1' in answer.get('message', ''), answer
    assert 'Always cite the source workbook.' in (answer.get('memory_context') or '')
    page.screenshot(path=str(WORLD / 'chat-context-result.png'), full_page=True)

    # 5. Refresh: history and outcome must agree.
    page.reload(wait_until='domcontentloaded')
    page.get_by_test_id('message-list').wait_for(timeout=60000)
    page.wait_for_function(
        "() => document.body.innerText.includes('Using the taught method from lesson')",
        timeout=60000)
    refreshed_text = page.locator('[data-testid="message-list"]').inner_text()
    history = page.evaluate(
        "async ({sid, t}) => (await fetch('/api/chat/history/' + sid + '?user_id=admin', {headers: {Authorization: 'Bearer ' + t}})).json()",
        {'sid': session_id, 't': token})
    assistant = [m for m in history.get('messages', [])
                 if m.get('role') == 'assistant']
    assert assistant, history
    last = assistant[-1].get('response') or {}
    assert last.get('outcome') == 'completed', last
    assert f'lesson {lesson_id} rev 1' in last.get('message', ''), last

    OUT.write_text(json.dumps({
        'session_id': session_id,
        'promoted_lesson_id': lesson_id,
        'candidate_id': candidate_id,
        'general_lesson_notice': general_notice,
        'clarification': {
            'message': clarify.get('message'),
            'outcome': clarify.get('outcome'),
            'required_context': required,
            'lesson_refs': clarify_meta.get('lesson_refs'),
            'memory_has_general': 'Always cite the source workbook.' in (
                clarify.get('memory_context') or ''),
        },
        'answer': {
            'message': answer.get('message'),
            'outcome': answer.get('outcome'),
            'model': answer.get('model'),
            'teaching_execution': execution,
            'memory_has_general': 'Always cite the source workbook.' in (
                answer.get('memory_context') or ''),
        },
        'clarify_visible': 'qualification' in clarify_text,
        'result_visible': 'Using the taught method from lesson' in result_text,
        'refreshed_visible': 'Using the taught method from lesson' in refreshed_text,
        'history_last_outcome': last.get('outcome'),
        'page_errors': errors,
    }, indent=2))
    browser.close()

print(OUT.read_text())
