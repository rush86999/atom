"""Normal-browser journey, part 2: restart persistence and blocked reuse."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

WORLD = Path('/Users/rushiparikh/projects/atom-conversation-world')
FRONTEND = 'http://127.0.0.1:3130'
PASSWORD = 'journey-pass'
PART1 = json.loads((WORLD / 'journey-part1.json').read_text())


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        page = browser.new_page(viewport={'width': 1440, 'height': 1200})
        page.on('pageerror', lambda exc: errors.append(f'pageerror: {exc}'))
        page.goto(f'{FRONTEND}/login', wait_until='domcontentloaded')
        page.get_by_test_id('login-email-input').fill('admin@example.com')
        page.get_by_test_id('login-password-input').fill(PASSWORD)
        page.get_by_test_id('login-submit-button').click()
        page.wait_for_url('**/dashboard', timeout=90000)
        page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed','1')")
        page.goto(f'{FRONTEND}/learning?thread=thread-learn', wait_until='domcontentloaded')
        page.get_by_test_id('learning-proposed-lesson').wait_for(timeout=60000)
        body = page.locator('body').inner_text()
        assert 'invalidated' in body, body[:1000]
        assert page.get_by_test_id('learning-apply').count() == 0

        token = page.evaluate(
            "localStorage.getItem('auth_token') || localStorage.getItem('token')")
        candidate = page.evaluate(
            "async ({token, cid}) => (await fetch('/api/conversation-learning/candidates/' + cid + "
            " '?thread_id=thread-learn', {headers: {Authorization: 'Bearer ' + token}})).json()",
            {'token': token, 'cid': PART1['candidate_id']})
        assert candidate['candidate']['status'] == 'invalidated', candidate

        import sqlite3
        conn = sqlite3.connect(WORLD / 'atom.db')
        row = conn.execute(
            "select configuration from agent_registry where id='agent-learn'"
        ).fetchone()
        conn.close()
        config = json.loads(row[0] or '{}')
        raw = next(item for item in config['learning']['log']
                   if item.get('id') == candidate['candidate']['promoted_entry_id'])
        assert raw.get('stale') is True, raw
        provenance = raw.get('details', {}).get('conversation_learning', {})
        assert provenance.get('revalidation_required') is True, provenance

        applied = page.evaluate(
            "async ({token, cid}) => { const r = await fetch('/api/conversation-learning/candidates/' + cid + '/apply', "
            "{method: 'POST', headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token}, "
            "body: JSON.stringify({thread_id: 'thread-learn', rows: [{Qty: 1, Price: '10'}]})}); "
            "return {status: r.status, body: await r.text()}; }",
            {'token': token, 'cid': PART1['candidate_id']})
        assert applied['status'] == 409, applied
        page.screenshot(path=str(WORLD / 'journey-after-restart.png'), full_page=True)

        out = {
            'candidate_status': candidate['candidate']['status'],
            'lesson_stale': raw.get('stale'),
            'revalidation_required': provenance.get('revalidation_required'),
            'apply_after_restart_http': applied['status'],
            'page_errors': errors,
            'screenshot': str(WORLD / 'journey-after-restart.png'),
        }
        (WORLD / 'journey-part2.json').write_text(json.dumps(out, indent=2))
        browser.close()
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
