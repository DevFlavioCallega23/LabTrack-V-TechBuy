/* JS do formulário de protocolo (extraído de protocols/create.html).
   Os dados vindos do servidor chegam em window.PF_FORM (ver bootstrap no template). */
'use strict';

function safeParse(texto, fallback) {
    try {
        const valor = JSON.parse(texto);
        return (valor === null || valor === undefined) ? fallback : valor;
    } catch (e) {
        return fallback;
    }
}

function escHtml(valor) {
    if (valor === null || valor === undefined) return '';
    return String(valor)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function mapFromPairs(pairs) {
    const map = {};
    (pairs || []).forEach(function(par) { map[par[0]] = par[1]; });
    return map;
}

const PF = window.PF_FORM || {};
const CFG = {
    compTypes: safeParse(PF.compTypes, []),
    machines: PF.machines || [],
    rmaTestData: safeParse(PF.rmaTestData, []),
    produtos: safeParse(PF.produtos, []),
    compData: safeParse(PF.compData, {}),
    rmaCompData: safeParse(PF.rmaCompData, {}),
    rmaTrocados: safeParse(PF.rmaTrocados, []),
    winKeys: safeParse(PF.winKeys, []),
    passagens: safeParse(PF.passagens, null),
    statusOptions: mapFromPairs(PF.statusOptions),
    titles: PF.titles || {},
    fields: PF.fields || {},
    protocolType: PF.protocolType || '',
    protocolId: PF.protocolId || 0,
    protocolNumber: PF.protocolNumber || '',
    saleRefs: safeParse(PF.saleRefs, {}),
    peRefs: safeParse(PF.peRefs, {})
};

function optionsHtml(map) {
    return Object.keys(map).map(function(k) {
        return '<option value="' + k + '">' + map[k] + '</option>';
    }).join('');
}

function optionsSelectedHtml(map, selected) {
    return Object.keys(map).map(function(k) {
        const sel = (selected === k) ? ' selected' : '';
        return '<option value="' + k + '"' + sel + '>' + map[k] + '</option>';
    }).join('');
}

let COMP_TYPES_DB = CFG.compTypes;
let produtosCatalogo = CFG.produtos;
const STATUS_OPTS = optionsHtml(CFG.statusOptions);
const statusOptsSelected = function(sel) { return optionsSelectedHtml(CFG.statusOptions, sel); };

const COMP_LABELS = {};
const COMP_ORDER = [];
COMP_TYPES_DB.forEach(function(t) {
    COMP_LABELS[t.key] = t.label;
    COMP_ORDER.push(t.key);
});
const EXTRA_OPTS = '<option value="">-- Selecione --</option>' +
    COMP_ORDER.map(function(k) { return `<option value="${escHtml(k)}">${escHtml(COMP_LABELS[k])}</option>`; }).join('');

const MACHINES_FROM_TEST = CFG.rmaTestData.map(function(it) { return it.machine; })
    .filter(function(m, i, arr) { return m && arr.indexOf(m) === i; });
const MACHINES = CFG.machines.concat(
    MACHINES_FROM_TEST.filter(function(m) { return CFG.machines.indexOf(m) === -1; }));
const MACHINE_OPTS = '<option value="">--</option>' +
    MACHINES.map(function(m) { return `<option value="${escHtml(m)}">${escHtml(m)}</option>`; }).join('');

function toggleMaterialComum() {
    const isComum = document.getElementById('materialComum').checked;
    document.querySelectorAll('.comp-row').forEach(function(row) {
        const typeSelect = row.querySelector('select[name^="comp_type_"]');
        const modelInput = row.querySelector('input[name^="comp_model_"]');
        const produtoIdInput = row.querySelector('input[name^="comp_product_id_"]');
        if (isComum) {
            if (typeSelect && !typeSelect.querySelector('option[value="outro"]')) {
                typeSelect.innerHTML = EXTRA_OPTS;
            }
            if (modelInput) modelInput.placeholder = 'Ex: I5-2400, 8GB...';
            if (produtoIdInput) produtoIdInput.value = '';
        } else {
            loadCatalogSelect(typeSelect, modelInput, produtoIdInput);
        }
    });
}

function loadCatalogSelect(typeSelect, modelInput, produtoIdInput) {
    if (!typeSelect) return;
    const currentType = typeSelect.value;
    const tiposCatalogo = [...new Set(produtosCatalogo.map(p => p.component_type))];
    const tipos = COMP_ORDER.filter(t => tiposCatalogo.includes(t));
    typeSelect.innerHTML = '<option value="">-- Selecione --</option>' +
        tipos.map(t => `<option value="${escHtml(t)}">${escHtml(COMP_LABELS[t] || t)}</option>`).join('');
    if (currentType) typeSelect.value = currentType;
    typeSelect.onchange = function() {
        updateModelOptions(typeSelect, modelInput, produtoIdInput);
    };
    if (currentType) updateModelOptions(typeSelect, modelInput, produtoIdInput);
}

function updateModelOptions(typeSelect, modelInput, produtoIdInput) {
    if (!modelInput || !typeSelect) return;
    const tipo = typeSelect.value;
    modelInput.onchange = function() {
        const v = (modelInput.value || '').trim();
        if (!v || !tipo) return;
        tentarAdicionarModelo(tipo, v, produtosCatalogo, modelInput, produtoIdInput);
    };
    const produtos = produtosCatalogo.filter(p => p.component_type === tipo);
    if (produtos.length === 0) {
        modelInput.placeholder = 'Modelo não encontrado no catálogo';
        modelInput.value = '';
        if (produtoIdInput) produtoIdInput.value = '';
        return;
    }
    const datalistId = 'datalist_' + typeSelect.name + '_' + Math.random().toString(36).substr(2, 9);
    let datalist = document.getElementById(datalistId);
    if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = datalistId;
        document.body.appendChild(datalist);
    }
    datalist.innerHTML = produtos.map(p => `<option value="${escHtml(p.model_name)}" data-id="${p.id}">${escHtml(p.model_name)}</option>`).join('');
    modelInput.setAttribute('list', datalistId);
    modelInput.placeholder = 'Selecione ou digite...';
    modelInput.oninput = function() {
        const match = produtos.find(p => p.model_name.toLowerCase() === modelInput.value.toLowerCase());
        if (produtoIdInput) produtoIdInput.value = match ? match.id : '';
    };
    const match = produtos.find(p => p.model_name.toLowerCase() === modelInput.value.toLowerCase());
    if (produtoIdInput) produtoIdInput.value = match ? match.id : '';
}

// "Equipamentos Mudados" (RMA, Serviço e NTB) também usa o catálogo de
// Produtos: ao escolher o componente, o Modelo passa a sugerir os modelos
// daquele tipo. Se o modelo digitado não existir no catálogo, o sistema
// pergunta se quer cadastrá-lo (peça trocada sai do estoque e precisa estar
// em Produtos). Aqui não se grava código do produto: muda só a sugestão.
let trocadoDatalistSeq = 0;

function initTrocadoCatalog(tr) {
    if (!tr) return;
    const typeSelect = tr.querySelector('select[name^="trocado_comp_type_"]');
    const modelInput = tr.querySelector('input[name^="trocado_comp_model_"]');
    if (!typeSelect || !modelInput) return;

    const aplicarSugestoes = function() {
        const tipo = typeSelect.value;
        modelInput.removeAttribute('list');
        if (!tipo) {
            modelInput.placeholder = 'Ex: I5-2400, 8GB...';
            return;
        }
        const produtos = produtosCatalogo.filter(function(p) {
            return p.component_type === tipo;
        });
        if (!produtos.length) {
            modelInput.placeholder = 'Digite o modelo (ainda não está em Produtos)';
            return;
        }
        trocadoDatalistSeq += 1;
        const datalistId = 'datalist_trocado_' + trocadoDatalistSeq;
        const datalist = document.createElement('datalist');
        datalist.id = datalistId;
        datalist.innerHTML = produtos.map(function(p) {
            return '<option value="' + escHtml(p.model_name) + '"></option>';
        }).join('');
        document.body.appendChild(datalist);
        modelInput.setAttribute('list', datalistId);
        modelInput.placeholder = 'Selecione ou digite...';
    };

    typeSelect.addEventListener('change', aplicarSugestoes);
    modelInput.addEventListener('change', function() {
        const modelo = (modelInput.value || '').trim();
        if (!modelo || !typeSelect.value) return;
        if (typeof window.tentarAdicionarModelo !== 'function') return;
        window.tentarAdicionarModelo(typeSelect.value, modelo, produtosCatalogo,
                                     modelInput, null);
    });
    aplicarSugestoes();
}

function syncDefectMachines() {
    const entries = [];
    document.querySelectorAll('input[name^="machine_name_"]').forEach(function(inp) {
        const m = inp.name.match(/^machine_name_(.+)/);
        const unit = m ? m[1] : '';
        const v = inp.value.trim();
        if (v) entries.push({ unit: unit, name: v });
    });
    const counts = {};
    entries.forEach(function(e) { counts[e.name] = (counts[e.name] || 0) + 1; });
    const names = entries.map(function(e) {
        return counts[e.name] > 1 ? e.name + ' (unid. ' + e.unit + ')' : e.name;
    });
    document.querySelectorAll('select[name="defect_maquina[]"]').forEach(function(sel) {
        const cur = sel.value;
        sel.innerHTML = '<option value="">--</option>' +
            names.map(n => `<option value="${escHtml(n)}">${escHtml(n)}</option>`).join('');
        if (cur) sel.value = cur;
    });
}

// Ao escolher Máquina + Componente no defeito, copia o Modelo da linha da
// máquina (mesmo modelo, sem limpar lá) e move o NS: ele vai pro defeito e a
// máquina fica com NS vazio pro novo componente.
function syncDefeitoNs(tr) {
    if (!tr) return;
    const selMaquina = tr.querySelector('select[name="defect_maquina[]"]');
    const selTipo = tr.querySelector('select[name="defect_type[]"]');
    const inpNs = tr.querySelector('input[name="defect_serial[]"]');
    const inpModelo = tr.querySelector('input[name="defect_model[]"]');
    if (!selMaquina || !selTipo || !inpNs) return;
    const nomeDefeito = selMaquina.value;
    const tipo = selTipo.value;
    if (!nomeDefeito || !tipo) return;

    let unit = null;
    document.querySelectorAll('input[name^="machine_name_"]').forEach(function(inp) {
        const m = inp.name.match(/^machine_name_(.+)$/);
        if (!m || unit !== null) return;
        const nomeMaq = (inp.value || '').trim();
        if (!nomeMaq) return;
        if (nomeDefeito === nomeMaq ||
            nomeDefeito === nomeMaq + ' (unid. ' + m[1] + ')') {
            unit = m[1];
        }
    });
    if (unit === null) return;

    const tipos = document.querySelectorAll('select[name="comp_type_' + unit + '[]"]');
    for (let i = 0; i < tipos.length; i++) {
        if (tipos[i].value !== tipo) continue;
        const linha = tipos[i].closest('tr');
        const serial = linha && linha.querySelector(
            'input[name="comp_serial_' + unit + '[]"]');
        const modelo = linha && linha.querySelector(
            'input[name="comp_model_' + unit + '[]"]');
        if (inpModelo && modelo && modelo.value.trim()) {
            inpModelo.value = modelo.value;
        }
        if (!serial || !serial.value.trim()) continue;
        inpNs.value = serial.value;
        serial.value = '';
        break;
    }
}

document.addEventListener('change', function(e) {
    const alvo = e.target;
    if (!alvo || !alvo.name) return;
    if (alvo.name === 'defect_maquina[]' || alvo.name === 'defect_type[]') {
        syncDefeitoNs(alvo.closest('tr'));
    }
    if (alvo.name === 'rma_test_machine[]' || alvo.name === 'rma_test_comp[]') {
        syncRmaTestFromEquip(alvo.closest('tr'));
    }
});

