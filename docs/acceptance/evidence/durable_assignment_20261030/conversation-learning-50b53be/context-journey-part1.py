import json, sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright
WORLD=Path('/Users/rushiparikh/projects/atom-conversation-context-world')
FRONTEND='http://127.0.0.1:3130'; PASSWORD='journey-pass'
OUT=WORLD/'context-journey-part1.json'
with sync_playwright() as p:
    b=p.chromium.launch(headless=True, executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    page=b.new_page(viewport={'width':1440,'height':1200}); errors=[]
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'{FRONTEND}/login', wait_until='domcontentloaded')
    page.get_by_test_id('login-email-input').fill('admin@example.com')
    page.get_by_test_id('login-password-input').fill(PASSWORD)
    page.get_by_test_id('login-submit-button').click(); page.wait_for_url('**/dashboard', timeout=90000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed','1')")
    page.goto(f'{FRONTEND}/learning', wait_until='domcontentloaded')
    page.get_by_test_id('learning-thread-select').wait_for(timeout=60000)
    page.get_by_test_id('learning-thread-select').select_option(value='thread-learn')
    page.get_by_test_id('learning-employee-select').select_option(value='agent-learn')
    page.get_by_test_id('learning-lesson-input').fill('Use the Customer-A licensed rates method.')
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
    page.wait_for_function("() => !document.querySelector('[data-testid=learning-promote]').disabled", timeout=60000)
    page.get_by_test_id('learning-promote').click()
    page.get_by_test_id('learning-apply').wait_for(timeout=60000)

    page.get_by_test_id('learning-apply-customer').fill('Customer-B')
    page.get_by_test_id('learning-apply-qualification').fill('unlicensed')
    page.get_by_test_id('learning-apply-quantity').fill('2')
    page.get_by_test_id('learning-apply-unit_price').fill('7.50')
    page.get_by_test_id('learning-apply-button').click()
    page.get_by_test_id('learning-error').wait_for(timeout=60000)
    wrong_error=page.get_by_test_id('learning-error').inner_text()
    assert 'context' in wrong_error.lower(), wrong_error

    page.get_by_test_id('learning-apply-customer').fill('Customer-A')
    page.get_by_test_id('learning-apply-qualification').fill('licensed')
    page.get_by_test_id('learning-apply-button').click()
    page.get_by_test_id('learning-apply-result').wait_for(timeout=60000)
    applied=page.get_by_test_id('learning-apply-result').inner_text().strip()
    assert applied.startswith('15'), applied
    page.screenshot(path=str(WORLD/'context-promoted.png'), full_page=True)

    token=page.evaluate("localStorage.getItem('auth_token') || localStorage.getItem('token')")
    candidates=page.evaluate("async (t) => (await fetch('/api/conversation-learning/threads/thread-learn/candidates', {headers:{Authorization:'Bearer '+t}})).json()", token)
    cid=candidates['candidates'][0]['candidate']['candidate_id']
    conn=sqlite3.connect(WORLD/'atom.db')
    entry=conn.execute("select configuration from agent_registry where id='agent-learn'").fetchone()
    conn.close()
    log=json.loads(entry[0])['learning']['log']
    lesson=next(item for item in log if item.get('id')==candidates['candidates'][0]['candidate']['promoted_entry_id'])
    assert lesson.get('context',{}).get('customer')=='Customer-A', lesson
    assert lesson.get('context',{}).get('qualification')=='licensed', lesson

    conn=sqlite3.connect(WORLD/'atom.db'); conn.execute("update dataset_entries set content_hash='v2' where id='ds-learn'"); conn.commit(); conn.close()
    page.reload(wait_until='domcontentloaded')
    page.get_by_test_id('learning-proposed-lesson').wait_for(timeout=60000)
    body=page.locator('body').inner_text(); assert 'invalidated' in body, body[:800]
    assert page.get_by_test_id('learning-apply').count()==0
    page.screenshot(path=str(WORLD/'context-stale.png'), full_page=True)
    applied_after=page.evaluate("async ({t,c}) => {const r=await fetch('/api/conversation-learning/candidates/'+c+'/apply',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+t},body:JSON.stringify({thread_id:'thread-learn',context:{customer:'Customer-A',qualification:'licensed'},rows:[{Qty:1,Price:'10'}]})});return {status:r.status,body:await r.text()}}", {'t':token,'c':cid})
    assert applied_after['status']==409, applied_after
    OUT.write_text(json.dumps({'candidate_id':cid,'wrong_context_error':wrong_error,'matching_value':applied,'stale_status':'invalidated','apply_after_change_http':applied_after['status'],'top_level_context':lesson['context'],'page_errors':errors}, indent=2))
    b.close()
print(OUT.read_text())
