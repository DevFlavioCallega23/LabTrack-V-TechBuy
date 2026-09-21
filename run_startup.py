import sys, os
sys.path.insert(0, r'C:\labtrack\ProjetoNovoControleLab')
os.chdir(r'C:\labtrack\ProjetoNovoControleLab')
import logging
logging.basicConfig(filename='error.log', level=logging.ERROR)
from app import create_app
app = create_app()
app.config['PROPAGATE_EXCEPTIONS'] = True

import werkzeug.serving
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
handler = logging.FileHandler('error.log')
handler.setLevel(logging.ERROR)
app.logger.addHandler(handler)
app.logger.setLevel(logging.ERROR)

app.run(host='0.0.0.0', port=5000, debug=False)