// Componentes registrados neste protocolo (máquinas, RMA e trocados).
function compRegistradosTipos() {
    const set = new Set();
    document.querySelectorAll(
        '#machinesContainer select[name^="comp_type_"], ' +
        '#rmaMachinesContainer select[name^="rma_comp_type_"], ' +
        '#rmaTrocadosContainer select[name^="trocado_comp_type_"]'
    ).forEach(function(sel) {
        if (sel.value) set.add(sel.value);
    });
    return set;
}

// Opções do select "Componente com Defeito": só o que está no protocolo
// (mais o valor já escolhido na linha, pra não perder dado salvo).
function defectOptsHtml(selected) {
    const set = compRegistradosTipos();
    if (selected) set.add(selected);
    const keys = COMP_ORDER.filter(function(k) { return set.has(k); });
    set.forEach(function(k) { if (keys.indexOf(k) === -1) keys.push(k); });
    let html = '<option value="">-- Selecione --</option>';
    keys.forEach(function(k) {
        html += `<option value="${escHtml(k)}"${selected === k ? ' selected' : ''}>` +
            `${escHtml(COMP_LABELS[k] || k)}</option>`;
    });
    return html;
}

function syncDefectTipos() {
    document.querySelectorAll('#defectsTable select[name="defect_type[]"]')
        .forEach(function(sel) {
            sel.innerHTML = defectOptsHtml(sel.value);
        });
}

let defectTiposPending = false;
function scheduleSyncDefectTipos() {
    if (defectTiposPending) return;
    defectTiposPending = true;
    setTimeout(function() {
        defectTiposPending = false;
        syncDefectTipos();
    }, 0);
}

document.addEventListener('change', function(e) {
    if (e.target && e.target.closest &&
        e.target.closest('#machinesContainer, #rmaMachinesContainer, #rmaTrocadosContainer')) {
        scheduleSyncDefectTipos();
    }
});
document.addEventListener('input', function(e) {
    if (e.target && e.target.name && e.target.name.indexOf('machine_name_') === 0) {
        syncDefectMachines();
    }
    if (e.target && e.target.name && e.target.name.indexOf('rma_machine_name_') === 0) {
        syncRmaTestMachines();
        if (typeof syncTrocadoMachines === 'function') syncTrocadoMachines();
    }
});

function syncRmaTestMachines() {
    const entries = [];
    document.querySelectorAll('input[name^="rma_machine_name_"]').forEach(function(inp) {
        const m = inp.name.match(/^rma_machine_name_(.+)/);
        const unit = m ? m[1] : '';
        const v = inp.value.trim();
        if (v) entries.push({ unit: unit, name: v });
    });
    const counts = {};
    entries.forEach(function(e) { counts[e.name] = (counts[e.name] || 0) + 1; });
    const names = entries.map(function(e) {
        return counts[e.name] > 1 ? e.name + ' (unid. ' + e.unit + ')' : e.name;
    });
    MACHINES_FROM_TEST.forEach(function(m) {
        if (names.indexOf(m) === -1) names.push(m);
    });
    document.querySelectorAll('select[name="rma_test_machine[]"]').forEach(function(sel) {
        const cur = sel.value;
        sel.innerHTML = '<option value="">--</option>' +
            names.map(n => `<option value="${escHtml(n)}">${escHtml(n)}</option>`).join('');
        if (cur) sel.value = cur;
    });
}

// No Teste de Mesa de RMA/Serviço/NTB, ao escolher Máquina + Componente,
// copia a Referência (Modelo) e o NS do "Equipamento do Cliente".
// É cópia, não recorte: os dados continuam na seção de origem.
// No NTB só vai a referência, porque o equipamento não foi comprado na TechBuy.
function syncRmaTestFromEquip(tr) {
    if (!tr) return;
    const selMaquina = tr.querySelector('select[name="rma_test_machine[]"]');
    const selTipo = tr.querySelector('select[name="rma_test_comp[]"]');
    const inpModelo = tr.querySelector('input[name="rma_test_model[]"]');
    const inpNs = tr.querySelector('input[name="rma_test_serial[]"]');
    if (!selMaquina || !selTipo || !inpModelo) return;
    const nomeMaquina = (selMaquina.value || '').trim();
    const tipo = selTipo.value;
    if (!nomeMaquina || !tipo) return;

    // Descobre a "unidade" (sufixo dos campos) comparando com os nomes das
    // máquinas do Equipamento do Cliente, inclusive o sufixo " (unid. XX)".
    // A comparação ignora maiúsculas/minúsculas porque protocolos antigos
    // gravaram "computador 01" e o equipamento pode estar "Computador 01".
    const nomeMin = nomeMaquina.toLowerCase();
    let unit = null;
    document.querySelectorAll('input[name^="rma_machine_name_"]').forEach(function(inp) {
        if (unit !== null) return;
        const m = inp.name.match(/^rma_machine_name_(.+)$/);
        if (!m) return;
        const nomeMaq = (inp.value || '').trim();
        if (!nomeMaq) return;
        if (nomeMin === nomeMaq.toLowerCase() ||
            nomeMin === (nomeMaq + ' (unid. ' + m[1] + ')').toLowerCase()) {
            unit = m[1];
        }
    });
    if (unit === null) return;

    // Pode haver mais de uma linha com o mesmo componente (ex.: dois SSDs).
    // Prefere a que tem NS, depois a que tem modelo; senão usa a primeira.
    const tipos = document.querySelectorAll(
        '#rmaMachinesContainer select[name="rma_comp_type_' + unit + '[]"]');
    const candidatas = [];
    for (let i = 0; i < tipos.length; i++) {
        if (tipos[i].value !== tipo) continue;
        const linha = tipos[i].closest('tr');
        if (linha) candidatas.push(linha);
    }
    if (!candidatas.length) return;

    const querNs = rmaTestHasNs();
    const modeloDe = function(linha) {
        const inp = linha.querySelector(
            'input[name="rma_comp_model_' + unit + '[]"]');
        return inp ? inp.value.trim() : '';
    };
    const serialDe = function(linha) {
        const inp = linha.querySelector(
            'input[name="rma_comp_serial_' + unit + '[]"]');
        return inp ? inp.value.trim() : '';
    };
    let escolhida = candidatas[0];
    for (let i = 0; i < candidatas.length; i++) {
        if (querNs && serialDe(candidatas[i])) { escolhida = candidatas[i]; break; }
    }
    if (!querNs || !serialDe(escolhida)) {
        for (let i = 0; i < candidatas.length; i++) {
            if (modeloDe(candidatas[i])) { escolhida = candidatas[i]; break; }
        }
    }

    // Espelha o que está no equipamento: se lá estiver vazio, aqui também fica.
    inpModelo.value = modeloDe(escolhida);
    if (inpNs && querNs) {
        inpNs.value = serialDe(escolhida);
    }
}

let machineCount = 0;
let rmaMachineCount = 0;

function currentProtocolType() {
    const sel = document.getElementById('protocolType');
    return sel ? sel.value : (CFG.protocolType || '');
}

function isPontaEntregaType() {
    return currentProtocolType() === 'ponta_entrega';
}

function materialComumAtivo() {
    const el = document.getElementById('materialComum');
    return !!(el && el.checked);
}

function machineIsPE(block) {
    if (!block) return false;
    if (isPontaEntregaType()) return true;
    const cb = block.querySelector('input[name^="pe_switch_"]');
    return !!(cb && cb.checked);
}

function nsOpcionalNoBloco(block) {
    // O NS é obrigatório na venda normal e na Pronta-Entrega.
    // Só na venda a máquina marcada como PE pode ficar sem NS (é o NS de referência).
    return currentProtocolType() === 'venda' && machineIsPE(block);
}

function refData(map, n) {
    const item = (map || {})[n];
    if (!item) return {};
    return (typeof item === 'string') ? { text: item } : item;
}

function peRefStatusHTML(info) {
    if (!info || !info.protocol_id) {
        return '<span class="text-secondary">Nenhuma Pronta-Entrega vinculada.</span>';
    }
    const nome = info.machine_name ? ' (' + escHtml(info.machine_name) + ')' : '';
    return '<i class="bi bi-link-45deg"></i> Vinculada a ' +
        '<a href="/protocolos/' + info.protocol_id + '" target="_blank" class="text-info">' +
        escHtml(info.protocol_number) + ' · Nº ' + escHtml(info.unit) + nome + '</a>' +
        (info.fonte ? ' · fonte <code>' + escHtml(info.fonte) + '</code>' : '');
}

function machineHTML(num, name, isPrebuilt, powerCableVal) {
    const n = String(num).padStart(2, '0');
    const label = name || `Máquina ${n}`;
    const checked = isPrebuilt ? 'checked' : '';
    const pcVal = powerCableVal || 'OK';
    const saleRef = refData(CFG.saleRefs, n);
    const peRef = refData(CFG.peRefs, n);
    const peRefJson = peRef.protocol_id ? JSON.stringify(peRef) : '';
    const switchDisplay = isPontaEntregaType() ? 'display:none' : '';
    const saleRefDisplay = isPontaEntregaType() ? '' : 'display:none';
    return `
    <div class="card bg-dark border-secondary mb-3 machine-block" data-machine="${n}">
        <div class="card-header d-flex justify-content-between align-items-center py-2 flex-wrap gap-2">
            <div class="d-flex align-items-center gap-3 flex-wrap">
                <span class="badge bg-secondary machine-number" title="Número deste bloco de máquina">Nº ${n}</span>
                <input type="text" name="machine_name_${n}" class="form-control form-control-sm bg-dark text-light border-secondary fw-bold" style="width:auto;min-width:200px;display:inline-block" value="${escHtml(label)}">
                <div class="form-check form-switch mb-0 pe-switch-wrap" style="${switchDisplay}">
                    <input class="form-check-input" type="checkbox" id="peSwitch_${n}" name="pe_switch_${n}" ${checked} onchange="togglePE(this)">
                    <label class="form-check-label small text-secondary" for="peSwitch_${n}">Pronta-Entrega</label>
                </div>
                <div class="d-flex align-items-center gap-1">
                    <span class="small text-secondary">Cabo de Força:</span>
                    <select name="machine_power_cable_${n}" class="form-select form-select-sm bg-dark text-light border-secondary" style="width:auto;">
                        <option value="OK" ${pcVal === 'OK' ? 'selected' : ''}>OK</option>
                        <option value="Foi sem Cabo de Força" ${pcVal === 'Foi sem Cabo de Força' || pcVal === 'Vai sem cabo de força' ? 'selected' : ''}>Foi sem Cabo de Força</option>
                    </select>
                </div>
            </div>
            <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeMachine(this)">
                <i class="bi bi-x-lg"></i>
            </button>
        </div>
        <div class="card-body p-2">
            <div class="pe-sale-ref mb-2" style="${saleRefDisplay}">
                <label class="form-label small text-secondary mb-1"><i class="bi bi-receipt"></i> Referência de Venda <span class="text-muted">(automática; pode editar)</span></label>
                <input type="text" name="sale_ref_${n}" class="form-control form-control-sm" placeholder="Ex: PRO-2026-0199 · Cliente · 03/11/2026" value="${escHtml(saleRef.text || '')}">
                <input type="hidden" name="sale_ref_id_${n}" value="${saleRef.sale_id || ''}">
                <input type="hidden" name="sale_ref_number_${n}" value="${escHtml(saleRef.sale_number || '')}">
            </div>
            <div class="pe-link-panel mb-2 p-2 border border-info rounded" style="display:none">
                <label class="form-label small text-info mb-1"><i class="bi bi-link-45deg"></i> Pronta-Entrega de origem</label>
                <div class="d-flex gap-1 flex-wrap align-items-center">
                    <input type="text" class="form-control form-control-sm pe-ns-input" style="max-width:230px" placeholder="NS da fonte (ex: 158418)" value="${escHtml(peRef.fonte || '')}">
                    <button type="button" class="btn btn-sm btn-outline-info" onclick="buscarPE(this)"><i class="bi bi-search"></i> Buscar</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary pe-change-btn" onclick="limparPE(this)" style="${peRefJson ? '' : 'display:none'}">Trocar</button>
                </div>
                <div class="pe-ref-status small mt-1">${peRefStatusHTML(peRef)}</div>
                <div class="pe-result mt-1"></div>
                <input type="hidden" name="pe_ref_json_${n}" class="pe-ref-json" value="${escHtml(peRefJson)}">
            </div>
            <table class="table table-dark table-sm mb-0">
                <thead>
                    <tr>
                        <th style="width:22%">Componente</th>
                        <th style="width:28%">Modelo</th>
                        <th style="width:40%">Nº de Série</th>
                        <th style="width:10%"></th>
                    </tr>
                </thead>
                <tbody class="machine-body">
                </tbody>
            </table>
            <button type="button" class="btn btn-sm btn-outline-success mt-2" onclick="addCompRow(this)">
                <i class="bi bi-plus"></i> Componente
            </button>
            <button type="button" class="btn btn-sm btn-outline-info mt-2 ms-1" onclick="replicateMachine(this)">
                <i class="bi bi-copy"></i> Replicar
            </button>
        </div>
    </div>`;
}

