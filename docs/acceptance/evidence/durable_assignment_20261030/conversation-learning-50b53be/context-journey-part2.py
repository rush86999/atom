import json, sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright
WORLD=Path('/Users/rushiparikh/projects/atom-conversation-context-world')
FRONTEND='http://127.0.0.1:3130'; PASSWORD='journey-pass'
part1=json.loads((WORLD/'context-journey-part1.json').read_text())
with sync_playwright() as p:
    b=p.chromium.launch(headless=True, executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    page=b.new_page(viewport={'width':1440,'height':1200}); errors=[]
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'{FRONTEND}/login', wait_until='domcontentloaded')
    page.get_by_test_id('login-email-input').fill('admin@example.com')
    page.get_by_test_id('login-password-input').fill(PASSWORD)
    page.get_by_test_id('login-submit-button').click(); page.wait_for_url('**/dashboard', timeout=90000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed','1')")
    page.goto(f'{FRONTEND}/learning?thread=thread-learn', wait_until='domcontentloaded')
    page.get_by_test_id('learning-proposed-lesson').wait_for(timeout=60000)
    body=page.locator('body').inner_text(); assert 'invalidated' in body, body[:800]
    assert page.get_by_test_id('learning-apply').count()==0
    token=page.evaluate("localStorage.getItem('auth_token') || localStorage.getItem('token')")
    candidate=page.evaluate("async ({t,c}) => (await fetch('/api/conversation-learning/candidates/'+c+'?thread_id=thread-learn',{headers:{Authorization:'Bearer '+t}})).json()", {'t':token,'c':part1['candidate_id']})
    assert candidate['candidate']['status']=='invalidated', candidate
    conn=sqlite3.connect(WORLD/'atom.db')
    row=conn.execute("select configuration from agent_registry where id='agent-learn'").fetchone(); conn.close()
    config=json.loads(row[0]); lesson=next(item for item in config['learning']['log'] if item.get('id')==candidate['candidate']['promoted_entry_id'])
    assert lesson.get('stale') is True, lesson
    assert lesson.get('context',{}).get('customer')=='Customer-A', lesson
    applied=page.evaluate("async ({t,c}) => {const r=await fetch('/api/conversation-learning/candidates/'+c+'/apply',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+t},body:JSON.stringify({thread_id:'thread-learn',context:{customer:'Customer-A',qualification:'licensed'},rows:[{Qty:1,Price:'10'}]})});return {status:r.status,body:await r.text()}}", {'t':token,'c':part1['candidate_id']})
    assert applied['status']==409, applied
    page.screenshot(path=str(WORLD/'context-after-restart.png'), full_page=True)
    out={'candidate_status':candidate['candidate']['status'],'lesson_stale':lesson.get('stale'),'top_level_context':lesson.get('context'),'apply_after_restart_http':applied['status'],'page_errors':errors,'screenshot':str(WORLD/'context-after-restart.png')}
    (WORLD/'context-journey-part2.json').write_text(json.dumps(out,indent=2)); b.close()
print(json.dumps(out,indent=2))
