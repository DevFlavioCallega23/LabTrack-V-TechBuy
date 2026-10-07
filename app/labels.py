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
    'processador', 'placa_mae', 'ram', 'ssd', 'gpu', 'fonte',
    'hdd', 'placa_de_video', 'gabinete', 'monitor', 'cabo_de_forca', 'outro',
]

COMPONENT_LABELS = {
    'processador': 'Processador',
    'placa_mae': 'Placa-Mãe',
    'ram': 'Memória RAM',
    'ssd': 'SSD',
    'gpu': 'GPU',
    'fonte': 'Fonte',
    'hdd': 'HD (mecânico)',
    'placa_de_video': 'Placa de Vídeo',
    'gabinete': 'Gabinete',
    'monitor': 'Monitor',
    'cabo_de_forca': 'Cabo de Força',
    'outro': 'Outro',
}

# Lista (chave, rótulo) na ordem de exibição — usada em <select>.
COMPONENT_OPTIONS = [(k, COMPONENT_LABELS[k]) for k in COMPONENT_ORDER]

# Snapshot das chaves oficiais — tipos cadastrados pelo usuário nunca
# sobrescrevem o rótulo de um tipo fixo (ex.: digitar "RAM" em "ram").
COMPONENT_KEYS_OFICIAIS = frozenset(COMPONENT_LABELS)


def carregar_tipos_custom(rows):
    """Registra tipos de componente cadastrados pelo usuário (botão +).

    `rows` é uma lista de (key, label). Os dicts/listas desta fonte única
    são mutados no lugar: todos os templates e rotas que já importam
    COMPONENT_LABELS/COMPONENT_ORDER/COMPONENT_OPTIONS enxergam o tipo
    novo sem precisar de mais nada.
    """
    for key, label in rows:
        if not key or not label:
            continue
        key = str(key).strip()
        label = str(label).strip()
        if key in COMPONENT_LABELS and COMPONENT_LABELS[key] == label:
            continue
        COMPONENT_LABELS[key] = label
        if key not in COMPONENT_ORDER:
            COMPONENT_ORDER.append(key)
    COMPONENT_OPTIONS[:] = [(k, COMPONENT_LABELS[k]) for k in COMPONENT_ORDER]


def aplicar_ordem_custom(rows):
    """Reordena COMPONENT_ORDER/dict conforme a ordem definida em Produtos.

    `rows` é uma lista de (key, posicao). Chaves sem posição ficam no fim
    na ordem original. A lista e o dict são mutados no lugar — todos os
    selects e listagens enxergam a nova ordem.
    """
    pos = {}
    for key, p in rows:
        try:
            pos[str(key)] = int(p)
        except (TypeError, ValueError):
            continue
    if not pos:
        return
    com_ordem = sorted((k for k in COMPONENT_ORDER if k in pos),
                       key=lambda k: (pos[k], k))
    extras = sorted((k for k in pos if k not in COMPONENT_ORDER),
                    key=lambda k: (pos[k], k))
    sem_ordem = [k for k in COMPONENT_ORDER if k not in pos]
    nova = com_ordem + extras + sem_ordem
    COMPONENT_ORDER[:] = nova

    visto = set()
    itens = []
    for k in nova:
        if k in COMPONENT_LABELS and k not in visto:
            itens.append((k, COMPONENT_LABELS[k]))
            visto.add(k)
    for k, v in COMPONENT_LABELS.items():
        if k not in visto:
            itens.append((k, v))
    COMPONENT_LABELS.clear()
    COMPONENT_LABELS.update(itens)

    COMPONENT_OPTIONS[:] = [
        (k, COMPONENT_LABELS[k]) for k in COMPONENT_ORDER if k in COMPONENT_LABELS
    ]

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

# Opções oferecidas nos formulários (status atuais).
DEFEITO_STATUS_LABELS = {
    'aguardando_peca': 'Aguardando peça',
    'trocado': 'Trocado',
}

# Todos os status, incluindo os antigos — usado só para exibir registros
# gravados antes da redução das opções (não aparecem nos selects).
DEFEITO_STATUS_TODOS = {
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
        if candidate in COMPONENT_LABELS:
            return COMPONENT_LABELS[candidate]
        if candidate in DEFEITO_PECA_LABELS:
            return DEFEITO_PECA_LABELS[candidate]
    return raw