function rmaMachineHTML(num, name) {
    const n = String(num).padStart(2, '0');
    const label = name || `Computador ${n}`;
    return `
    <div class="card bg-dark border-secondary mb-3 rma-machine-block" data-rma-machine="${n}">
        <div class="card-header d-flex justify-content-between align-items-center py-2">
            <input type="text" name="rma_machine_name_${n}" class="form-control form-control-sm bg-dark text-light border-secondary fw-bold" style="width:auto;min-width:200px;display:inline-block" value="${escHtml(label)}">
            <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeRmaMachine(this)">
                <i class="bi bi-x-lg"></i>
            </button>
        </div>
        <div class="card-body p-2">
            <table class="table table-dark table-sm mb-0">
                <thead>
                    <tr>
                        <th style="width:22%">Componente</th>
                        <th style="width:28%">Modelo</th>
                        <th style="width:40%">Nº de Série</th>
                        <th style="width:10%"></th>
                    </tr>
                </thead>
                <tbody class="rma-machine-body">
                </tbody>
            </table>
            <button type="button" class="btn btn-sm btn-outline-success mt-2" onclick="addRmaCompRow(this)">
                <i class="bi bi-plus"></i> Componente
            </button>
            <button type="button" class="btn btn-sm btn-outline-info mt-2 ms-1" onclick="replicateRmaMachine(this)">
                <i class="bi bi-copy"></i> Replicar
            </button>
        </div>
    </div>`;
}

function addMachine() {
    const container = document.getElementById('machinesContainer');
    const blocks = container.querySelectorAll('.machine-block');
    const used = new Set();
    blocks.forEach(function(b) { used.add(parseInt(b.dataset.machine, 10)); });
    let next = 1;
    while (used.has(next)) next++;
    if (next > machineCount) machineCount = next;
    container.insertAdjacentHTML('beforeend', machineHTML(next));
    syncDefectMachines();
}

function replicateMachine(btn) {
    const srcBlock = btn.closest('.machine-block');
    const srcMachine = srcBlock.dataset.machine;
    const container = document.getElementById('machinesContainer');
    const blocks = container.querySelectorAll('.machine-block');
    const used = new Set();
    blocks.forEach(function(b) { used.add(parseInt(b.dataset.machine, 10)); });
    let next = 1;
    while (used.has(next)) next++;
    if (next > machineCount) machineCount = next;
    const isPE = machineIsPE(srcBlock);
    const srcPcSel = srcBlock.querySelector('select[name^="machine_power_cable_"]');
    const pcVal = srcPcSel ? srcPcSel.value : 'OK';
    container.insertAdjacentHTML('beforeend', machineHTML(next, null, isPE, pcVal));
    const dstBlock = container.lastElementChild;
    const dstMachine = dstBlock.dataset.machine;
    const dstCb = dstBlock.querySelector('.form-check-input');
    if (isPE && dstCb) dstCb.checked = true;
    const dstTbody = dstBlock.querySelector('.machine-body');
    const srcRows = srcBlock.querySelectorAll('.machine-body .comp-row');
    srcRows.forEach(function(row) {
        const tr = document.createElement('tr');
        tr.className = 'comp-row';
        const srcSelect = row.querySelector('select');
        const srcModel = row.querySelector('input[name^="comp_model_"]');
        const srcProductId = row.querySelector('input[name^="comp_product_id_"]');
        const serial = '';
        const nsOpcional = nsOpcionalNoBloco(srcBlock);
        const showBtn = (nsOpcional && !serial) ? '' : 'style="display:none"';
        const showInput = (!nsOpcional || serial) ? '' : 'style="display:none"';
        tr.innerHTML = `
            <td>
                <select name="comp_type_${dstMachine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select>
                <input type="hidden" name="comp_product_id_${dstMachine}[]" value="${escHtml(srcProductId ? srcProductId.value : '')}">
            </td>
            <td><input type="text" name="comp_model_${dstMachine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(srcModel ? srcModel.value : '')}"></td>
            <td>
                <div class="d-flex align-items-center gap-1">
                    <button type="button" class="btn btn-sm btn-outline-warning pe-ref-btn py-0 px-1" ${showBtn} onclick="addRefSerial(this)" title="Adicionar NS de referência"><i class="bi bi-plus-lg"></i></button>
                    <input type="text" name="comp_serial_${dstMachine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${escHtml(serial)}">
                    <button type="button" class="btn btn-sm btn-outline-danger remove-ref-btn py-0 px-1" onclick="removeRefSerial(this)" title="Remover NS" style="display:none"><i class="bi bi-x"></i></button>
                </div>
            </td>
            <td class="text-nowrap">
                <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, -1)" title="Mover pra cima"><i class="bi bi-arrow-up"></i></button>
                <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, 1)" title="Mover pra baixo"><i class="bi bi-arrow-down"></i></button>
                <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="this.closest('tr').remove()" title="Remover"><i class="bi bi-x"></i></button>
            </td>
        `;
        const select = tr.querySelector('select');
        const modelInput = tr.querySelector('input[name^="comp_model_"]');
        const modeloOriginal = srcModel ? srcModel.value : '';
        const tipoOriginal = srcSelect ? srcSelect.value : '';
        select.value = tipoOriginal;
        if (!materialComumAtivo() && produtosCatalogo.length > 0) {
            loadCatalogSelect(select, modelInput, tr.querySelector('input[name^="comp_product_id_"]'));
            if (select.value !== tipoOriginal) {
                select.innerHTML = EXTRA_OPTS;
                select.value = tipoOriginal;
            }
            // Mantém o modelo copiado mesmo que o tipo não esteja no catálogo.
            if (!modelInput.value && modeloOriginal) modelInput.value = modeloOriginal;
        }
        dstTbody.appendChild(tr);
    });
    if (isPE && dstCb) togglePE(dstCb);
    syncDefectMachines();
}

function removeMachine(btn) {
    btn.closest('.machine-block').remove();
    syncDefectMachines();
}

function addRmaMachine() {
    const container = document.getElementById('rmaMachinesContainer');
    const blocks = container.querySelectorAll('.rma-machine-block');
    const used = new Set();
    blocks.forEach(function(b) { used.add(parseInt(b.dataset.rmaMachine, 10)); });
    let next = 1;
    while (used.has(next)) next++;
    if (next > rmaMachineCount) rmaMachineCount = next;
    container.insertAdjacentHTML('beforeend', rmaMachineHTML(next));
    syncRmaTestMachines();
}

function removeRmaMachine(btn) {
    btn.closest('.rma-machine-block').remove();
    syncRmaTestMachines();
}

function addRmaCompRow(btn) {
    const block = btn.closest('.rma-machine-block');
    const machine = block.dataset.rmaMachine;
    const tbody = block.querySelector('.rma-machine-body');
    const tr = document.createElement('tr');
    tr.className = 'comp-row';
    tr.innerHTML = `
        <td><select name="rma_comp_type_${machine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
        <td><input type="text" name="rma_comp_model_${machine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..."></td>
        <td>
            <div class="d-flex align-items-center gap-1">
                <button type="button" class="btn btn-sm btn-outline-warning rma-ref-btn py-0 px-1" onclick="addRmaRefSerial(this)" title="Adicionar NS"><i class="bi bi-plus-lg"></i></button>
                <input type="text" name="rma_comp_serial_${machine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" style="display:none">
                <button type="button" class="btn btn-sm btn-outline-danger remove-ref-btn py-0 px-1" onclick="removeRmaRefSerial(this)" title="Remover NS" style="display:none"><i class="bi bi-x"></i></button>
            </div>
        </td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
    `;
    tbody.appendChild(tr);
}

function addRmaRefSerial(btn) {
    btn.style.display = 'none';
    const div = btn.parentElement;
    div.querySelector('.serial-input').style.display = '';
    div.querySelector('.remove-ref-btn').style.display = '';
    div.querySelector('.serial-input').focus();
}

function removeRmaRefSerial(btn) {
    const div = btn.parentElement;
    div.querySelector('.serial-input').value = '';
    div.querySelector('.serial-input').style.display = 'none';
    div.querySelector('.remove-ref-btn').style.display = 'none';
    div.querySelector('.rma-ref-btn').style.display = '';
}

function replicateRmaMachine(btn) {
    const srcBlock = btn.closest('.rma-machine-block');
    const srcMachine = srcBlock.dataset.rmaMachine;
    const container = document.getElementById('rmaMachinesContainer');
    const blocks = container.querySelectorAll('.rma-machine-block');
    const used = new Set();
    blocks.forEach(function(b) { used.add(parseInt(b.dataset.rmaMachine, 10)); });
    let next = 1;
    while (used.has(next)) next++;
    if (next > rmaMachineCount) rmaMachineCount = next;
    container.insertAdjacentHTML('beforeend', rmaMachineHTML(next));
    const dstBlock = container.lastElementChild;
    const dstMachine = dstBlock.dataset.rmaMachine;
    const dstTbody = dstBlock.querySelector('.rma-machine-body');
    const srcRows = srcBlock.querySelectorAll('.rma-machine-body .comp-row');
        srcRows.forEach(function(row) {
            const tr = document.createElement('tr');
            tr.className = 'comp-row';
            const srcSelect = row.querySelector('select');
            const srcModel = row.querySelector('input[name^="rma_comp_model_"]');
            const serial = '';
            const hasSerial = serial ? true : false;
            const showBtn = hasSerial ? 'style="display:none"' : '';
            const showInput = hasSerial ? '' : 'style="display:none"';
            tr.innerHTML = `
                <td><select name="rma_comp_type_${dstMachine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
                <td><input type="text" name="rma_comp_model_${dstMachine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(srcModel ? srcModel.value : '')}"></td>
                <td>
                    <div class="d-flex align-items-center gap-1">
                        <button type="button" class="btn btn-sm btn-outline-warning rma-ref-btn py-0 px-1" ${showBtn} onclick="addRmaRefSerial(this)" title="Adicionar NS"><i class="bi bi-plus-lg"></i></button>
                        <input type="text" name="rma_comp_serial_${dstMachine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${escHtml(serial)}">
                        <button type="button" class="btn btn-sm btn-outline-danger remove-ref-btn py-0 px-1" onclick="removeRmaRefSerial(this)" title="Remover NS" style="display:none"><i class="bi bi-x"></i></button>
                    </div>
                </td>
                <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
            `;
            const select = tr.querySelector('select');
            select.value = srcSelect ? srcSelect.value : '';
            dstTbody.appendChild(tr);
        });
}

function rmaTestHasNs() {
    const sel = document.getElementById('protocolType');
    return sel ? sel.value === 'rma' || sel.value === 'servico' : false;
}

function rmaTestHasOrigemTechBuy() {
    return rmaTestHasNs();
}

