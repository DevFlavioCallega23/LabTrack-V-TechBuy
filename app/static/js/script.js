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

    var dateInputs = document.querySelectorAll('.date-mask');
    dateInputs.forEach(function(input) {
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
});
