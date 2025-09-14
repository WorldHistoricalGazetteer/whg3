// profile.js

import { initClipboard } from './utilities'

const {apiTokenUrl, newsToggleUrl, csrfToken} = window.profileConfig;
const tokenSection = document.getElementById('api-token-section');
const tokenCode = document.getElementById('api-token');

function setState(hasToken, tokenValue = null) {
    tokenSection.classList.toggle('has-token', hasToken);
    if (hasToken && tokenValue) {
        tokenCode.textContent = tokenValue;
    }
}

function requestToken(action) {
    return fetch(apiTokenUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest'},
        body: new URLSearchParams({action})
    }).then(r => r.json());
}

initClipboard();

tokenSection.querySelectorAll('#has-token button').forEach(button => {
    button.setAttribute('data-bs-title', 'This will immediately invalidate the existing token');
    button.setAttribute('data-bs-toggle', 'tooltip');
});

document.body.addEventListener('click', function (e) {
    if (e.target.closest('.generate-token')) {
        requestToken('generate').then(data => {
            if (data.token) setState(true, data.token);
            else if (data.error) alert(data.error);
        }).catch(() => alert('Failed to generate token.'));
    }

    if (e.target.closest('.delete-token')) {
        if (!confirm("Are you sure you want to delete your API token?")) return;
        fetch(apiTokenUrl, {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest'},
            body: new URLSearchParams({'action': 'delete'})
        })
            .then(resp => resp.json())
            .then(data => {
                if (data.success) setState(false);
                else if (data.error) alert(data.error);
            })
            .catch(() => alert('Failed to delete token.'));
    }
});

const newsCheckbox = document.getElementById('id_news_permitted');
if (newsCheckbox) {
    newsCheckbox.addEventListener('change', function () {
        const formData = new FormData();
        formData.append('news_permitted', newsCheckbox.checked ? 'on' : '');
        formData.append('csrfmiddlewaretoken', csrfToken);

        fetch(newsToggleUrl, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: formData
        }).then(response => {
            if (!response.ok) {
                alert('Failed to save news preferences.');
            }
        }).catch(() => {
            alert('Failed to save news preferences.');
        });
    });
}