function updateRmaTestNsColumns() {
    const showNs = rmaTestHasNs();
    const showOrigem = rmaTestHasOrigemTechBuy();
    const header = document.getElementById('rmaTestNsHeader');
    if (header) header.style.display = showNs ? '' : 'none';
    document.querySelectorAll('#rmaTestTable .rma-test-ns-cell').forEach(function(c) {
        c.style.display = showNs ? '' : 'none';
    });
    ['rmaTestPedidoHeader', 'rmaTestDataCompraHeader'].forEach(function(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = showOrigem ? '' : 'none';
    });
    document.querySelectorAll('#rmaTestTable .rma-test-origem-cell').forEach(function(c) {
        c.style.display = showOrigem ? '' : 'none';
        c.querySelectorAll('input').forEach(function(inp) {
            inp.disabled = !showOrigem;
            if (!showOrigem) inp.value = '';
        });
    });
}

function currentRmaMachineOpts() {
    const entries = [];
    document.querySelectorAll('input[name^="rma_machine_name_"]').forEach(function(inp) {
        const m = inp.name.match(/^rma_machine_name_(.+)/);
        const unit = m ? m[1] : '';
        const v = inp.value.trim();
        if (v) entries.push({ unit: unit, name: v });
    });
    const counts = {};
    entries.forEach(function(e) { counts[e.name] = (counts[e.name] || 0) + 1; });
    const names = entries.map(function(e) {
        return counts[e.name] > 1 ? e.name + ' (unid. ' + e.unit + ')' : e.name;
    });
    MACHINES_FROM_TEST.forEach(function(m) {
        if (names.indexOf(m) === -1) names.push(m);
    });
    return '<option value="">--</option>' +
        names.map(n => `<option value="${escHtml(n)}">${escHtml(n)}</option>`).join('');
}

function addRmaTestRow() {
    const tbody = document.querySelector('#rmaTestTable tbody');
    const opts = '<option value="">-- Selecione --</option>' +
        Object.entries(COMP_LABELS).map(([k, v]) => `<option value="${escHtml(k)}">${escHtml(v)}</option>`).join('');
    const tr = document.createElement('tr');
    tr.className = 'rma-test-row';
    tr.innerHTML = `
        <td><select name="rma_test_machine[]" class="form-select form-select-sm">${currentRmaMachineOpts()}</select></td>
        <td><select name="rma_test_comp[]" class="form-select form-select-sm">${opts}</select></td>
        <td><input type="text" name="rma_test_model[]" class="form-control form-control-sm" placeholder="Ex: I5-2400"></td>
        <td class="rma-test-ns-cell" style="display:${rmaTestHasNs() ? '' : 'none'}"><input type="text" name="rma_test_serial[]" class="form-control form-control-sm" placeholder="Nº de Série"></td>
        <td><input type="text" name="rma_test_defeito[]" class="form-control form-control-sm" placeholder="Descrição do defeito"></td>
        <td class="rma-test-origem-cell" style="display:${rmaTestHasOrigemTechBuy() ? '' : 'none'}"><input type="text" name="rma_test_pedido[]" class="form-control form-control-sm" placeholder="Pedido"${rmaTestHasOrigemTechBuy() ? '' : ' disabled'}></td>
        <td class="rma-test-origem-cell" style="display:${rmaTestHasOrigemTechBuy() ? '' : 'none'}"><input type="text" name="rma_test_data_compra[]" class="form-control form-control-sm date-mask" placeholder="DD/MM/AAAA"${rmaTestHasOrigemTechBuy() ? '' : ' disabled'}></td>
        <td>
            <select name="rma_test_status[]" class="form-select form-select-sm">
                <option value=\"\">--</option>
                ${STATUS_OPTS}
            </select>
        </td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
    `;
    tbody.appendChild(tr);
    if (window.initDateMask) initDateMask(tr);
}

let trocadoMachineCount = 0;

function currentTrocadoMachineOpts(selected) {
    const names = [];
    document.querySelectorAll('input[name^="rma_machine_name_"]').forEach(function(inp) {
        const v = inp.value.trim();
        if (v && names.indexOf(v) === -1) names.push(v);
    });
    document.querySelectorAll('input[name^="trocado_machine_name_"]').forEach(function(inp) {
        const v = inp.value.trim();
        if (v && names.indexOf(v) === -1) names.push(v);
    });
    if (selected && names.indexOf(selected) === -1) names.push(selected);
    if (!names.length) names.push('Computador 01');
    return '<option value="">--</option>' +
        names.map(n => `<option value="${escHtml(n)}"${n === selected ? ' selected' : ''}>${escHtml(n)}</option>`).join('');
}

function syncTrocadoMachines() {
    document.querySelectorAll('#rmaTrocadosContainer select[name="trocado_row_machine[]"]').forEach(function(sel) {
        const cur = sel.value;
        sel.innerHTML = currentTrocadoMachineOpts(cur);
        if (cur) sel.value = cur;
    });
}

function trocadoMachineHTML(num, name) {
    const n = String(num).padStart(2, '0');
    const label = name || `Computador ${n}`;
    return `
    <div class="card bg-dark border-secondary mb-3 trocado-machine-block" data-trocado-machine="${n}">
        <div class="card-header d-flex justify-content-between align-items-center py-2">
            <input type="text" name="trocado_machine_name_${n}" class="form-control form-control-sm bg-dark text-light border-secondary fw-bold" style="width:auto;min-width:200px;display:inline-block" value="${escHtml(label)}" oninput="syncTrocadoMachines()">
            <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeTrocadoMachine(this)">
                <i class="bi bi-x-lg"></i>
            </button>
        </div>
        <div class="card-body p-2">
            <table class="table table-dark table-sm mb-0">
                <thead>
                    <tr>
                        <th style="width:16%">Máquina</th>
                        <th style="width:18%">Componente</th>
                        <th style="width:24%">Modelo</th>
                        <th style="width:32%">Nº de Série</th>
                        <th style="width:10%"></th>
                    </tr>
                </thead>
                <tbody class="trocado-machine-body">
                </tbody>
            </table>
            <button type="button" class="btn btn-sm btn-outline-success mt-2" onclick="addTrocadoCompRow(this)">
                <i class="bi bi-plus"></i> Componente
            </button>
            <button type="button" class="btn btn-sm btn-outline-info mt-2 ms-1" onclick="replicateTrocadoMachine(this)">
                <i class="bi bi-copy"></i> Replicar
            </button>
        </div>
    </div>`;
}

function addTrocadoMachine() {
    const container = document.getElementById('rmaTrocadosContainer');
    const blocks = container.querySelectorAll('.trocado-machine-block');
    const used = new Set();
    blocks.forEach(function(b) { used.add(parseInt(b.dataset.trocadoMachine, 10)); });
    let next = 1;
    while (used.has(next)) next++;
    if (next > trocadoMachineCount) trocadoMachineCount = next;
    container.insertAdjacentHTML('beforeend', trocadoMachineHTML(next));
}

function removeTrocadoMachine(btn) {
    btn.closest('.trocado-machine-block').remove();
}

function addTrocadoCompRow(btn, presetMachine) {
    const block = btn.closest('.trocado-machine-block');
    const machine = block.dataset.trocadoMachine;
    const nameInput = block.querySelector('input[name^="trocado_machine_name_"]');
    const cardName = nameInput ? nameInput.value.trim() : ('Computador ' + machine);
    const tbody = block.querySelector('.trocado-machine-body');
    const tr = document.createElement('tr');
    tr.className = 'comp-row';
    tr.innerHTML = `
        <td><select name="trocado_row_machine[]" class="form-select form-select-sm">${currentTrocadoMachineOpts(presetMachine || cardName)}</select></td>
        <td><select name="trocado_comp_type_${machine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
        <td><input type="text" name="trocado_comp_model_${machine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..."></td>
        <td><input type="text" name="trocado_comp_serial_${machine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" minlength="3"></td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
    `;
    tbody.appendChild(tr);
    initTrocadoCatalog(tr);
}

function replicateTrocadoMachine(btn) {
    const srcBlock = btn.closest('.trocado-machine-block');
    const srcMachine = srcBlock.dataset.trocadoMachine;
    const container = document.getElementById('rmaTrocadosContainer');
    const blocks = container.querySelectorAll('.trocado-machine-block');
    const used = new Set();
    blocks.forEach(function(b) { used.add(parseInt(b.dataset.trocadoMachine, 10)); });
    let next = 1;
    while (used.has(next)) next++;
    if (next > trocadoMachineCount) trocadoMachineCount = next;
    container.insertAdjacentHTML('beforeend', trocadoMachineHTML(next));
    const dstBlock = container.lastElementChild;
    const dstMachine = dstBlock.dataset.trocadoMachine;
    const dstTbody = dstBlock.querySelector('.trocado-machine-body');
    const srcRows = srcBlock.querySelectorAll('.trocado-machine-body .comp-row');
    const dstNameInput = dstBlock.querySelector('input[name^="trocado_machine_name_"]');
    const dstName = dstNameInput ? dstNameInput.value.trim() : ('Computador ' + dstMachine);
    srcRows.forEach(function(row) {
        const tr = document.createElement('tr');
        tr.className = 'comp-row';
        const srcTypeSel = row.querySelector('select[name^="trocado_comp_type_"]');
        const srcMachSel = row.querySelector('select[name="trocado_row_machine[]"]');
        const srcModel = row.querySelector('input[name^="trocado_comp_model_"]');
        const serial = '';
        tr.innerHTML = `
            <td><select name="trocado_row_machine[]" class="form-select form-select-sm">${currentTrocadoMachineOpts(dstName)}</select></td>
            <td><select name="trocado_comp_type_${dstMachine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
            <td><input type="text" name="trocado_comp_model_${dstMachine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(srcModel ? srcModel.value : '')}"></td>
            <td><input type="text" name="trocado_comp_serial_${dstMachine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" minlength="3" value="${escHtml(serial)}"></td>
            <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
        `;
        const selects = tr.querySelectorAll('select');
        if (selects[1]) selects[1].value = srcTypeSel ? srcTypeSel.value : '';
        dstTbody.appendChild(tr);
        initTrocadoCatalog(tr);
    });
}

function loadTrocadoMachines(data) {
    if (!data || Object.keys(data).length === 0) {
        addTrocadoMachine();
        return;
    }
    const container = document.getElementById('rmaTrocadosContainer');
    container.innerHTML = '';
    const machines = Object.keys(data).sort();
    let maxM = 0;
    machines.forEach(function(m) {
        const num = parseInt(m, 10);
        if (!isNaN(num) && num > maxM) maxM = num;
        const entry = data[m];
        const machineName = entry.name || null;
        const comps = entry.components || entry || [];
        container.insertAdjacentHTML('beforeend', trocadoMachineHTML(num, machineName));
        const block = container.lastElementChild;
        const tbody = block.querySelector('.trocado-machine-body');
        comps.forEach(function(item) {
            const tr = document.createElement('tr');
            tr.className = 'comp-row';
            tr.innerHTML = `
                <td><select name="trocado_row_machine[]" class="form-select form-select-sm">${currentTrocadoMachineOpts(entry.name || null)}</select></td>
                <td><select name="trocado_comp_type_${m}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
                <td><input type="text" name="trocado_comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(item.model)}"></td>
                <td><input type="text" name="trocado_comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" minlength="3" value="${escHtml(item.serial)}"></td>
                <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
            `;
            const selects = tr.querySelectorAll('select');
            if (selects[1]) selects[1].value = item.type || '';
            tbody.appendChild(tr);
            initTrocadoCatalog(tr);
        });
    });
    trocadoMachineCount = maxM || 0;
    if (trocadoMachineCount === 0) addTrocadoMachine();
}

function refreshPESerialRows(block) {
    const nsOpcional = nsOpcionalNoBloco(block);
    block.querySelectorAll('.comp-row').forEach(function(row) {
        const btn = row.querySelector('.pe-ref-btn');
        const input = row.querySelector('.serial-input');
        if (!input || !btn) return;
        if (nsOpcional) {
            if (input.value) {
                btn.style.display = 'none';
                input.style.display = '';
            } else {
                btn.style.display = '';
                input.style.display = 'none';
            }
        } else {
            btn.style.display = 'none';
            input.style.display = '';
        }
    });
}

