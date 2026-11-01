import json
from pathlib import Path
from playwright.sync_api import sync_playwright

WORLD = Path('/Users/rushiparikh/projects/atom-conversation-context-world')
FRONTEND = 'http://127.0.0.1:3130'
PASSWORD = 'journey-pass'
BEFORE = WORLD / 'chat-operand-restart-part1.json'
OUT = WORLD / 'chat-operand-restart-part2.json'

before = json.loads(BEFORE.read_text())
session_id = before['session_id']


def login(page):
    page.goto(f'{FRONTEND}/login', wait_until='domcontentloaded')
    page.get_by_test_id('login-email-input').fill('admin@example.com')
    page.get_by_test_id('login-password-input').fill(PASSWORD)
    page.get_by_test_id('login-submit-button').click()
    page.wait_for_url('**/dashboard', timeout=90000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed','1')")


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    )
    page = browser.new_page(viewport={'width': 1440, 'height': 1200})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    login(page)
    page.evaluate(
        "sid => localStorage.setItem('atom_chat_session_id', sid)",
        session_id)
    page.goto(f'{FRONTEND}/chat?agent_id=agent-browser-final',
              wait_until='domcontentloaded')
    page.get_by_test_id('agent-chat-input').wait_for(timeout=60000)
    page.get_by_test_id('message-list').wait_for(timeout=60000)
    page.wait_for_function(
        "() => document.body.innerText.includes('more than one value for Price')",
        timeout=60000)
    page.get_by_test_id('agent-chat-input').fill('8.00')
    page.wait_for_function(
        "() => { const b = document.querySelector('[data-testid=send-message-button]'); return b && !b.disabled; }",
        timeout=60000)
    with page.expect_response(
            lambda r: '/api/chat/message' in r.url, timeout=60000) as info:
        page.get_by_test_id('send-message-button').click()
    response = info.value.json()
    page.wait_for_function(
        "() => document.body.innerText.includes('Calculation receipt from lesson')",
        timeout=60000)
    execution = (response.get('metadata') or {}).get(
        'teaching_execution') or {}
    receipt = execution.get('calculation_receipt') or {}
    assert response.get('outcome') == 'completed', response
    assert receipt.get('value') == '16', receipt
    assert receipt.get('lesson_ref', {}).get('revision') == 1, receipt
    assert '8.00' in response.get('message', ''), response

    token = page.evaluate(
        "() => localStorage.getItem('auth_token') || localStorage.getItem('token')")
    page.reload(wait_until='domcontentloaded')
    page.get_by_test_id('message-list').wait_for(timeout=60000)
    page.wait_for_function(
        "() => document.body.innerText.includes('Calculation receipt from lesson')",
        timeout=60000)
    history = page.evaluate(
        "async ({sid, t}) => (await fetch('/api/chat/history/' + sid + '?user_id=admin', {headers: {Authorization: 'Bearer ' + t}})).json()",
        {'sid': session_id, 't': token})
    assistant = [m for m in history.get('messages', [])
                 if m.get('role') == 'assistant']
    last = assistant[-1].get('response') or {}
    assert last.get('outcome') == 'completed', last
    assert 'Calculation receipt from lesson' in last.get('message', ''), last
    OUT.write_text(json.dumps({
        'session_id': session_id,
        'restart_clarification': before.get('clarification'),
        'answer_outcome': response.get('outcome'),
        'answer_message': response.get('message'),
        'receipt': receipt,
        'history_last_outcome': last.get('outcome'),
        'page_errors': errors,
    }, indent=2))
    page.screenshot(path=str(WORLD / 'chat-operand-restart-result.png'),
                    full_page=True)
    browser.close()

print(OUT.read_text())
