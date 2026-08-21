import sys, os, re, http.client, urllib.parse
sys.path.insert(0, r'C:\labtrack\ProjetoNovoControleLab')
os.chdir(r'C:\labtrack\ProjetoNovoControleLab')

host = '192.168.0.50'

def http_get(path, cookies=None):
    conn = http.client.HTTPConnection(host, 5000, timeout=10)
    headers = {}
    if cookies:
        headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    conn.request('GET', path, headers=headers)
    r = conn.getresponse()
    data = r.read().decode('utf-8')
    set_cookie = r.getheader('Set-Cookie')
    conn.close()
    if set_cookie:
        for part in set_cookie.split(','):
            m = re.match(r'(session=[^;]+)', part.strip())
            if m:
                kv = m.group(1).split('=', 1)
                if kv[0] not in cookies:
                    cookies[kv[0]] = kv[1]
    return r.status, data

def http_post(path, data, cookies=None):
    conn = http.client.HTTPConnection(host, 5000, timeout=10)
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if cookies:
        headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    body = urllib.parse.urlencode(data)
    conn.request('POST', path, body=body, headers=headers)
    r = conn.getresponse()
    result = r.read().decode('utf-8')
    set_cookie = r.getheader('Set-Cookie')
    conn.close()
    if set_cookie:
        for part in set_cookie.split(','):
            m = re.match(r'(session=[^;]+)', part.strip())
            if m:
                kv = m.group(1).split('=', 1)
                cookies[kv[0]] = kv[1]
    return r.status, result

cookies = {}

# Login
status, data = http_get('/login', cookies)
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', data)
csrf = m.group(1) if m else ''
print(f'Login CSRF: {csrf[:20]}...')

status, data = http_post('/login', {
    'csrf_token': csrf,
    'username': 'admin',
    'password': 'admin'
}, cookies)
print(f'Login status: {status}')

# Get edit
status, data = http_get('/protocolos/6/editar', cookies)
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', data)
csrf2 = m.group(1) if m else ''
print(f'Edit CSRF: {csrf2[:20]}...')

# Check current status value
status_val = re.search(r'<select[^>]*name="status"[^>]*>.*?</select>', data, re.DOTALL)
if status_val:
    sel = re.search(r'value="([^"]*)"[^>]*selected', status_val.group())
    print(f'Current status in form: {sel.group(1) if sel else "none selected"}')

# POST update
status, data = http_post('/protocolos/6/editar', {
    'csrf_token': csrf2,
    'type': 'venda',
    'client_name': 'Jannete Leda',
    'seller': 'Myris',
    'status': 'concluido',
    'entry_date': '10/07/2026',
}, cookies)
print(f'Update status: {status}')
print(f'Redirected to: {"/protocolos/6" if status in [200, 302] else "unknown"}')

# Check detail
status, data = http_get('/protocolos/6', cookies)
m = re.search(r'Status.*?</label>\s*<strong[^>]*>\s*(.*?)\s*</strong>', data, re.DOTALL)
if m:
    import html
    print(f'Status in detail: {html.unescape(m.group(1)).strip()}')
else:
    print('Could not find status')
    # Save response for debug
    with open('debug_response.html', 'w', encoding='utf-8') as f:
        f.write(data)
    print('Saved response to debug_response.html')
