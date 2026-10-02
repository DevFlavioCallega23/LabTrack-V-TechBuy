"""Rótulos canônicos do LabTrack — fonte única de verdade.

Todos os templates, models e rotas importam daqui. Nunca copiar estes
dicts para dentro de outro arquivo: edite apenas neste.
"""

# --- Protocolo ---------------------------------------------------------

PROTO_TYPE_LABELS = {
    'venda': 'Venda',
    'ponta_entrega': 'Pronta-Entrega',
    'rma': 'RMA (Garantia)',
    'servico': 'Serviço (Fora de Garantia)',
    'nao_comprado': 'NTB',
}

PROTO_TYPE_BADGES = {
    'venda': 'bg-success',
    'ponta_entrega': 'bg-warning text-dark',
    'rma': 'bg-primary',
    'servico': 'bg-danger',
    'nao_comprado': 'bg-secondary',
}

PROTO_STATUS_LABELS = {
    'pendente': 'Pendente',
    'andamento': 'Em Andamento',
    'concluido': 'Concluído',
    'cancelado': 'Cancelado',
}

PROTO_STATUS_BADGES = {
    'pendente': 'bg-warning text-dark',
    'andamento': 'bg-dark',
    'concluido': 'bg-info text-dark',
    'cancelado': 'bg-danger',
}

# Agrupamento do relatório de tempo médio
TEMPO_LABELS = {
    'venda': 'Venda',
    'ponta_entrega': 'Pronta-Entrega',
    'nao_comprado': 'NTB',
    'rma_servico': 'RMA / Serviço',
}

# --- Componentes -------------------------------------------------------

COMPONENT_ORDER = [
    'processador', 'placa_mae', 'ram', 'ssd', 'hdd', 'fonte',
    'placa_de_video', 'gpu', 'gabinete', 'monitor', 'cabo_de_forca', 'outro',
]

COMPONENT_LABELS = {
    'processador': 'Processador',
    'placa_mae': 'Placa-Mãe',
    'ram': 'Memória RAM',
    'ssd': 'SSD',
    'hdd': 'HD (mecânico)',
    'fonte': 'Fonte',
    'placa_de_video': 'Placa de Vídeo',
    'gpu': 'GPU',
    'gabinete': 'Gabinete',
    'monitor': 'Monitor',
    'cabo_de_forca': 'Cabo de Força',
    'outro': 'Outro',
}

# Lista (chave, rótulo) na ordem de exibição — usada em <select>.
COMPONENT_OPTIONS = [(k, COMPONENT_LABELS[k]) for k in COMPONENT_ORDER]

# --- Formulário de protocolo --------------------------------------------
# Rótulos dos campos do ProtocolForm (forms.py) e títulos das seções do
# create/edit. Edite aqui: forms.py, create.html e o JS leem daqui.

PROTO_FIELD_LABELS = {
    'type': 'Tipo de Protocolo',
    'venda_pe': 'Venda Pronta-Entrega (PE)',
    'client_name': 'Cliente',
    'lote': 'Quantidade',
    'order_number': 'Número do Pedido',
    'seller': 'Vendedor',
    'status': 'Status',
    'entry_date': 'Data da Compra',
    'exit_date': 'Data de Saída',
    'ref_ns': 'NS de Referência',
    'base_defect': 'Defeito de Base',
    'original_order': 'Pedido Original',
    'rma_extra_equip': 'Equipamento extra do cliente',
    'rma_test_result': 'Resultado do Teste de Mesa',
    'rma_entry_date': 'Data de Entrada',
    'observations': 'Observações',
    'submit': 'Salvar',
}

PROTO_SECTION_TITLES = {
    'cliente': 'Dados do Cliente',
    'rma': 'Dados do RMA',
    'rma_servico': 'Dados do Serviço',
    'equipamento_cliente': 'Equipamento do Cliente',
    'teste_mesa': 'Resultado do Teste de Mesa / Defeitos encontrados',
    'equipamentos_mudados': 'Equipamentos Mudados',
    'identificacao': 'Dados da Venda',
    'numeros_serie': 'Números de Série',
    'chave_windows': 'Chave do Windows',
    'defeitos': 'Defeitos Encontrados',
    'observacoes': 'Observações',
    'defeito_relatado': 'Defeito Relatado / Observações Técnicas',
}

# --- Defeitos ----------------------------------------------------------

DEFEITO_STATUS_LABELS = {
    'aguardando_peca': 'Aguardando peça',
    'em_teste': 'Em teste',
    'trocado': 'Trocado',
    'devolvido': 'Devolvido ao cliente',
    'concluido': 'Concluído',
}

DEFEITO_STATUS_BADGES = {
    'aguardando_peca': 'bg-danger',
    'em_teste': 'bg-dark',
    'trocado': 'bg-primary',
    'devolvido': 'bg-warning text-dark',
    'concluido': 'bg-success',
}

DEFEITO_RESP_LABELS = {
    'loja': 'Loja',
    'cliente': 'Cliente',
    'terceiro': 'Terceiro',
}

DEFEITO_RESP_BADGES = {
    'loja': 'bg-success',
    'cliente': 'bg-warning text-dark',
    'terceiro': 'bg-info text-dark',
}

# Mapeia o texto digitado no campo de defeito para o rótulo exibido
# (chaves minúsculas, sem acento — vindo de dados livres antigos).
DEFEITO_PECA_LABELS = {
    'placa mae': 'Placa-Mãe',
    'processador': 'Processador',
    'memoria ram': 'Memória RAM',
    'hd': 'HD',
    'ssd': 'SSD',
    'fonte': 'Fonte',
    'placa de video': 'Placa de Vídeo',
    'gabinete': 'Gabinete',
    'cooling': 'Cooler',
    'monitor': 'Monitor',
    'mouse': 'Mouse',
    'teclado': 'Teclado',
    'mouse_teclado': 'Mouse + Teclado',
    'webcam': 'Webcam',
    'headset': 'Headset',
    'fone': 'Fone',
    'no_break': 'No-Break',
    'cabo de rede': 'Cabo de Rede',
    'cabo hdmi': 'Cabo HDMI',
    'cabo displayport': 'Cabo DP',
    'ssd notebook': 'SSD Notebook',
    'placa mae notebook': 'Placa-Mãe Notebook',
    'memoria ram notebook': 'Memória RAM Notebook',
    'memoria ram note': 'Memória RAM Notebook',
}


def peca_label(text):
    """Rótulo legível para um nome de peça vindo de texto livre/legado.

    Tenta, nesta ordem: chave canônica exata, minúsculas, minúsculas com
    '_' trocado por espaço, e por último o mapa de peças de defeito.
    """
    if not text:
        return ''
    raw = str(text).strip()
    if raw in COMPONENT_LABELS:
        return COMPONENT_LABELS[raw]
    key = raw.lower()
    if key in COMPONENT_LABELS:
        return COMPONENT_LABELS[key]
    for candidate in (key, key.replace('_', ' '), key.replace(' ', '_')):
        if candidate in DEFEITO_PECA_LABELS:
            return DEFEITO_PECA_LABELS[candidate]
    return raw
