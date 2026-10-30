"""Normal-browser journey, part 1: learn, promote, apply, change source."""
import json
import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

WORLD = Path('/Users/rushiparikh/projects/atom-conversation-world')
FRONTEND = 'http://127.0.0.1:3130'
PASSWORD = 'journey-pass'
OUT = WORLD / 'journey-part1.json'


def login(page):
    page.goto(f'{FRONTEND}/login', wait_until='domcontentloaded')
    page.get_by_test_id('login-email-input').fill('admin@example.com')
    page.get_by_test_id('login-password-input').fill(PASSWORD)
    page.get_by_test_id('login-submit-button').click()
    page.wait_for_url('**/dashboard', timeout=90000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed', '1')")
    page.reload(wait_until='domcontentloaded')


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        page = browser.new_page(viewport={'width': 1440, 'height': 1200})
        page.on('pageerror', lambda exc: errors.append(f'pageerror: {exc}'))
        login(page)

        page.goto(f'{FRONTEND}/learning', wait_until='domcontentloaded')
        page.get_by_test_id('learning-thread-select').wait_for(timeout=60000)
        page.get_by_test_id('learning-thread-select').select_option(value='thread-learn')
        page.get_by_test_id('learning-employee-select').wait_for(timeout=60000)
        page.get_by_test_id('learning-employee-select').select_option(value='agent-learn')
        page.get_by_test_id('learning-lesson-input').fill(
            'Use the approved rates method for pricing.')
        page.get_by_test_id('learning-operation-select').select_option(value='multiply_sum')
        page.get_by_test_id('learning-concept-1').fill('quantity')
        page.get_by_test_id('learning-column-1').fill('Qty')
        page.get_by_test_id('learning-unit-1').fill('units')
        page.get_by_test_id('learning-concept-2').fill('unit_price')
        page.get_by_test_id('learning-column-2').fill('Price')
        page.get_by_test_id('learning-unit-2').fill('USD')
        page.get_by_test_id('learning-draft-button').click()

        page.get_by_test_id('learning-proposed-lesson').wait_for(timeout=60000)
        assert page.get_by_test_id('learning-proposed-lesson').inner_text().startswith(
            'Use the approved rates method'), 'lesson text missing'
        assert 'rates.xlsx' in page.get_by_test_id('learning-references').inner_text()
        assert 'multiply_sum' in page.get_by_test_id('learning-method').inner_text()

        page.get_by_test_id('learning-confirm').click()
        page.get_by_test_id('learning-promote').wait_for(timeout=60000)
        page.wait_for_function(
            "() => !document.querySelector('[data-testid=learning-promote]').disabled",
            timeout=60000)
        page.get_by_test_id('learning-promote').click()
        page.get_by_test_id('learning-apply').wait_for(timeout=60000)

        page.get_by_test_id('learning-apply-quantity').fill('2')
        page.get_by_test_id('learning-apply-unit_price').fill('7.50')
        page.get_by_test_id('learning-apply-button').click()
        page.get_by_test_id('learning-apply-result').wait_for(timeout=60000)
        applied = page.get_by_test_id('learning-apply-result').inner_text().strip()
        assert applied.startswith('15'), applied
        page.screenshot(path=str(WORLD / 'journey-promoted.png'), full_page=True)

        token = page.evaluate(
            "localStorage.getItem('auth_token') || localStorage.getItem('token')")
        candidates = page.evaluate(
            "async (token) => (await fetch('/api/conversation-learning/threads/thread-learn/candidates', "
            "{headers: {Authorization: 'Bearer ' + token}})).json()",
            token)
        candidate_id = candidates['candidates'][0]['candidate']['candidate_id']

        conn = sqlite3.connect(WORLD / 'atom.db')
        conn.execute("update dataset_entries set content_hash='v2' where id='ds-learn'")
        conn.commit()
        conn.close()

        page.reload(wait_until='domcontentloaded')
        page.get_by_test_id('learning-proposed-lesson').wait_for(timeout=60000)
        body = page.locator('body').inner_text()
        assert 'invalidated' in body, body[:1000]
        assert page.get_by_test_id('learning-apply').count() == 0
        page.screenshot(path=str(WORLD / 'journey-stale.png'), full_page=True)

        applied_after = page.evaluate(
            "async ({token, cid}) => { const r = await fetch('/api/conversation-learning/candidates/' + cid + '/apply', "
            "{method: 'POST', headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token}, "
            "body: JSON.stringify({thread_id: 'thread-learn', rows: [{Qty: 1, Price: '10'}]})}); "
            "return {status: r.status, body: await r.text()}; }",
            {'token': token, 'cid': candidate_id})
        assert applied_after['status'] == 409, applied_after

        OUT.write_text(json.dumps({
            'candidate_id': candidate_id,
            'applied_value': applied,
            'stale_status': 'invalidated',
            'apply_after_change_http': applied_after['status'],
            'page_errors': errors,
            'screenshots': [str(WORLD / 'journey-promoted.png'),
                            str(WORLD / 'journey-stale.png')],
        }, indent=2))
        browser.close()
    print(OUT.read_text())


if __name__ == '__main__':
    main()
