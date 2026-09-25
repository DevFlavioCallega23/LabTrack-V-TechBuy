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
    respOptions: mapFromPairs(PF.respOptions)
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
const RESP_OPTS = optionsHtml(CFG.respOptions);
const statusOptsSelected = function(sel) { return optionsSelectedHtml(CFG.statusOptions, sel); };
const respOptsSelected = function(sel) { return optionsSelectedHtml(CFG.respOptions, sel); };

const COMP_LABELS = {};
const COMP_ORDER = [];
COMP_TYPES_DB.forEach(function(t) {
    COMP_LABELS[t.key] = t.label;
    COMP_ORDER.push(t.key);
});
const EXTRA_OPTS = '<option value="">-- Selecione --</option>' +
    COMP_ORDER.map(function(k) { return `<option value="${k}">${COMP_LABELS[k]}</option>`; }).join('');

const MACHINES_FROM_TEST = CFG.rmaTestData.map(function(it) { return it.machine; })
    .filter(function(m, i, arr) { return m && arr.indexOf(m) === i; });
const MACHINES = CFG.machines.concat(
    MACHINES_FROM_TEST.filter(function(m) { return CFG.machines.indexOf(m) === -1; }));
const MACHINE_OPTS = '<option value="">--</option>' +
    MACHINES.map(function(m) { return `<option value="${m}">${m}</option>`; }).join('');

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
        tipos.map(t => `<option value="${t}">${COMP_LABELS[t] || t}</option>`).join('');
    if (currentType) typeSelect.value = currentType;
    typeSelect.onchange = function() {
        updateModelOptions(typeSelect, modelInput, produtoIdInput);
    };
    if (currentType) updateModelOptions(typeSelect, modelInput, produtoIdInput);
}

function updateModelOptions(typeSelect, modelInput, produtoIdInput) {
    if (!modelInput || !typeSelect) return;
    const tipo = typeSelect.value;
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
    datalist.innerHTML = produtos.map(p => `<option value="${p.model_name}" data-id="${p.id}">${p.model_name}</option>`).join('');
    modelInput.setAttribute('list', datalistId);
    modelInput.placeholder = 'Selecione ou digite...';
    modelInput.oninput = function() {
        const match = produtos.find(p => p.model_name.toLowerCase() === modelInput.value.toLowerCase());
        if (produtoIdInput) produtoIdInput.value = match ? match.id : '';
    };
    const match = produtos.find(p => p.model_name.toLowerCase() === modelInput.value.toLowerCase());
    if (produtoIdInput) produtoIdInput.value = match ? match.id : '';
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
            names.map(n => `<option value="${n}">${n}</option>`).join('');
        if (cur) sel.value = cur;
    });
}
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
            names.map(n => `<option value="${n}">${n}</option>`).join('');
        if (cur) sel.value = cur;
    });
}

let machineCount = 0;
let rmaMachineCount = 0;

