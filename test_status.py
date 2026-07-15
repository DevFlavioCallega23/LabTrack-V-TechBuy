import sys, os, json
sys.path.insert(0, r'C:\labtrack\ProjetoNovoControleLab')
os.chdir(r'C:\labtrack\ProjetoNovoControleLab')
from app import create_app, db
from app.models import Protocol, User
app = create_app()
with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['_fresh'] = True
    
    # GET edit page
    r = c.get('/protocolos/6/editar')
    print('GET status:', r.status_code)
    
    # Extract the csrf token
    import re
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.data.decode('utf-8'))
    csrf = match.group(1) if match else ''
    print('CSRF:', csrf[:20] + '...')
    
    # POST with status=concluido
    r2 = c.post('/protocolos/6/editar', data={
        'csrf_token': csrf,
        'type': 'venda',
        'client_name': 'Jannete Leda',
        'seller': 'Myris',
        'status': 'concluido',
        'entry_date': '10/07/2026',
    }, follow_redirects=True)
    print('POST status:', r2.status_code)
    
    # Check the protocol
    p = db.session.get(Protocol, 6)
    print('Protocol 6 status after POST:', repr(p.status))
