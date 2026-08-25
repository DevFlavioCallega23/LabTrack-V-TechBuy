# LabTrack — Controle de Laboratório

Sistema web para gestão de protocolos de um laboratório de manutenção de computadores: RMA (garantia), Serviços fora de garantia, Vendas (montadas e pronta-entrega), Pronta-Entrega e NTB.

Desenvolvido para uso real no dia a dia do laboratório da TechBuy — controle completo desde a entrada do equipamento até a saída, com histórico de passagens, rastreio de números de série e relatórios gerenciais.

## Funcionalidades

### Protocolos
- **Cinco tipos de protocolo**, cada um com formulário adaptado ao fluxo:
  - **RMA (Garantia)** — produto do cliente coberto pela loja
  - **Serviço (Fora de Garantia)** — responsabilidade do cliente
  - **Venda** — com marcador para vendas *Pronta-Entrega (PE)*
  - **Pronta-Entrega** — inspeção de máquinas novas em estoque
  - **NTB** — equipamentos não comprados na TechBuy
- **Teste de Mesa** por item: componente, modelo, NS, defeito, situação, pedido e data de compra de cada peça enviada ao laboratório
- **Passagens anteriores**: histórico de retornos do mesmo equipamento, incluindo o NS do produto novo instalado
- Numeração que reinicia a cada ano (`PRO-2026-0095` → `PRO-2027-0001`)
- Compartilhamento formatado por WhatsApp com um clique
- Geração de **PDF oficial** com logo e identidade visual do sistema

### Defeitos
- Controle centralizado separando duas naturezas:
  - **Produto que voltou do cliente** (RMA Garantia / Fora de Garantia / NTB)
  - **Equipamentos da TechBuy** — item novo de estoque que apresentou defeito, vindo de qualquer tipo de protocolo
- Status por defeito: aguardando peça, em teste, trocado, devolvido, concluído

### Busca e rastreio
- **Busca avançada combinável**: cliente, vendedor, tipo, número do pedido (incluindo pedido original), período de entrada e número de série
- **Rastreio de NS**: um número de série é localizado em qualquer canto do sistema — componentes, defeitos, teste de mesa, passagens e máquinas TechBuy
- **Todos os NS**: visão consolidada de todo número de série já registrado

### Relatórios e dashboard
- Filtro por ano/mês com total por tipo e ranking de defeitos por componente
- **Tempo médio de permanência** no laboratório por tipo de protocolo
- Dashboard inicial com contadores e alerta de protocolos parados há mais de 7 dias

### Administração
- Usuários com papéis **Master / Admin / Visualizador**
- **Backup automático** agendado (segunda a sexta, 16h) para o OneDrive, com retenção configurável
- **Página de backup** (exclusiva Master): criação manual, download e restauração segura — exige digitação de confirmação e salva snapshot automático do estado anterior antes de restaurar

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + Flask 3 |
| Banco de dados | SQLite (via SQLAlchemy) |
| Autenticação | Flask-Login |
| Formulários | Flask-WTF / WTForms |
| Frontend | Bootstrap 5 (tema dark) + Bootstrap Icons |
| PDF | xhtml2pdf |
| Testes | pytest |

## Como executar

```bash
# 1. Clone o repositório
git clone https://github.com/DevFlavioCallega23/ProjetoNovoControleLab.git
cd ProjetoNovoControleLab

# 2. Crie e ative um ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Execute
python run.py
```

O sistema sobe em `http://localhost:5000`. Na primeira execução (banco vazio) é criado automaticamente o usuário inicial:

| Usuário | Senha | Papel |
|---|---|---|
| `admin` | `admin123` | Master |

> 🔐 **Recomendação**: altere a senha no primeiro acesso (menu da conta → Minha Conta). Em bancos que já possuem usuários, nenhum usuário automático é criado.

> Observação: o módulo de backup aponta para uma pasta local específica do ambiente de produção; para uso em outra máquina basta ajustar `ONE_DRIVE_DIR` em `backup.py`.

## Testes

A suíte roda em banco de dados isolado (nunca toca nos dados reais):

```bash
python -m pytest tests/ -q
```

Cobrem autenticação, criação de protocolos, migrações de dados, busca avançada, geração de PDF, numeração anual e o fluxo completo de backup/restauração.

## Estrutura do projeto

```
ProjetoNovoControleLab/
├── app/
│   ├── __init__.py          # Factory da aplicação + migrações automáticas
│   ├── models.py            # Modelos (Protocol, Defect, Component, User...)
│   ├── forms.py             # Formulários WTForms
│   ├── routes/              # Blueprints (protocols, main, auth, maquinas, backup_admin)
│   ├── templates/           # Templates Jinja2
│   └── static/              # CSS, JS e imagens
├── tests/                   # Suíte pytest (banco temporário isolado)
├── backup.py                # Rotina de backup com retenção
├── run.py / run_startup.py  # Pontos de entrada
└── requirements.txt
```

## Autor

**Flávio Callega**
Projeto real desenvolvido para o laboratório da TechBuy.
