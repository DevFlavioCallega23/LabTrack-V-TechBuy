import requests
import re

base = 'http://192.168.0.50:5000'
session = requests.Session()

# Login
r = session.get(f'{base}/login')
match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
csrf = match.group(1) if match else ''
print(f'Login CSRF: {csrf[:20]}...')

r2 = session.post(f'{base}/login', data={
    'csrf_token': csrf,
    'username': 'admin',
    'password': 'admin'
}, allow_redirects=True)
print(f'Login status: {r2.status_code}')

# Get edit page for protocol 6
r3 = session.get(f'{base}/protocolos/6/editar')
match2 = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r3.text)
csrf2 = match2.group(1) if match2 else ''
print(f'Edit CSRF: {csrf2[:20]}...')

# Check current status in form
status_match = re.search(r'<select[^>]*name="status"[^>]*>.*?<option[^>]*value="([^"]*)"[^>]*selected', r3.text, re.DOTALL)
if status_match:
    print(f'Current status in form: {status_match.group(1)}')
else:
    print('Could not find selected status in form')
    # Try to find any status-related info
    for m in re.finditer(r'name="status"[^>]*>(.*?)</select>', r3.text, re.DOTALL):
        options = re.findall(r'value="([^"]*)"', m.group(1))
        selected = re.findall(r'value="([^"]*)"[^>]*selected', m.group(1))
        print(f'Status options: {options}, selected: {selected}')

# POST change status to concluido
r4 = session.post(f'{base}/protocolos/6/editar', data={
    'csrf_token': csrf2,
    'type': 'venda',
    'client_name': 'Jannete Leda',
    'seller': 'Myris',
    'status': 'concluido',
    'entry_date': '10/07/2026',
}, allow_redirects=True)
print(f'Update status: {r4.status_code}')
print(f'Final URL: {r4.url}')

# Check the detail page
r5 = session.get(f'{base}/protocolos/6')
# Find status display
status_display = re.search(r'Status.*?</label>\s*<strong[^>]*>(.*?)</strong>', r5.text, re.DOTALL)
if status_display:
    import html
    print(f'Status displayed: {html.unescape(status_display.group(1)).strip()}')
else:
    print('Could not find status display in detail page')
