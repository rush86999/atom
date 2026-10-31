import json
from pathlib import Path
from playwright.sync_api import sync_playwright

WORLD = Path('/Users/rushiparikh/projects/atom-conversation-context-world')
FRONTEND = 'http://127.0.0.1:3130'
PASSWORD = 'journey-pass'
BEFORE = WORLD / 'chat-context-restart-part1.json'
OUT = WORLD / 'chat-context-restart-part2.json'

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
        "() => document.body.innerText.includes('Before I can apply the taught method')",
        timeout=60000)
    page.get_by_test_id('agent-chat-input').fill('licensed')
    with page.expect_response(
            lambda r: '/api/chat/message' in r.url, timeout=60000) as info:
        page.get_by_test_id('send-message-button').click()
    response = info.value.json()
    page.wait_for_function(
        "() => document.body.innerText.includes('Using the taught method from lesson')",
        timeout=60000)
    execution = (response.get('metadata') or {}).get(
        'teaching_execution') or {}
    assert response.get('outcome') == 'completed', response
    assert execution.get('lesson_id'), response
    assert execution.get('lesson_revision') == 1, response
    assert execution.get('operation') == 'multiply_sum', response
    assert execution.get('operands', {}).get('quantity', {}).get('value') == '2', response
    assert execution.get('operands', {}).get('unit_price', {}).get('value') == '7.50', response
    assert execution.get('value') == '15', response
    assert '1.75' not in response.get('message', ''), response

    token = page.evaluate(
        "() => localStorage.getItem('auth_token') || localStorage.getItem('token')")
    page.reload(wait_until='domcontentloaded')
    page.get_by_test_id('message-list').wait_for(timeout=60000)
    page.wait_for_function(
        "() => document.body.innerText.includes('Using the taught method from lesson')",
        timeout=60000)
    history = page.evaluate(
        "async ({sid, t}) => (await fetch('/api/chat/history/' + sid + '?user_id=admin', {headers: {Authorization: 'Bearer ' + t}})).json()",
        {'sid': session_id, 't': token})
    assistant = [m for m in history.get('messages', [])
                 if m.get('role') == 'assistant']
    last = assistant[-1].get('response') or {}
    assert last.get('outcome') == 'completed', last
    assert 'Using the taught method from lesson' in last.get('message', ''), last
    OUT.write_text(json.dumps({
        'session_id': session_id,
        'restart_clarification': before['clarification'],
        'answer': {
            'message': response.get('message'),
            'outcome': response.get('outcome'),
            'model': response.get('model'),
            'teaching_execution': execution,
        },
        'history_last_outcome': last.get('outcome'),
        'page_errors': errors,
    }, indent=2))
    page.screenshot(path=str(WORLD / 'chat-context-restart-result.png'),
                    full_page=True)
    browser.close()

print(OUT.read_text())
