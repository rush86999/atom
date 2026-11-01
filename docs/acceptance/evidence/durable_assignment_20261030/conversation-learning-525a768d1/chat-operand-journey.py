import json
from pathlib import Path
from playwright.sync_api import sync_playwright

WORLD = Path('/Users/rushiparikh/projects/atom-conversation-context-world')
FRONTEND = 'http://127.0.0.1:3130'
PASSWORD = 'journey-pass'
OUT = WORLD / 'chat-operand-journey.json'


def login(page):
    page.goto(f'{FRONTEND}/login', wait_until='domcontentloaded')
    page.get_by_test_id('login-email-input').fill('admin@example.com')
    page.get_by_test_id('login-password-input').fill(PASSWORD)
    page.get_by_test_id('login-submit-button').click()
    page.wait_for_url('**/dashboard', timeout=90000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed','1')")


_CASE_COUNTER = {'n': 0}


def new_chat(page):
    _CASE_COUNTER['n'] += 1
    page.evaluate("localStorage.removeItem('atom_chat_session_id')")
    page.goto(
        f'{FRONTEND}/chat?agent_id=agent-browser-final&case={_CASE_COUNTER["n"]}',
        wait_until='load')
    page.get_by_test_id('agent-chat-input').wait_for(timeout=60000)
    page.get_by_test_id('message-list').wait_for(timeout=60000)
    page.get_by_test_id('chat-agent-identity').wait_for(timeout=60000)


def send(page, message, marker, timeout=60000):
    page.get_by_test_id('agent-chat-input').fill(message)
    page.wait_for_function(
        "() => { const b = document.querySelector('[data-testid=send-message-button]'); return b && !b.disabled; }",
        timeout=timeout)
    with page.expect_response(
            lambda r: '/api/chat/message' in r.url,
            timeout=timeout) as info:
        page.get_by_test_id('send-message-button').click()
    response = info.value.json()
    page.wait_for_function(
        "marker => document.body.innerText.includes(marker)",
        arg=marker, timeout=timeout)
    session_id = page.evaluate(
        "() => localStorage.getItem('atom_chat_session_id')")
    return response, session_id


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    )
    page = browser.new_page(viewport={'width': 1440, 'height': 1200})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    login(page)
    out = {'page_errors': errors, 'cases': {}}

    # 1. Valid calculation completes truthfully.
    new_chat(page)
    valid, valid_sid = send(
        page,
        'Use the pricing method for the Customer-A licensed order '
        'with Qty 2 and Price 7.50 USD.',
        'Calculation receipt from lesson')
    valid_exec = (valid.get('metadata') or {}).get('teaching_execution') or {}
    valid_receipt = valid_exec.get('calculation_receipt') or {}
    assert valid.get('outcome') == 'completed', valid
    assert valid_receipt.get('value') == '15', valid_receipt
    assert valid_receipt.get('unit') == 'USD', valid_receipt
    assert '1.75' not in valid.get('message', ''), valid
    out['cases']['valid'] = {
        'session_id': valid_sid,
        'outcome': valid.get('outcome'),
        'message': valid.get('message'),
        'receipt': valid_receipt,
    }

    # 2. Ambiguous price asks; refresh; answer resumes the original task.
    new_chat(page)
    ambiguous, ambiguous_sid = send(
        page,
        'Use the pricing method for the Customer-A licensed order '
        'with Qty 2 and Price 7.50 or Price 8.00.',
        'more than one value for Price')
    assert ambiguous.get('outcome') == 'partial', ambiguous
    operand_meta = (ambiguous.get('metadata') or {}).get(
        'teaching_operand_clarification') or {}
    assert operand_meta.get('kind') == 'operands', operand_meta
    assert 'teaching_execution' not in (ambiguous.get('metadata') or {})
    confirmed, _ = send(page, '8.00', 'Calculation receipt from lesson')
    confirmed_exec = (confirmed.get('metadata') or {}).get(
        'teaching_execution') or {}
    confirmed_receipt = confirmed_exec.get('calculation_receipt') or {}
    assert confirmed.get('outcome') == 'completed', confirmed
    assert confirmed_receipt.get('value') == '16', confirmed_receipt
    assert '8.00' in confirmed.get('message', ''), confirmed
    out['cases']['ambiguous_resume'] = {
        'session_id': ambiguous_sid,
        'clarification': ambiguous.get('message'),
        'clarification_meta': operand_meta,
        'answer_outcome': confirmed.get('outcome'),
        'answer_message': confirmed.get('message'),
        'receipt': confirmed_receipt,
    }

    # 3. Explicit incompatible currency remains blocked, then a compatible
    # answer resumes the original task.
    new_chat(page)
    cad, cad_sid = send(
        page,
        'Use the pricing method for the Customer-A licensed order '
        'with Qty 2 and Price 7.50 CAD.',
        'is in CAD')
    assert cad.get('outcome') == 'partial', cad
    assert 'teaching_execution' not in (cad.get('metadata') or {})
    assert 'CAD' in cad.get('message', ''), cad
    cad_answer, _ = send(page, 'Price 7.50 USD', 'Calculation receipt from lesson')
    cad_exec = (cad_answer.get('metadata') or {}).get(
        'teaching_execution') or {}
    cad_receipt = cad_exec.get('calculation_receipt') or {}
    assert cad_answer.get('outcome') == 'completed', cad_answer
    assert cad_receipt.get('value') == '15', cad_receipt
    assert cad_receipt.get('unit') == 'USD', cad_receipt
    out['cases']['incompatible_unit'] = {
        'session_id': cad_sid,
        'blocked_message': cad.get('message'),
        'answer_outcome': cad_answer.get('outcome'),
        'receipt': cad_receipt,
    }

    # 4. Compound calculation + email request is partial; the email obligation
    # is retained and awaiting approval. No outbound send is performed.
    new_chat(page)
    compound, compound_sid = send(
        page,
        'Use the pricing method for the Customer-A licensed order '
        'with Qty 2 and Price 7.50; then email the quote.',
        'Additional work remains open')
    compound_exec = (compound.get('metadata') or {}).get(
        'teaching_execution') or {}
    compound_receipt = compound_exec.get('calculation_receipt') or {}
    assert compound.get('outcome') == 'partial', compound
    assert compound_receipt.get('value') == '15', compound_receipt
    assert compound_exec.get('covered_obligations') == ['calculation']
    assert compound_exec.get('open_obligations') == [
        {'kind': 'action', 'text': 'email the quote'}], compound_exec
    assert compound_exec.get('approval_id'), compound_exec
    assert 'email the quote' in compound.get('message', ''), compound
    out['cases']['compound'] = {
        'session_id': compound_sid,
        'outcome': compound.get('outcome'),
        'message': compound.get('message'),
        'receipt': compound_receipt,
        'open_obligations': compound_exec.get('open_obligations'),
        'approval_id': compound_exec.get('approval_id'),
    }
    page.screenshot(path=str(WORLD / 'chat-operand-compound.png'),
                    full_page=True)

    OUT.write_text(json.dumps(out, indent=2))
    browser.close()

print(OUT.read_text())
