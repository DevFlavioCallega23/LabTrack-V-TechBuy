"""Conversão de datas no formato brasileiro (DD/MM/AAAA) usado nos formulários."""
from datetime import datetime

def parse_date_br(text):
    """Converte 'DD/MM/AAAA', 'DD/MM/AA' ou 'AAAA-MM-DD' em datetime; None se inválido."""
    if not text or not text.strip():
        return None
    text = text.strip().replace('/', '-')
    for fmt in ['%d-%m-%Y', '%d-%m-%y', '%Y-%m-%d']:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
