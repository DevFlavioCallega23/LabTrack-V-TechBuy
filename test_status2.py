import sys, os, re
sys.path.insert(0, r'C:\labtrack\ProjetoNovoControleLab')
os.chdir(r'C:\labtrack\ProjetoNovoControleLab')
from app import create_app, db
from app.models import Protocol
app = create_app()
with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['_fresh'] = True
    
    # GET edit page
    r = c.get('/protocolos/6/editar')
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.data.decode('utf-8'))
    csrf = match.group(1) if match else ''
    
    # Simulate what user does: change status to concluido, submit with minimal data
    r2 = c.post('/protocolos/6/editar', data={
        'csrf_token': csrf,
        'type': 'venda',
        'client_name': 'Jannete Leda',
        'seller': 'Myris',
        'status': 'concluido',
        'entry_date': '10/07/2026',
    }, follow_redirects=True)
    
    # Check result  
    p = db.session.get(Protocol, 6)
    print('After POST with status=concluido:', repr(p.status))
    
    # Now try with status field NOT in POST data (simulate if display:none prevents submission)
    r3 = c.get('/protocolos/6/editar')
    match2 = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r3.data.decode('utf-8'))
    csrf2 = match2.group(1) if match2 else ''
    
    r4 = c.post('/protocolos/6/editar', data={
        'csrf_token': csrf2,
        'type': 'venda',
        'client_name': 'Jannete Leda',
        'seller': 'Myris',
        # no status field!
        'entry_date': '10/07/2026',
    }, follow_redirects=True)
    
    p2 = db.session.get(Protocol, 6)
    print('After POST without status:', repr(p2.status))
