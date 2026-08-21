import sys, os
sys.path.insert(0, r'C:\labtrack\ProjetoNovoControleLab')
os.chdir(r'C:\labtrack\ProjetoNovoControleLab')
os.environ['FLASK_DEBUG'] = '1'
from app import create_app
app = create_app()
with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['_fresh'] = True
    r = c.get('/protocolos/7')
    print('Status:', r.status_code)
    if r.status_code == 200:
        # Check if it returned the detail page or login page
        if 'PRO-2026-0007' in r.data.decode('utf-8') or 'WhatsApp' in r.data.decode('utf-8'):
            print('SUCCESS: Detail page rendered')
        elif 'login' in r.data.decode('utf-8'):
            print('Got login page instead')
        else:
            print('Unknown page')
    else:
        print('ERROR:', r.data.decode('utf-8')[:1000])
