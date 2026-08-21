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
    r = c.get('/protocolos/6/editar')
    html = r.data.decode('utf-8')
    selects = re.findall(r'<select[^>]*name="status"[^>]*>', html)
    print(f'Found {len(selects)} status selects')
    for i, s in enumerate(selects):
        print(f'  Select {i}: {s[:120]}')
    # Check if there are truly two different status fields
    status_blocks = re.findall(r'<select[^>]*name="status"[^>]*>.*?</select>', html, re.DOTALL)
    p = db.session.get(Protocol, 6)
    print(f'\nProtocol 6 status in DB: {repr(p.status)}')
