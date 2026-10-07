// Promessa de adição de produto ainda em andamento (segura o submit do form).
window.adicaoPendente = null;

// Cria o produto no catálogo via API e atualiza a lista local.
window.adicionarProdutoCatalogo = function(tipo, modelo, catalogo) {
    return fetch('/produtos/api/criar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ component_type: tipo, model_name: modelo })
    }).then(function(res) {
        return res.json().catch(function() { return {}; }).then(function(dados) {
            if (!res.ok) throw new Error(dados.erro || 'Não foi possível adicionar o produto.');
            var lista = catalogo || [];
            if (!lista.some(function(p) { return p.id === dados.id; })) {
                lista.push({
                    id: dados.id,
                    component_type: dados.component_type,
                    model_name: dados.model_name
                });
            }
            return dados;
        });
    });
};

// Se o modelo digitado não existe no catálogo, pergunta e cria na hora.
// Preenche o hidden do produto e atualiza o datalist quando der certo.
window.tentarAdicionarModelo = function(tipo, modelo, catalogo, modelInput, produtoIdInput) {
    if (!tipo || !modelo) return Promise.resolve(null);
    var existe = (catalogo || []).find(function(p) {
        return p.component_type === tipo &&
            p.model_name.toLowerCase() === modelo.toLowerCase();
    });
    if (existe) {
        if (produtoIdInput) produtoIdInput.value = existe.id;
        return Promise.resolve(existe);
    }
    if (!window.confirm('Modelo "' + modelo + '" não está em Produtos.\n\nAdicionar ao catálogo agora?')) {
        if (produtoIdInput) produtoIdInput.value = '';
        return Promise.resolve(null);
    }
    var promessa = window.adicionarProdutoCatalogo(tipo, modelo, catalogo)
        .then(function(p) {
            if (produtoIdInput) produtoIdInput.value = p.id;
            if (modelInput) {
                var listId = modelInput.getAttribute('list');
                var dl = listId ? document.getElementById(listId) : null;
                if (dl && !Array.from(dl.options).some(function(o) { return o.value === p.model_name; })) {
                    var o = document.createElement('option');
                    o.value = p.model_name;
                    dl.appendChild(o);
                }
            }
            return p;
        })
        .catch(function(e) {
            window.alert(e.message || 'Erro ao adicionar produto.');
            return null;
        });
    window.adicaoPendente = promessa;
    promessa.then(function() {
        if (window.adicaoPendente === promessa) window.adicaoPendente = null;
    });
    return promessa;
};

// Se houver adição pendente quando o form for enviado, espera e reenvia.
document.addEventListener('submit', function(e) {
    if (!window.adicaoPendente) return;
    e.preventDefault();
    var form = e.target;
    var pend = window.adicaoPendente;
    window.adicaoPendente = null;
    pend.then(function() {
        if (typeof form.requestSubmit === 'function') form.requestSubmit();
        else form.submit();
    });
}, true);

window.initDateMask = function(scope) {
    var root = scope || document;
    var dateInputs = root.querySelectorAll('.date-mask');
    dateInputs.forEach(function(input) {
        if (input.dataset.maskBound) return;
        input.dataset.maskBound = '1';
        input.addEventListener('input', function(e) {
            var value = this.value.replace(/\D/g, '');
            if (value.length > 8) value = value.slice(0, 8);
            var formatted = '';
            for (var i = 0; i < value.length; i++) {
                if (i === 2 || i === 4) formatted += '/';
                formatted += value[i];
            }
            this.value = formatted;
        });

        input.addEventListener('blur', function() {
            var parts = this.value.split('/');
            if (parts.length === 3 && parts[2].length === 2) {
                parts[2] = '20' + parts[2];
                this.value = parts.join('/');
            }
        });
    });
};

document.addEventListener('DOMContentLoaded', function() {
    var alerts = document.querySelectorAll('.alert');
    setTimeout(function() {
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    var rows = document.querySelectorAll('.clickable-row');
    rows.forEach(function(row) {
        row.addEventListener('click', function(e) {
            if (e.target.closest('.action-btns')) return;
            var href = this.getAttribute('data-href');
            if (href) window.location.href = href;
        });
    });

    // Enter navigates to next field in all forms
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                var formEls = Array.from(this.querySelectorAll('input, select, button:not([type="submit"])'));
                var idx = formEls.indexOf(e.target);
                if (idx >= 0 && idx < formEls.length - 1) {
                    formEls[idx + 1].focus();
                }
            }
        });
    });

    initDateMask();
});