function machineHTML(num, name, isPrebuilt, powerCableVal) {
    const n = String(num).padStart(2, '0');
    const label = name || `Máquina ${n}`;
    const checked = isPrebuilt ? 'checked' : '';
    const pcVal = powerCableVal || 'OK';
    return `
    <div class="card bg-dark border-secondary mb-3 machine-block" data-machine="${n}">
        <div class="card-header d-flex justify-content-between align-items-center py-2 flex-wrap gap-2">
            <div class="d-flex align-items-center gap-3 flex-wrap">
                <input type="text" name="machine_name_${n}" class="form-control form-control-sm bg-dark text-light border-secondary fw-bold" style="width:auto;min-width:200px;display:inline-block" value="${label}">
                <div class="form-check form-switch mb-0">
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
            <input type="text" name="rma_machine_name_${n}" class="form-control form-control-sm bg-dark text-light border-secondary fw-bold" style="width:auto;min-width:200px;display:inline-block" value="${label}">
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
    const srcPE = srcBlock.querySelector('.form-check-input');
    const isPE = srcPE ? srcPE.checked : false;
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
        const serial = '';
        const isPE = srcBlock.querySelector('.form-check-input') ? srcBlock.querySelector('.form-check-input').checked : false;
        const showBtn = (isPE && !serial) ? '' : 'style="display:none"';
        const showInput = (!isPE || serial) ? '' : 'style="display:none"';
        tr.innerHTML = `
            <td><select name="comp_type_${dstMachine}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select></td>
            <td><input type="text" name="comp_model_${dstMachine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${srcModel ? srcModel.value : ''}"></td>
            <td>
                <div class="d-flex align-items-center gap-1">
                    <button type="button" class="btn btn-sm btn-outline-warning pe-ref-btn py-0 px-1" ${showBtn} onclick="addRefSerial(this)" title="Adicionar NS de referência"><i class="bi bi-plus-lg"></i></button>
                    <input type="text" name="comp_serial_${dstMachine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${serial}">
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
        select.value = srcSelect ? srcSelect.value : '';
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
                <td><input type="text" name="rma_comp_model_${dstMachine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${srcModel ? srcModel.value : ''}"></td>
                <td>
                    <div class="d-flex align-items-center gap-1">
                        <button type="button" class="btn btn-sm btn-outline-warning rma-ref-btn py-0 px-1" ${showBtn} onclick="addRmaRefSerial(this)" title="Adicionar NS"><i class="bi bi-plus-lg"></i></button>
                        <input type="text" name="rma_comp_serial_${dstMachine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${serial}">
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

function updateRmaTestNsColumns() {
    const show = rmaTestHasNs();
    const header = document.getElementById('rmaTestNsHeader');
    if (header) header.style.display = show ? '' : 'none';
    document.querySelectorAll('#rmaTestTable .rma-test-ns-cell').forEach(function(c) {
        c.style.display = show ? '' : 'none';
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
        names.map(n => `<option value="${n}">${n}</option>`).join('');
}

function addRmaTestRow() {
    const tbody = document.querySelector('#rmaTestTable tbody');
    const opts = '<option value="">-- Selecione --</option>' +
        Object.entries(COMP_LABELS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('');
    const tr = document.createElement('tr');
    tr.className = 'rma-test-row';
    tr.innerHTML = `
        <td><select name="rma_test_machine[]" class="form-select form-select-sm">${currentRmaMachineOpts()}</select></td>
        <td><select name="rma_test_comp[]" class="form-select form-select-sm">${opts}</select></td>
        <td><input type="text" name="rma_test_model[]" class="form-control form-control-sm" placeholder="Ex: I5-2400"></td>
        <td class="rma-test-ns-cell" style="display:${rmaTestHasNs() ? '' : 'none'}"><input type="text" name="rma_test_serial[]" class="form-control form-control-sm" placeholder="Nº de Série"></td>
        <td><input type="text" name="rma_test_defeito[]" class="form-control form-control-sm" placeholder="Descrição do defeito"></td>
        <td><input type="text" name="rma_test_pedido[]" class="form-control form-control-sm" placeholder="Pedido"></td>
        <td><input type="text" name="rma_test_data_compra[]" class="form-control form-control-sm date-mask" placeholder="DD/MM/AAAA"></td>
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
        names.map(n => `<option value="${n}"${n === selected ? ' selected' : ''}>${n}</option>`).join('');
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
            <input type="text" name="trocado_machine_name_${n}" class="form-control form-control-sm bg-dark text-light border-secondary fw-bold" style="width:auto;min-width:200px;display:inline-block" value="${label}" oninput="syncTrocadoMachines()">
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
            <td><input type="text" name="trocado_comp_model_${dstMachine}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${srcModel ? srcModel.value : ''}"></td>
            <td><input type="text" name="trocado_comp_serial_${dstMachine}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" minlength="3" value="${serial}"></td>
            <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
        `;
        const selects = tr.querySelectorAll('select');
        if (selects[1]) selects[1].value = srcTypeSel ? srcTypeSel.value : '';
        dstTbody.appendChild(tr);
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
                <td><input type="text" name="trocado_comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${item.model || ''}"></td>
                <td><input type="text" name="trocado_comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" minlength="3" value="${item.serial || ''}"></td>
                <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
            `;
            const selects = tr.querySelectorAll('select');
            if (selects[1]) selects[1].value = item.type || '';
            tbody.appendChild(tr);
        });
    });
    trocadoMachineCount = maxM || 0;
    if (trocadoMachineCount === 0) addTrocadoMachine();
}

function togglePE(cb) {
    const block = cb.closest('.machine-block');
    const isPE = cb.checked;
    block.querySelectorAll('.comp-row').forEach(function(row) {
        const btn = row.querySelector('.pe-ref-btn');
        const input = row.querySelector('.serial-input');
        if (!input) return;
        if (isPE) {
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
    const isPE = machineBlock.querySelector('.form-check-input').checked;
    const isComum = document.getElementById('materialComum') && document.getElementById('materialComum').checked;
    const tr = document.createElement('tr');
    tr.className = 'comp-row';
    const showBtn = isPE ? '' : 'style="display:none"';
    const showInput = isPE ? 'style="display:none"' : '';
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
        const isPE = entry.is_prebuilt || false;
        const pc = entry.power_cable || 'OK';
        container.insertAdjacentHTML('beforeend', machineHTML(num, machineName, isPE, pc));
        const block = container.lastElementChild;
        const tbody = block.querySelector('.machine-body');
        const cb = block.querySelector('.form-check-input');
        if (isPE) cb.checked = true;
        comps.forEach(function(item) {
            const tr = document.createElement('tr');
            tr.className = 'comp-row';
            const hasSerial = item.serial ? true : false;
            const showBtn = (isPE && !hasSerial) ? '' : 'style="display:none"';
            const showInput = (!isPE || hasSerial) ? '' : 'style="display:none"';
            tr.innerHTML = `
                <td>
                    <select name="comp_type_${m}[]" class="form-select form-select-sm">${EXTRA_OPTS}</select>
                    <input type="hidden" name="comp_product_id_${m}[]" value="${item.product_id || ''}">
                </td>
                <td><input type="text" name="comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${item.model || ''}"></td>
                <td>
                    <div class="d-flex align-items-center gap-1">
                        <button type="button" class="btn btn-sm btn-outline-warning pe-ref-btn py-0 px-1" ${showBtn} onclick="addRefSerial(this)" title="Adicionar NS de referência"><i class="bi bi-plus-lg"></i></button>
                        <input type="text" name="comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${item.serial || ''}">
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
    const opts = '<option value="">-- Selecione --</option>' +
        Object.entries(COMP_LABELS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('');
    const tr = document.createElement('tr');
    tr.className = 'defect-row';
    tr.innerHTML = `
        <td><select name="defect_type[]" class="form-select form-select-sm">${opts}</select></td>
        <td class="maquina-col"><select name="defect_maquina[]" class="form-select form-select-sm">${MACHINE_OPTS}</select></td>
        <td><input type="text" name="defect_model[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..."></td>
        <td><input type="text" name="defect_serial[]" class="form-control form-control-sm" placeholder="NS do componente com defeito"></td>
        <td><input type="text" name="defect_desc[]" class="form-control form-control-sm" placeholder="Ex: Não liga, não dá vídeo..."></td>
        <td>
            <select name="defect_resp[]" class="form-select form-select-sm">
                <option value=\"\">--</option>
                ${RESP_OPTS}
            </select>
        </td>
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
                    <input type="text" name="passagem_protocolo[]" class="form-control form-control-sm" placeholder="Opcional" value="${p.protocolo || ''}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">Data Entrada</label>
                    <input type="text" name="passagem_data_entrada[]" class="form-control form-control-sm" placeholder="DD/MM/AAAA" value="${p.data_entrada || ''}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">Data Saída</label>
                    <input type="text" name="passagem_data_saida[]" class="form-control form-control-sm" placeholder="DD/MM/AAAA" value="${p.data_saida || ''}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">Pedido do produto com defeito</label>
                    <input type="text" name="passagem_pedido[]" class="form-control form-control-sm" placeholder="Pedido do defeito" value="${p.pedido || ''}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">NS do produto com defeito</label>
                    <input type="text" name="passagem_ns[]" class="form-control form-control-sm" placeholder="NS do defeito" value="${p.ns || ''}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small mb-0">NS do novo produto</label>
                    <input type="text" name="passagem_ns_novo[]" class="form-control form-control-sm" placeholder="NS do novo" value="${p.ns_novo || ''}">
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
                <td><input type="text" name="rma_comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${item.model || ''}"></td>
                <td>
                    <div class="d-flex align-items-center gap-1">
                        <button type="button" class="btn btn-sm btn-outline-warning rma-ref-btn py-0 px-1" ${showBtn} onclick="addRmaRefSerial(this)" title="Adicionar NS"><i class="bi bi-plus-lg"></i></button>
                        <input type="text" name="rma_comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" ${showInput} value="${item.serial || ''}">
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
        Object.entries(COMP_LABELS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('');
    items.forEach(function(item) {
        const tr = document.createElement('tr');
        tr.className = 'rma-test-row';
        tr.innerHTML = `
            <td><select name="rma_test_machine[]" class="form-select form-select-sm">${MACHINE_OPTS}</select></td>
            <td><select name="rma_test_comp[]" class="form-select form-select-sm">${opts}</select></td>
            <td><input type="text" name="rma_test_model[]" class="form-control form-control-sm" value="${item.model || ''}"></td>
            <td class="rma-test-ns-cell" style="display:${rmaTestHasNs() ? '' : 'none'}"><input type="text" name="rma_test_serial[]" class="form-control form-control-sm" placeholder="Nº de Série" value="${item.serial || ''}"></td>
            <td><input type="text" name="rma_test_defeito[]" class="form-control form-control-sm" value="${item.defeito || ''}"></td>
            <td><input type="text" name="rma_test_pedido[]" class="form-control form-control-sm" value="${item.pedido || ''}"></td>
            <td><input type="text" name="rma_test_data_compra[]" class="form-control form-control-sm date-mask" value="${item.data_compra || ''}"></td>
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
        if (item.machine) tr.querySelector('select[name="rma_test_machine[]"]').value = item.machine;
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
                <td><input type="text" name="trocado_comp_model_${m}[]" class="form-control form-control-sm" placeholder="Ex: I5-2400, 8GB..." value="${item.model || ''}"></td>
                <td><input type="text" name="trocado_comp_serial_${m}[]" class="form-control form-control-sm serial-input" placeholder="Nº de Série" minlength="3" value="${item.serial || ''}"></td>
                <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove()"><i class="bi bi-x"></i></button></td>
            `;
            const selects = tr.querySelectorAll('select');
            if (selects[1]) selects[1].value = type;
            tbody.appendChild(tr);
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
            <td><input type="text" class="form-control form-control-sm win-key-chave" placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX" value="${chave || ''}"></td>
            <td><input type="text" class="form-control form-control-sm win-key-fonte" placeholder="NS da Fonte" value="${fonte || ''}"></td>
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
        var equipHeading = document.getElementById('equipClientHeading');
        if (equipHeading) equipHeading.style.display = isNaoComprado ? '' : 'none';
        var entryLabel = document.getElementById('entryDateLabel');
        if (entryLabel) entryLabel.textContent = type === 'nao_comprado' ? 'Data de Entrada' : 'Data da Compra';
        if (sectionClient) sectionClient.style.display = type === 'ponta_entrega' ? 'none' : 'block';
        var rmaDataHeading = document.getElementById('rmaDataHeading');
        if (rmaDataHeading) rmaDataHeading.textContent = type === 'servico' ? 'Dados do Serviço' : 'Dados do RMA';
        var rmaWarrantyInfo = document.getElementById('rmaWarrantyInfo');
        if (rmaWarrantyInfo) rmaWarrantyInfo.value = type === 'rma' ? 'Sim' : 'Não';
        var obsLabel = document.getElementById('obsLabel');
        if (obsLabel) {
            obsLabel.innerHTML = (isRma
                ? '<i class="bi bi-exclamation-triangle text-warning"></i> Defeito Relatado / Observações Técnicas'
                : '<i class="bi bi-chat-dots"></i> Observações');
        }
        updateRmaTestNsColumns();
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
            items.push({
                machine: mval,
                component: comp ? comp.value : '',
                model: model ? model.value : '',
                serial: serial ? serial.value : '',
                defeito: defeito ? defeito.value : '',
                pedido: pedido ? pedido.value : '',
                data_compra: dataCompra ? dataCompra.value : '',
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
