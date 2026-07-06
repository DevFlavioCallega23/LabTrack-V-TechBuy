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
});