function syncVendaPeTop() {
    if (currentProtocolType() !== 'venda') return;
    const top = document.getElementById('vendaPe');
    if (!top) return;
    const blocks = Array.from(document.querySelectorAll('.machine-block'));
    const anyPE = blocks.some(function(b) { return machineIsPE(b); });
    const anyLink = Array.from(document.querySelectorAll('.pe-ref-json')).some(function(i) { return i.value; });
    if (anyPE || anyLink) {
        top.checked = true;
    }
}

function syncPEMachineUI() {
    const type = currentProtocolType();
    document.querySelectorAll('.machine-block').forEach(function(block) {
        const wrap = block.querySelector('.pe-switch-wrap');
        if (wrap) wrap.style.display = (type === 'ponta_entrega') ? 'none' : '';
        const saleRef = block.querySelector('.pe-sale-ref');
        if (saleRef) saleRef.style.display = (type === 'ponta_entrega') ? 'block' : 'none';
        const panel = block.querySelector('.pe-link-panel');
        if (panel) {
            panel.style.display = (type === 'venda' && machineIsPE(block)) ? 'block' : 'none';
        }
        refreshPESerialRows(block);
    });
    syncVendaPeTop();
}

function togglePE(cb) {
    const block = cb.closest('.machine-block');
    const panel = block.querySelector('.pe-link-panel');
    if (panel) {
        panel.style.display = (currentProtocolType() === 'venda' && cb.checked) ? 'block' : 'none';
    }
    refreshPESerialRows(block);
    if (cb.checked) {
        syncVendaPeTop();
    } else {
        const anyPE = Array.from(document.querySelectorAll('.machine-block')).some(function(b) { return machineIsPE(b); });
        const anyLink = Array.from(document.querySelectorAll('.pe-ref-json')).some(function(i) { return i.value; });
        const top = document.getElementById('vendaPe');
        if (top && !anyPE && !anyLink) top.checked = false;
    }
}

function updatePERefStatus(block, info) {
    const status = block.querySelector('.pe-ref-status');
    if (status) status.innerHTML = peRefStatusHTML(info);
}

function peResultHTML(r) {
    const comps = (r.components || []).map(function(c) {
        return '<div>' + escHtml(c.label || c.type) + ': <strong>' + escHtml(c.model || '-') +
            '</strong> <span class="text-secondary">NS ' + escHtml(c.serial || '—') + '</span></div>';
    }).join('');
    const vendida = (r.vendida || []).map(function(v) {
        return '<div class="text-danger"><i class="bi bi-exclamation-triangle"></i> Já saiu na venda ' +
            escHtml(v.protocol_number) + ' — ' + escHtml(v.client_name || 'sem cliente') +
            ' ' + escHtml(v.date || '') + '</div>';
    }).join('');
    const dados = escHtml(JSON.stringify(r));
    return '<div class="border border-secondary rounded p-2 mt-1">' +
        '<div class="fw-bold">' + escHtml(r.protocol_number) + ' · Nº ' + escHtml(r.unit) +
        (r.machine_name ? ' · ' + escHtml(r.machine_name) : '') + '</div>' +
        '<div class="text-secondary small">Fonte: <code>' + escHtml(r.fonte || '—') + '</code></div>' +
        '<div class="small mt-1">' + comps + '</div>' + vendida +
        '<div class="mt-2 d-flex gap-1 flex-wrap">' +
        '<button type="button" class="btn btn-sm btn-success" data-pe="' + dados + '" onclick="aplicarPE(this, \'tudo\')">Trazer tudo (peças + NS)</button>' +
        '<button type="button" class="btn btn-sm btn-outline-success" data-pe="' + dados + '" onclick="aplicarPE(this, \'fonte\')">Só o NS da fonte</button>' +
        '<a class="btn btn-sm btn-outline-info" href="/protocolos/' + r.protocol_id + '" target="_blank">Abrir PE</a>' +
        '</div></div>';
}

function renderPEResultados(container, resultados) {
    if (!resultados || !resultados.length) {
        container.innerHTML = '<div class="text-warning">Nenhuma Pronta-Entrega encontrada. Confira o NS da fonte ou registre a PE primeiro.</div>';
        return;
    }
    container.innerHTML = resultados.map(peResultHTML).join('');
}

function buscarPE(btn) {
    const block = btn.closest('.machine-block');
    const input = block.querySelector('.pe-ns-input');
    const result = block.querySelector('.pe-result');
    const termo = (input ? input.value : '').trim();
    if (!termo) {
        result.innerHTML = '<div class="text-warning">Digite o NS da fonte (ou o número da PE).</div>';
        return;
    }
    const params = new URLSearchParams();
    const m = termo.match(/^(PRO[-\s]?\d{4}[-\s]?\d{1,4})(?:[\s\/\-]+(\d{1,2}))?$/i);
    if (m) {
        params.set('pe', m[1].replace(/\s+/g, '-'));
        if (m[2]) params.set('unit', m[2]);
    } else {
        params.set('ns', termo);
    }
    if (CFG.protocolId && currentProtocolType() === 'venda') params.set('venda_id', CFG.protocolId);
    result.innerHTML = '<div class="text-secondary">Buscando...</div>';
    const url = '/protocolos/api/pronta-entrega/buscar?' + params.toString();
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.resultados && data.resultados.length) {
                renderPEResultados(result, data.resultados);
                return;
            }
            // Se digitou só números, pode ser o número da PE (ex.: 0186).
            if (/^\d{1,4}$/.test(termo)) {
                const p2 = new URLSearchParams();
                p2.set('pe', termo);
                if (CFG.protocolId) p2.set('venda_id', CFG.protocolId);
                return fetch('/protocolos/api/pronta-entrega/buscar?' + p2.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                    .then(function(r) { return r.json(); })
                    .then(function(d2) { renderPEResultados(result, d2.resultados || []); });
            }
            renderPEResultados(result, []);
        })
        .catch(function() {
            result.innerHTML = '<div class="text-danger">Não foi possível consultar agora. Tente novamente.</div>';
        });
}

function appendCompRow(tbody, machine, item) {
    const tr = document.createElement('tr');
    tr.className = 'comp-row';
    const bloco = tbody.closest ? tbody.closest('.machine-block') : null;
    const nsOpcional = bloco ? nsOpcionalNoBloco(bloco) : false;
    const hasSerial = !!(item.serial);
    const showBtn = (nsOpcional && !hasSerial) ? '' : 'style="display:none"';
    const showInput = (!nsOpcional || hasSerial) ? '' : 'style="display:none"';
    tr.innerHTML = `
        <td>
            <select name="comp_type_${machine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select>
            <input type="hidden" name="comp_product_id_${machine}[]" value="">
        </td>
        <td><input type="text" name="comp_model_${machine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(item.model || '')}"></td>
        <td>
            <div class="d-flex align-items-center gap-1">
                <button type="button" class="btn btn-sm btn-outline-warning pe-ref-btn py-0 px-1" ${showBtn} onclick="addRefSerial(this)" title="Adicionar NS de referência"><i class="bi bi-plus-lg"></i></button>
                <input type="text" name="comp_serial_${machine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${escHtml(item.serial || '')}">
                <button type="button" class="btn btn-sm btn-outline-danger remove-ref-btn py-0 px-1" onclick="removeRefSerial(this)" title="Remover NS" style="display:none"><i class="bi bi-x"></i></button>
            </div>
        </td>
        <td class="text-nowrap">
            <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, -1)" title="Mover pra cima"><i class="bi bi-arrow-up"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, 1)" title="Mover pra baixo"><i class="bi bi-arrow-down"></i></button>
            <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="this.closest('tr').remove()" title="Remover"><i class="bi bi-x"></i></button>
        </td>
    `;
    const select = tr.querySelector('select');
    select.value = item.type || '';
    if (!materialComumAtivo() && produtosCatalogo.length > 0) {
        loadCatalogSelect(select, tr.querySelector('input[name^="comp_model_"]'), tr.querySelector('input[name^="comp_product_id_"]'));
        if (select.value !== (item.type || '')) {
            select.innerHTML = EXTRA_OPTS;
            select.value = item.type || '';
        }
    }
    tbody.appendChild(tr);
}

function aplicarPE(btn, modo) {
    const info = JSON.parse(btn.getAttribute('data-pe'));
    const block = btn.closest('.machine-block');
    const machine = block.dataset.machine;
    if ((info.vendida || []).length) {
        const msg = info.vendida.map(function(v) {
            return v.protocol_number + ' — ' + (v.client_name || 'sem cliente') + ' ' + (v.date || '');
        }).join('\n');
        if (!window.confirm('Atenção: esta máquina já saiu em outra venda:\n\n' + msg +
                '\n\nConfirmar mesmo assim (troca/devolução)?')) {
            return;
        }
    }
    const tbody = block.querySelector('.machine-body');
    tbody.innerHTML = '';
    (info.components || []).forEach(function(c) {
        appendCompRow(tbody, machine, {
            type: c.type,
            model: c.model,
            serial: (modo === 'tudo' || c.type === 'fonte') ? c.serial : ''
        });
    });
    const hidden = block.querySelector('.pe-ref-json');
    hidden.value = JSON.stringify({
        protocol_id: info.protocol_id,
        protocol_number: info.protocol_number,
        unit: info.unit,
        machine_name: info.machine_name || '',
        fonte: info.fonte || ''
    });
    const changeBtn = block.querySelector('.pe-change-btn');
    if (changeBtn) changeBtn.style.display = '';
    updatePERefStatus(block, {
        protocol_id: info.protocol_id,
        protocol_number: info.protocol_number,
        unit: info.unit,
        machine_name: info.machine_name || '',
        fonte: info.fonte || ''
    });
    const result = block.querySelector('.pe-result');
    if (result) {
        result.innerHTML = '<div class="text-success"><i class="bi bi-check-lg"></i> Máquina da Pronta-Entrega vinculada.</div>';
    }
    syncVendaPeTop();
}

function limparPE(btn) {
    const block = btn.closest('.machine-block');
    const hidden = block.querySelector('.pe-ref-json');
    if (hidden) hidden.value = '';
    const input = block.querySelector('.pe-ns-input');
    if (input) input.value = '';
    const result = block.querySelector('.pe-result');
    if (result) result.innerHTML = '';
    updatePERefStatus(block, null);
    const changeBtn = block.querySelector('.pe-change-btn');
    if (changeBtn) changeBtn.style.display = 'none';
}

function addRefSerial(btn) {
    btn.style.display = 'none';
    const div = btn.parentElement;
    div.querySelector('.serial-input').style.display = '';
    div.querySelector('.remove-ref-btn').style.display = '';
    div.querySelector('.serial-input').focus();
}

function removeRefSerial(btn) {
    const div = btn.parentElement;
    div.querySelector('.serial-input').value = '';
    div.querySelector('.serial-input').style.display = 'none';
    div.querySelector('.remove-ref-btn').style.display = 'none';
    div.querySelector('.pe-ref-btn').style.display = '';
}

