document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form.classList.contains('ajax-modal-form')) {
        return;
    }
    event.preventDefault();

    var modalBody = form.closest('.modal-body');
    var submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
    }

    fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        })
        .then(function (result) {
            if (result.ok && result.data.success) {
                window.location.href = result.data.redirect_url;
                return;
            }
            if (modalBody) {
                modalBody.innerHTML = result.data.html;
            }
        })
        .catch(function () {
            if (submitButton) {
                submitButton.disabled = false;
            }
        });
});
