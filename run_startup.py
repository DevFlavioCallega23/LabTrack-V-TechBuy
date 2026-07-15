import sys, os
sys.path.insert(0, r'C:\labtrack\ProjetoNovoControleLab')
os.chdir(r'C:\labtrack\ProjetoNovoControleLab')
from app import create_app
create_app().run(host='0.0.0.0', port=5000, debug=False)