function addCompRow(btn) {
    const machineBlock = btn.closest('.machine-block');
    const machine = machineBlock.dataset.machine;
    const tbody = machineBlock.querySelector('.machine-body');
    const nsOpcional = nsOpcionalNoBloco(machineBlock);
    const isComum = materialComumAtivo();
    const tr = document.createElement('tr');
    tr.className = 'comp-row';
    const showBtn = nsOpcional ? '' : 'style="display:none"';
    const showInput = nsOpcional ? 'style="display:none"' : '';
    tr.innerHTML = `
        <td>
            <select name="comp_type_${machine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select>
            <input type="hidden" name="comp_product_id_${machine}[]" value="">
        </td>
        <td><input type="text" name="comp_model_${machine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..."></td>
        <td>
            <div class="d-flex align-items-center gap-1">
                <button type="button" class="btn btn-sm btn-outline-warning pe-ref-btn py-0 px-1" ${showBtn} onclick="addRefSerial(this)" title="Adicionar NS de referência"><i class="bi bi-plus-lg"></i></button>
                <input type="text" name="comp_serial_${machine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput}>
                <button type="button" class="btn btn-sm btn-outline-danger remove-ref-btn py-0 px-1" onclick="removeRefSerial(this)" title="Remover NS" style="display:none"><i class="bi bi-x"></i></button>
            </div>
        </td>
        <td class="text-nowrap">
            <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, -1)" title="Mover pra cima"><i class="bi bi-arrow-up"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, 1)" title="Mover pra baixo"><i class="bi bi-arrow-down"></i></button>
            <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="this.closest('tr').remove()" title="Remover"><i class="bi bi-x"></i></button>
        </td>
    `;
    tbody.appendChild(tr);
    if (!isComum && produtosCatalogo.length > 0) {
        const typeSelect = tr.querySelector('select');
        const modelInput = tr.querySelector('input[name^="comp_model_"]');
        const produtoIdInput = tr.querySelector('input[name^="comp_product_id_"]');
        loadCatalogSelect(typeSelect, modelInput, produtoIdInput);
    }
}

function moveCompRow(btn, direction) {
    const tr = btn.closest('tr');
    const tbody = tr.closest('tbody');
    const rows = Array.from(tbody.querySelectorAll('.comp-row'));
    const idx = rows.indexOf(tr);
    if (direction === -1 && idx > 0) {
        tbody.insertBefore(tr, rows[idx - 1]);
    } else if (direction === 1 && idx < rows.length - 1) {
        tbody.insertBefore(rows[idx + 1], tr);
    }
}

function loadMachines(data) {
    if (!data || Object.keys(data).length === 0) {
        addMachine();
        return;
    }
    const container = document.getElementById('machinesContainer');
    container.innerHTML = '';
    const machines = Object.keys(data).sort();
    let maxM = 0;
    const isComum = document.getElementById('materialComum') && document.getElementById('materialComum').checked;
    machines.forEach(function(m) {
        const num = parseInt(m, 10);
        if (!isNaN(num) && num > maxM) maxM = num;
        const entry = data[m];
        const machineName = entry.name || null;
        const comps = entry.components || entry || [];
        const isPE = entry.is_prebuilt || isPontaEntregaType();
        const pc = entry.power_cable || 'OK';
        container.insertAdjacentHTML('beforeend', machineHTML(num, machineName, isPE, pc));
        const block = container.lastElementChild;
        const tbody = block.querySelector('.machine-body');
        const cb = block.querySelector('.form-check-input');
        if (isPE) cb.checked = true;
        if (isPE && currentProtocolType() === 'venda') togglePE(cb);
        comps.forEach(function(item) {
            const tr = document.createElement('tr');
            tr.className = 'comp-row';
            const hasSerial = item.serial ? true : false;
            const nsOpcional = currentProtocolType() === 'venda' && isPE;
            const showBtn = (nsOpcional && !hasSerial) ? '' : 'style="display:none"';
            const showInput = (!nsOpcional || hasSerial) ? '' : 'style="display:none"';
            tr.innerHTML = `
                <td>
                    <select name="comp_type_${m}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select>
                    <input type="hidden" name="comp_product_id_${m}[]" value="${item.product_id || ''}">
                </td>
                <td><input type="text" name="comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(item.model)}"></td>
                <td>
                    <div class="d-flex align-items-center gap-1">
                        <button type="button" class="btn btn-sm btn-outline-warning pe-ref-btn py-0 px-1" ${showBtn} onclick="addRefSerial(this)" title="Adicionar NS de referência"><i class="bi bi-plus-lg"></i></button>
                        <input type="text" name="comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${escHtml(item.serial)}">
                        <button type="button" class="btn btn-sm btn-outline-danger remove-ref-btn py-0 px-1" onclick="removeRefSerial(this)" title="Remover NS" style="display:none"><i class="bi bi-x"></i></button>
                    </div>
                </td>
                <td class="text-nowrap">
                    <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, -1)" title="Mover pra cima"><i class="bi bi-arrow-up"></i></button>
                    <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="moveCompRow(this, 1)" title="Mover pra baixo"><i class="bi bi-arrow-down"></i></button>
                    <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="this.closest('tr').remove()" title="Remover"><i class="bi bi-x"></i></button>
                </td>
            `;
            const select = tr.querySelector('select');
            select.value = item.type || '';
            if (!isComum && produtosCatalogo.length > 0) {
                const typeSelect = tr.querySelector('select');
                const modelInput = tr.querySelector('input[name^="comp_model_"]');
                const produtoIdInput = tr.querySelector('input[name^="comp_product_id_"]');
                loadCatalogSelect(typeSelect, modelInput, produtoIdInput);
                if (item.product_id && produtoIdInput) {
                    produtoIdInput.value = item.product_id;
                }
            }
            tbody.appendChild(tr);
        });
    });
    machineCount = maxM || 0;
    if (machineCount === 0) addMachine();
    syncDefectMachines();
}

function addDefectRow() {
    const tbody = document.querySelector('#defectsTable tbody');
    const opts = defectOptsHtml('');
    const tr = document.createElement('tr');
    tr.className = 'defect-row';
    tr.innerHTML = `
        <td><select name="defect_type[]" class="form-select form-select-sm">${opts}</select></td>
        <td class="maquina-col"><select name="defect_maquina[]" class="form-select form-select-sm">${MACHINE_OPTS}</select></td>
        <td><input type="text" name="defect_model[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..."></td>
        <td><input type="text" name="defect_serial[]" class="form-control form-control-sm" placeholder="NS do componente com defeito"></td>
        <td><input type="text" name="defect_desc[]" class="form-control form-control-sm" placeholder="Ex: Não liga, não dá vídeo..."></td>
        <td>
            <select name="defect_status[]" class="form-select form-select-sm">
                <option value=\"\">--</option>
                ${STATUS_OPTS}
            </select>
        </td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
    `;
    tbody.appendChild(tr);
}

function addPassagem() {
    const container = document.getElementById('passagensContainer');
    const div = document.createElement('div');
    div.className = 'passagem-row position-relative border rounded p-2 mb-2';
    div.innerHTML = `
        <button type="button" class="btn btn-sm btn-outline-danger position-absolute top-0 end-0 m-1" onclick="this.closest('.passagem-row').remove()"><i class="bi bi-x"></i></button>
        <div class="row g-2">
            <div class="col-md-2">
                <label class="form-label small mb-0">Protocolo</label>
                <input type="text" name="passagem_protocolo[]" class="form-control form-control-sm" placeholder="Opcional">
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-0">Data Entrada</label>
                <input type="text" name="passagem_data_entrada[]" class="form-control form-control-sm" placeholder="DD/MM/AAAA">
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-0">Data Saída</label>
                <input type="text" name="passagem_data_saida[]" class="form-control form-control-sm" placeholder="DD/MM/AAAA">
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-0">Pedido do produto com defeito</label>
                <input type="text" name="passagem_pedido[]" class="form-control form-control-sm" placeholder="Pedido do defeito">
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-0">NS do produto com defeito</label>
                <input type="text" name="passagem_ns[]" class="form-control form-control-sm" placeholder="NS do defeito">
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-0">NS do novo produto</label>
                <input type="text" name="passagem_ns_novo[]" class="form-control form-control-sm" placeholder="NS do novo">
            </div>
        </div>
    `;
    container.appendChild(div);
}

function loadPassagens(passagens) {
    if (!passagens || passagens.length === 0) return;
    const container = document.getElementById('passagensContainer');
    container.innerHTML = '';
    passagens.forEach(function(p) {
        const div = document.createElement('div');
        div.className = 'passagem-row position-relative border rounded p-2 mb-2';
        div.innerHTML = `
            <button type="button" class="btn btn-sm btn-outline-danger position-absolute top-0 end-0 m-1" onclick="this.closest('.passagem-row').remove()"><i class="bi bi-x"></i></button>
            <div class="row g-2">
                <div class="col-md-2">
                    <label class="form-label small mb-0">Protocolo</label>
                    <input type="text" name="passagem_protocolo[]" class="form-control form-control-sm" placeholder="Opcional" value="${escHtml(p.protocolo)}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">Data Entrada</label>
                    <input type="text" name="passagem_data_entrada[]" class="form-control form-control-sm" placeholder="DD/MM/AAAA" value="${escHtml(p.data_entrada)}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">Data Saída</label>
                    <input type="text" name="passagem_data_saida[]" class="form-control form-control-sm" placeholder="DD/MM/AAAA" value="${escHtml(p.data_saida)}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">Pedido do produto com defeito</label>
                    <input type="text" name="passagem_pedido[]" class="form-control form-control-sm" placeholder="Pedido do defeito" value="${escHtml(p.pedido)}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">NS do produto com defeito</label>
                    <input type="text" name="passagem_ns[]" class="form-control form-control-sm" placeholder="NS do defeito" value="${escHtml(p.ns)}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">NS do novo produto</label>
                    <input type="text" name="passagem_ns_novo[]" class="form-control form-control-sm" placeholder="NS do novo" value="${escHtml(p.ns_novo)}">
                </div>
            </div>
        `;
        container.appendChild(div);
    });
}

function loadRmaMachines(data) {
    if (!data || Object.keys(data).length === 0) {
        addRmaMachine();
        return;
    }
    const container = document.getElementById('rmaMachinesContainer');
    container.innerHTML = '';
    const machines = Object.keys(data).sort();
    let maxM = 0;
    machines.forEach(function(m) {
        const num = parseInt(m, 10);
        if (!isNaN(num) && num > maxM) maxM = num;
        const entry = data[m];
        const machineName = entry.name || null;
        const comps = entry.components || entry || [];
        container.insertAdjacentHTML('beforeend', rmaMachineHTML(num, machineName));
        const block = container.lastElementChild;
        const tbody = block.querySelector('.rma-machine-body');
        comps.forEach(function(item) {
            const tr = document.createElement('tr');
            tr.className = 'comp-row';
            const hasSerial = item.serial ? true : false;
            const showBtn = hasSerial ? 'style="display:none"' : '';
            const showInput = hasSerial ? '' : 'style="display:none"';
            tr.innerHTML = `
                <td><select name="rma_comp_type_${m}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
                <td><input type="text" name="rma_comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(item.model)}"></td>
                <td>
                    <div class="d-flex align-items-center gap-1">
                        <button type="button" class="btn btn-sm btn-outline-warning rma-ref-btn py-0 px-1" ${showBtn} onclick="addRmaRefSerial(this)" title="Adicionar NS"><i class="bi bi-plus-lg"></i></button>
                        <input type="text" name="rma_comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${escHtml(item.serial)}">
                        <button type="button" class="btn btn-sm btn-outline-danger remove-ref-btn py-0 px-1" onclick="removeRmaRefSerial(this)" title="Remover NS" style="display:none"><i class="bi bi-x"></i></button>
                    </div>
                </td>
                <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
            `;
            const select = tr.querySelector('select');
            select.value = item.type || '';
            tbody.appendChild(tr);
        });
    });
    rmaMachineCount = maxM || 0;
    if (rmaMachineCount === 0) addRmaMachine();
}

