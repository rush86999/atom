import json
from pathlib import Path
from playwright.sync_api import sync_playwright

WORLD = Path('/Users/rushiparikh/projects/atom-conversation-context-world')
FRONTEND = 'http://127.0.0.1:3130'
PASSWORD = 'journey-pass'
OUT = WORLD / 'chat-operand-restart-part1.json'


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
    page.evaluate("localStorage.removeItem('atom_chat_session_id')")
    page.goto(f'{FRONTEND}/chat?agent_id=agent-browser-final',
              wait_until='domcontentloaded')
    page.get_by_test_id('agent-chat-input').wait_for(timeout=60000)
    page.get_by_test_id('agent-chat-input').fill(
        'Use the pricing method for the Customer-A licensed order '
        'with Qty 2 and Price 7.50 or Price 8.00.')
    page.wait_for_function(
        "() => { const b = document.querySelector('[data-testid=send-message-button]'); return b && !b.disabled; }",
        timeout=60000)
    with page.expect_response(
            lambda r: '/api/chat/message' in r.url, timeout=60000) as info:
        page.get_by_test_id('send-message-button').click()
    response = info.value.json()
    page.wait_for_function(
        "() => document.body.innerText.includes('more than one value for Price')",
        timeout=60000)
    session_id = page.evaluate(
        "() => localStorage.getItem('atom_chat_session_id')")
    assert response.get('outcome') == 'partial', response
    assert (response.get('metadata') or {}).get(
        'teaching_operand_clarification'), response
    OUT.write_text(json.dumps({
        'session_id': session_id,
        'clarification': response.get('message'),
        'metadata': response.get('metadata'),
        'page_errors': errors,
    }, indent=2))
    page.screenshot(path=str(WORLD / 'chat-operand-restart-pending.png'),
                    full_page=True)
    browser.close()

print(OUT.read_text())