function loadRmaTestItems(items) {
    if (!items || items.length === 0) return;
    const tbody = document.querySelector('#rmaTestTable tbody');
    const opts = '<option value="">-- Selecione --</option>' +
        Object.entries(COMP_LABELS).map(([k, v]) => `<option value="${escHtml(k)}">${escHtml(v)}</option>`).join('');
    items.forEach(function(item) {
        const tr = document.createElement('tr');
        tr.className = 'rma-test-row';
        tr.innerHTML = `
            <td><select name="rma_test_machine[]" class="form-select form-select-sm">${currentRmaMachineOpts()}</select></td>
            <td><select name="rma_test_comp[]" class="form-select form-select-sm">${opts}</select></td>
            <td><input type="text" name="rma_test_model[]" class="form-control form-control-sm" value="${escHtml(item.model)}"></td>
            <td class="rma-test-ns-cell" style="display:${rmaTestHasNs() ? '' : 'none'}"><input type="text" name="rma_test_serial[]" class="form-control form-control-sm" placeholder="Nº de Série" value="${escHtml(item.serial)}"></td>
            <td><input type="text" name="rma_test_defeito[]" class="form-control form-control-sm" value="${escHtml(item.defeito)}"></td>
            <td class="rma-test-origem-cell" style="display:${rmaTestHasOrigemTechBuy() ? '' : 'none'}"><input type="text" name="rma_test_pedido[]" class="form-control form-control-sm" value="${rmaTestHasOrigemTechBuy() ? escHtml(item.pedido) : ''}"${rmaTestHasOrigemTechBuy() ? '' : ' disabled'}></td>
            <td class="rma-test-origem-cell" style="display:${rmaTestHasOrigemTechBuy() ? '' : 'none'}"><input type="text" name="rma_test_data_compra[]" class="form-control form-control-sm date-mask" value="${rmaTestHasOrigemTechBuy() ? escHtml(item.data_compra) : ''}"${rmaTestHasOrigemTechBuy() ? '' : ' disabled'}></td>
            <td>
                <select name="rma_test_status[]" class="form-select form-select-sm">
                    <option value="">--</option>
                    ${statusOptsSelected(item.status)}
                </select>
            </td>
            <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
        `;
        tbody.appendChild(tr);
        if (window.initDateMask) initDateMask(tr);
        const selMaquina = tr.querySelector('select[name="rma_test_machine[]"]');
        const alvoMaquina = (item.machine || '').trim();
        if (selMaquina && alvoMaquina) {
            let opcao = Array.from(selMaquina.options).filter(function(o) {
                return o.value === alvoMaquina;
            })[0];
            if (!opcao) {
                opcao = Array.from(selMaquina.options).filter(function(o) {
                    return o.value.trim().toLowerCase() === alvoMaquina.toLowerCase();
                })[0];
            }
            if (opcao) selMaquina.value = opcao.value;
        }
        if (item.component) tr.querySelector('select[name="rma_test_comp[]"]').value = item.component;
    });
}

function loadRmaTrocadosItems(data) {
    // Handle both old format (array) and new format (dict with unit keys)
    if (!data || (Array.isArray(data) && data.length === 0) || (!Array.isArray(data) && Object.keys(data).length === 0)) {
        addTrocadoMachine();
        return;
    }
    // Convert old array format to new dict format
    if (Array.isArray(data)) {
        const old = data;
        data = {'01': {name: 'Computador 01', components: old}};
    }
    const container = document.getElementById('rmaTrocadosContainer');
    container.innerHTML = '';
    const machines = Object.keys(data).sort();
    let maxM = 0;
    machines.forEach(function(m) {
        const num = parseInt(m, 10);
        if (!isNaN(num) && num > maxM) maxM = num;
        const entry = data[m];
        const machineName = entry.name || null;
        const comps = entry.components || [];
        container.insertAdjacentHTML('beforeend', trocadoMachineHTML(num, machineName));
        const block = container.lastElementChild;
        const tbody = block.querySelector('.trocado-machine-body');
        comps.forEach(function(item) {
            const tr = document.createElement('tr');
            tr.className = 'comp-row';
            const type = item.type || item.component || '';
            tr.innerHTML = `
                <td><select name="trocado_row_machine[]" class="form-select form-select-sm">${currentTrocadoMachineOpts(entry.name || null)}</select></td>
                <td><select name="trocado_comp_type_${m}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
                <td><input type="text" name="trocado_comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${escHtml(item.model)}"></td>
                <td><input type="text" name="trocado_comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" minlength="3" value="${escHtml(item.serial)}"></td>
                <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
            `;
            const selects = tr.querySelectorAll('select');
            if (selects[1]) selects[1].value = type;
            tbody.appendChild(tr);
            initTrocadoCatalog(tr);
        });
    });
    trocadoMachineCount = maxM || 0;
    if (trocadoMachineCount === 0) addTrocadoMachine();
}

document.addEventListener('DOMContentLoaded', function() {
    const typeSelect = document.getElementById('protocolType');
    const fieldGroups = document.querySelectorAll('.field-group');
    const exitGroups = document.querySelectorAll('.field-group-exit');
    const sectionClient = document.getElementById('sectionClientLabel');
    const compData = CFG.compData;
    loadMachines(compData);

    loadRmaMachines(CFG.rmaCompData);
    loadRmaTestItems(CFG.rmaTestData);
    syncRmaTestMachines();
    loadRmaTrocadosItems(CFG.rmaTrocados);

    syncDefectTipos();
    ['#machinesContainer', '#rmaMachinesContainer', '#rmaTrocadosContainer'].forEach(function(sel) {
        const el = document.querySelector(sel);
        if (el && typeof MutationObserver !== 'undefined') {
            new MutationObserver(function() { scheduleSyncDefectTipos(); })
                .observe(el, { childList: true, subtree: true });
        }
    });

    function toggleWindowsKeys() {
        const checked = document.getElementById('toggleWindowsKeys').checked;
        document.getElementById('windowsKeysSection').style.display = checked ? 'block' : 'none';
    }
    document.getElementById('toggleWindowsKeys').addEventListener('change', toggleWindowsKeys);
    window.toggleWindowsKeys = toggleWindowsKeys;

    function addWindowsKey(chave, fonte, ativo) {
        const tbody = document.querySelector('#windowsKeysTable tbody');
        const tr = document.createElement('tr');
        tr.className = 'win-key-row';
        tr.innerHTML = `
            <td><input type="text" class="form-control form-control-sm win-key-chave" placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX" value="${escHtml(chave)}"></td>
            <td><input type="text" class="form-control form-control-sm win-key-fonte" placeholder="NS da Fonte" value="${escHtml(fonte)}"></td>
            <td>
                <div class="form-check">
                    <input type="checkbox" class="form-check-input win-key-ativo" ${ativo ? 'checked' : ''}>
                    <label class="form-check-label small">Ativo</label>
                </div>
            </td>
            <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>`;
        tbody.appendChild(tr);
    }
    window.addWindowsKey = addWindowsKey;

    function loadWindowsKeys(data) {
        if (!data || data.length === 0) return;
        document.getElementById('toggleWindowsKeys').checked = true;
        toggleWindowsKeys();
        data.forEach(function(item) {
            addWindowsKey(item.chave || '', item.fonte || '', item.ativo || false);
        });
    }
    window.loadWindowsKeys = loadWindowsKeys;

    function updateFields() {
        const type = typeSelect.value;
        fieldGroups.forEach(function(g) {
            const sf = g.getAttribute('data-show-for');
            if (sf) {
                const show = sf.split(',').includes(type);
                if (g.classList.contains('venda-pe-group')) {
                    g.style.display = show ? 'flex' : 'none';
                } else {
                    g.style.display = show ? 'block' : 'none';
                }
            }
        });
        exitGroups.forEach(function(g) {
            const sf = g.getAttribute('data-show-for');
            if (sf) g.style.display = sf.split(',').includes(type) ? 'block' : 'none';
        });
        var isRma = type === 'rma' || type === 'servico';
        var isNaoComprado = type === 'nao_comprado';
        document.querySelectorAll('.rma-only').forEach(function(g) {
            var showRmaOrNtb = isRma || isNaoComprado;
            g.style.display = showRmaOrNtb ? 'block' : 'none';
            g.querySelectorAll('select, input, textarea').forEach(function(f) { f.disabled = !showRmaOrNtb; });
        });
        document.querySelectorAll('.rma-field:not(.rma-only)').forEach(function(g) {
            g.style.display = (isRma || isNaoComprado) ? 'block' : 'none';
            g.querySelectorAll('select, input, textarea').forEach(function(f) { f.disabled = !(isRma || isNaoComprado); });
        });
        document.querySelectorAll('.hide-for-rma').forEach(function(g) {
            if (g.classList.contains('hide-for-nao-comprado') && isNaoComprado) return;
            g.style.display = isRma ? 'none' : 'block';
            g.querySelectorAll('select, input, textarea').forEach(function(f) { f.disabled = isRma; });
        });
        document.querySelectorAll('.hide-for-nao-comprado').forEach(function(g) {
            if (g.classList.contains('hide-for-rma') && isRma) return;
            g.style.display = isNaoComprado ? 'none' : 'block';
            g.querySelectorAll('select, input, textarea').forEach(function(f) { f.disabled = isNaoComprado; });
        });
        document.querySelectorAll('.maquina-col').forEach(function(el) {
            el.style.display = '';
            el.querySelectorAll('select').forEach(function(f) { f.disabled = false; });
        });
        // Dynamic heading: "Dados do Equipamento do Cliente" only for NTB
        var entryLabel = document.getElementById('entryDateLabel');
        if (entryLabel) entryLabel.textContent = type === 'nao_comprado'
            ? (CFG.fields.rma_entry_date || 'Data de Entrada')
            : (CFG.fields.entry_date || 'Data da Compra');
        if (sectionClient) sectionClient.style.display = type === 'ponta_entrega' ? 'none' : 'block';
        var rmaDataHeading = document.getElementById('rmaDataHeading');
        if (rmaDataHeading) rmaDataHeading.textContent = type === 'servico'
            ? (CFG.titles.rma_servico || 'Dados do Serviço')
            : (CFG.titles.rma || 'Dados do RMA');
        var rmaWarrantyInfo = document.getElementById('rmaWarrantyInfo');
        if (rmaWarrantyInfo) rmaWarrantyInfo.value = type === 'rma' ? 'Sim' : 'Não';
        var obsLabel = document.getElementById('obsLabel');
        if (obsLabel) {
            obsLabel.innerHTML = (isRma
                ? '<i class="bi bi-exclamation-triangle text-warning"></i> ' + (CFG.titles.defeito_relatado || 'Defeito Relatado / Observações Técnicas')
                : '<i class="bi bi-chat-dots"></i> ' + (CFG.titles.observacoes || 'Observações'));
        }
        updateRmaTestNsColumns();
        syncPEMachineUI();
    }
    if (typeSelect) { typeSelect.addEventListener('change', updateFields); updateFields(); }

    // Load existing passagens
    if (CFG.passagens && CFG.passagens.length) {
        try { loadPassagens(CFG.passagens); } catch(e) {}
    }

    // Load existing windows keys
    if (CFG.winKeys && CFG.winKeys.length > 0) {
        try { loadWindowsKeys(CFG.winKeys); } catch(e) {}
    }

    // Serialize passagens on submit
    document.querySelector('form').addEventListener('submit', function(e) {
        const rows = document.querySelectorAll('.passagem-row');
        const passagens = [];
        rows.forEach(function(row) {
            const q = function(name) {
                const el = row.querySelector('input[name="' + name + '"]');
                return el ? el.value : '';
            };
            passagens.push({
                protocolo: q('passagem_protocolo[]'),
                data_entrada: q('passagem_data_entrada[]'),
                data_saida: q('passagem_data_saida[]'),
                pedido: q('passagem_pedido[]'),
                ns: q('passagem_ns[]'),
                ns_novo: q('passagem_ns_novo[]')
            });
        });
        let hidden = document.querySelector('input[name="rma_passagens_json"]');
        if (!hidden) {
            hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'rma_passagens_json';
            this.appendChild(hidden);
        }
        hidden.value = JSON.stringify(passagens);
    });

    // Serialize RMA test items on submit
    document.querySelector('form').addEventListener('submit', function(e) {
        const rows = document.querySelectorAll('#rmaTestTable tbody .rma-test-row');
        const items = [];
        const singleMachine = (function() {
            const names = [];
            document.querySelectorAll('input[name^="rma_machine_name_"]').forEach(function(inp) {
                const v = inp.value.trim();
                if (v && names.indexOf(v) === -1) names.push(v);
            });
            return names.length === 1 ? names[0] : '';
        })();
        rows.forEach(function(row) {
            const machine = row.querySelector('select[name^="rma_test_machine"]');
            let mval = machine ? machine.value : '';
            if (!mval && singleMachine) {
                mval = singleMachine;
                if (machine) machine.value = singleMachine;
            }
            const comp = row.querySelector('select[name^="rma_test_comp"]');
            const model = row.querySelector('input[name^="rma_test_model"]');
            const serial = row.querySelector('input[name^="rma_test_serial"]');
            const defeito = row.querySelector('input[name^="rma_test_defeito"]');
            const pedido = row.querySelector('input[name^="rma_test_pedido"]');
            const dataCompra = row.querySelector('input[name^="rma_test_data_compra"]');
            const status = row.querySelector('select[name^="rma_test_status"]');
            const origemTechBuy = rmaTestHasOrigemTechBuy();
            items.push({
                machine: mval,
                component: comp ? comp.value : '',
                model: model ? model.value : '',
                serial: serial ? serial.value : '',
                defeito: defeito ? defeito.value : '',
                pedido: origemTechBuy && pedido ? pedido.value : '',
                data_compra: origemTechBuy && dataCompra ? dataCompra.value : '',
                status: status ? status.value : ''
            });
        });
        let hidden = document.querySelector('input[name="rma_test_json"]');
        if (!hidden) {
            hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'rma_test_json';
            this.appendChild(hidden);
        }
        hidden.value = JSON.stringify(items);
        const singleDefMachine = (function() {
            const names = [];
            document.querySelectorAll('input[name^="machine_name_"]').forEach(function(inp) {
                const v = inp.value.trim();
                if (v && names.indexOf(v) === -1) names.push(v);
            });
            if (names.length !== 1) {
                const rma = [];
                document.querySelectorAll('input[name^="rma_machine_name_"]').forEach(function(inp) {
                    const v = inp.value.trim();
                    if (v && rma.indexOf(v) === -1) rma.push(v);
                });
                return rma.length === 1 ? rma[0] : (names.length ? '' : '');
            }
            return names[0];
        })();
        if (singleDefMachine) {
            document.querySelectorAll('select[name="defect_maquina[]"]').forEach(function(sel) {
                if (!sel.value) {
                    let opt = sel.querySelector('option[value="' + singleDefMachine + '"]');
                    if (!opt) {
                        opt = document.createElement('option');
                        opt.value = singleDefMachine;
                        opt.textContent = singleDefMachine;
                        sel.appendChild(opt);
                    }
                    sel.value = singleDefMachine;
                }
            });
        }
    });

    // Serialize Equipamentos Mudados on submit (regrouped by chosen Máquina per row)
    document.querySelector('form').addEventListener('submit', function(e) {
        const blocks = document.querySelectorAll('#rmaTrocadosContainer .trocado-machine-block');
        const unitByName = {};
        blocks.forEach(function(block) {
            const unit = block.dataset.trocadoMachine;
            const nameInput = block.querySelector('input[name^="trocado_machine_name_"]');
            const name = nameInput ? nameInput.value.trim() : ('Computador ' + unit);
            if (name && !unitByName[name]) unitByName[name] = unit;
        });
        if (!Object.keys(unitByName).length) unitByName['Computador 01'] = '01';
        let autoUnit = 1;
        const data = {};
        blocks.forEach(function(block) {
            const rows = block.querySelectorAll('.trocado-machine-body .comp-row');
            rows.forEach(function(row) {
                const machSel = row.querySelector('select[name="trocado_row_machine[]"]');
                const comp = row.querySelector('select[name^="trocado_comp_type_"]');
                const model = row.querySelector('input[name^="trocado_comp_model_"]');
                const serial = row.querySelector('input[name^="trocado_comp_serial_"]');
                if (comp && comp.value) {
                    let mname = machSel ? machSel.value.trim() : '';
                    if (!mname) {
                        const blkNameInput = block.querySelector('input[name^="trocado_machine_name_"]');
                        mname = blkNameInput ? blkNameInput.value.trim() : 'Computador 01';
                    }
                    if (!unitByName[mname]) {
                        while (Object.values(unitByName).indexOf(String(autoUnit).padStart(2, '0')) !== -1) autoUnit++;
                        unitByName[mname] = String(autoUnit).padStart(2, '0');
                        autoUnit++;
                    }
                    const unit = unitByName[mname];
                    if (!data[unit]) data[unit] = {name: mname, components: []};
                    data[unit].components.push({
                        type: comp.value,
                        model: model ? model.value : '',
                        serial: serial ? serial.value : ''
                    });
                }
            });
        });
        Object.keys(unitByName).forEach(function(nm) {
            const u = unitByName[nm];
            if (!data[u]) data[u] = {name: nm, components: []};
        });
        let hidden = document.querySelector('input[name="rma_trocados_json"]');
        if (!hidden) {
            hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'rma_trocados_json';
            this.appendChild(hidden);
        }
        hidden.value = JSON.stringify(data);
    });

    // Serialize RMA equipment (Computador XX) on submit
    document.querySelector('form').addEventListener('submit', function(e) {
        const blocks = document.querySelectorAll('#rmaMachinesContainer .rma-machine-block');
        const data = {};
        blocks.forEach(function(block) {
            const unit = block.dataset.rmaMachine;
            const nameInput = block.querySelector('input[name^="rma_machine_name_"]');
            const name = nameInput ? nameInput.value : ('Computador ' + unit);
            const comps = [];
            const rows = block.querySelectorAll('.rma-machine-body .comp-row');
            rows.forEach(function(row) {
                const comp = row.querySelector('select');
                const model = row.querySelector('input[name^="rma_comp_model_"]');
                const serial = row.querySelector('input[name^="rma_comp_serial_"]');
                if (comp && comp.value) {
                    comps.push({
                        type: comp.value,
                        model: model ? model.value : '',
                        serial: serial ? serial.value : ''
                    });
                }
            });
            data[unit] = {name: name, components: comps};
        });
        let hidden = document.querySelector('input[name="rma_equip_json"]');
        if (!hidden) {
            hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'rma_equip_json';
            this.appendChild(hidden);
        }
        hidden.value = JSON.stringify(data);
    });

    // Serialize Windows Keys on submit
    document.querySelector('form').addEventListener('submit', function(e) {
        const rows = document.querySelectorAll('#windowsKeysTable tbody .win-key-row');
        const items = [];
        rows.forEach(function(row) {
            items.push({
                chave: row.querySelector('.win-key-chave').value,
                fonte: row.querySelector('.win-key-fonte').value,
                ativo: row.querySelector('.win-key-ativo').checked
            });
        });
        let hidden = document.querySelector('input[name="windows_keys_json"]');
        if (!hidden) {
            hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'windows_keys_json';
            this.appendChild(hidden);
        }
        hidden.value = JSON.stringify(items);
    });

    // Submit via fetch to preserve JS state on validation errors
    document.querySelector('form').addEventListener('submit', function(e) {
        e.preventDefault();
        const form = this;
        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Salvando...';

        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData
        }).then(function(resp) {
            if (resp.redirected) {
                window.location.href = resp.url;
            } else {
                return resp.json().then(function(data) {
                    btn.disabled = false;
                    btn.innerHTML = 'Salvar';
                    form.querySelectorAll('.alert').forEach(function(a) { a.remove(); });
                    if (data.errors && data.errors.length > 0) {
                        var alertBox = document.createElement('div');
                        alertBox.className = 'alert alert-warning alert-dismissible fade show mt-3';
                        alertBox.innerHTML = '<i class="bi bi-exclamation-triangle"></i> <strong>Corrija os erros abaixo:</strong><ul class="mb-0 mt-1">' +
                            data.errors.map(function(e) { return '<li>' + e + '</li>'; }).join('') +
                            '</ul><button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
                        form.prepend(alertBox);
                    } else {
                        var alertBox = document.createElement('div');
                        alertBox.className = 'alert alert-warning alert-dismissible fade show mt-3';
                        alertBox.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Verifique os campos obrigatórios.<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
                        form.prepend(alertBox);
                    }
                    window.scrollTo(0, 0);
                }).catch(function() {
                    btn.disabled = false;
                    btn.innerHTML = 'Salvar';
                    var alertBox = document.createElement('div');
                    alertBox.className = 'alert alert-warning alert-dismissible fade show mt-3';
                    alertBox.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Verifique os campos obrigatórios.<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
                    form.prepend(alertBox);
                    window.scrollTo(0, 0);
                });
            }
        }).catch(function() {
            btn.disabled = false;
            btn.innerHTML = 'Salvar';
            const alertBox = document.createElement('div');
            alertBox.className = 'alert alert-danger alert-dismissible fade show mt-3';
            alertBox.innerHTML = '<i class="bi bi-x-circle"></i> Erro de conexão. Tente novamente.<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
            form.prepend(alertBox);
        });
    });
});
// Histórico do pedido: digitou o pedido, puxa a corrente de protocolos.
document.addEventListener('DOMContentLoaded', function() {
    const pedidoInput = document.getElementById('order_number');
    const container = document.getElementById('historicoPedido');
    if (!pedidoInput || !container) return;

    const ignorar = container.dataset.protocolId || '';
    let ultimo = null;
    let timer = null;

    function carregarHistoricoPedido() {
        const pedido = (pedidoInput.value || '').trim();
        if (!pedido) {
            container.innerHTML = '';
            ultimo = null;
            return;
        }
        if (pedido === ultimo) return;
        ultimo = pedido;
        const params = new URLSearchParams({ pedido: pedido });
        if (ignorar) params.set('ignorar', ignorar);
        fetch('/protocolos/historico-pedido?' + params.toString())
            .then(function(r) { return r.ok ? r.text() : ''; })
            .then(function(html) { container.innerHTML = html; })
            .catch(function() { /* silencioso: o histórico é só um apoio */ });
    }

    function agendarBusca() {
        clearTimeout(timer);
        timer = setTimeout(carregarHistoricoPedido, 500);
    }

    pedidoInput.addEventListener('change', carregarHistoricoPedido);
    pedidoInput.addEventListener('blur', carregarHistoricoPedido);
    pedidoInput.addEventListener('input', agendarBusca);

    // Ao abrir a edição, já mostra o histórico do pedido salvo.
    carregarHistoricoPedido();
});
// Caixa "Puxar de um protocolo existente" (tela de novo protocolo).
document.addEventListener('DOMContentLoaded', function() {
    const campo = document.getElementById('buscarProtocoloInput');
    const botao = document.getElementById('buscarProtocoloBtn');
    const resultado = document.getElementById('resultadoBuscaAnterior');
    if (!campo || !botao || !resultado) return;

    function buscar() {
        const termo = (campo.value || '').trim();
        if (!termo) {
            resultado.innerHTML = '';
            return;
        }
        botao.disabled = true;
        fetch('/protocolos/buscar-historico?q=' + encodeURIComponent(termo))
            .then(function(r) { return r.ok ? r.text() : ''; })
            .then(function(html) { resultado.innerHTML = html; })
            .catch(function() {
                resultado.innerHTML = '<div class="alert alert-danger mt-2 mb-0 py-2">Não foi possível buscar agora.</div>';
            })
            .finally(function() { botao.disabled = false; });
    }

    botao.addEventListener('click', buscar);
    campo.addEventListener('keydown', function(ev) {
        if (ev.key === 'Enter') {
            ev.preventDefault();
            buscar();
        }
    });

    resultado.addEventListener('click', function(ev) {
        const btn = ev.target.closest('button[data-origem-id]');
        if (!btn) return;
        const tipoSelect = document.getElementById('protocolType');
        const tipo = tipoSelect ? tipoSelect.value : '';
        if (!tipo) {
            alert('Escolha primeiro o tipo do protocolo novo.');
            return;
        }
        const numero = btn.dataset.origemNumero || 'protocolo anterior';
        if (!confirm('Criar um protocolo novo a partir de ' + numero + '?' +
            '\n\nOs dados serão copiados do protocolo anterior e o que já estiver preenchido abaixo será substituído.')) {
            return;
        }
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/protocolos/' + btn.dataset.origemId + '/novo-retorno';
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'type';
        input.value = tipo;
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    });
});
