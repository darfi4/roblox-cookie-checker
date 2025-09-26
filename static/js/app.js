// ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
let currentSessionId = null;
let currentResults = [];
let currentPage = 'home';
let isChecking = false;
let userStats = { total_checks: 0, total_cookies: 0, valid_cookies: 0, success_rate: 0 };

// ==================== ИНИЦИАЛИЗАЦИЯ ====================
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    loadUserStats();
});

function initializeApp() {
    initializeNavigation();
    initializeTabs();
    initializeFileUpload();
    initializeContactMenu();
    initializeEventListeners();
    setupServiceWorker();
}

// ==================== СИСТЕМА НАВИГАЦИИ ====================
function initializeNavigation() {
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const page = this.dataset.page;
            navigateTo(page);
        });
    });
}

function navigateTo(page) {
    if (currentPage === page || isChecking) return;
    
    const currentSection = document.getElementById(currentPage + 'Section');
    const newSection = document.getElementById(page + 'Section');
    const currentTab = document.querySelector(`[data-page="${currentPage}"]`);
    const newTab = document.querySelector(`[data-page="${page}"]`);
    
    // Анимация перехода
    currentSection.style.opacity = '0';
    currentSection.style.transform = 'translateX(-20px)';
    
    setTimeout(() => {
        currentSection.classList.remove('active');
        currentTab.classList.remove('active');
        
        newSection.classList.add('active');
        newTab.classList.add('active');
        
        setTimeout(() => {
            newSection.style.opacity = '1';
            newSection.style.transform = 'translateX(0)';
            currentPage = page;
            
            // Специфичные действия для страниц
            if (page === 'history') {
                loadHistory();
            }
        }, 50);
    }, 300);
}

// ==================== ЗАГРУЗКА СТАТИСТИКИ ====================
async function loadUserStats() {
    try {
        const response = await fetch('/api/stats');
        if (response.ok) {
            userStats = await response.json();
            updateStatsDisplay();
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function updateStatsDisplay() {
    document.getElementById('totalChecks').textContent = userStats.total_checks;
    document.getElementById('validAccounts').textContent = userStats.valid_cookies;
    document.getElementById('activeUsers').textContent = userStats.success_rate.toFixed(1) + '%';
}

// ==================== ПРОВЕРКА КУКИ ====================
async function checkCookies() {
    if (isChecking) return;
    
    const input = document.getElementById('cookiesInput').value.trim();
    const button = document.getElementById('checkButton');
    
    if (!input) {
        showNotification('Введите куки для проверки', 'error');
        return;
    }
    
    const cookies = input.split('\n')
        .map(c => c.trim())
        .filter(c => c && c.length > 100);
    
    if (cookies.length === 0) {
        showNotification('Не найдено валидных куки для проверки', 'error');
        return;
    }
    
    if (cookies.length > 25) {
        showNotification('Максимум 25 куки за раз', 'error');
        return;
    }

    isChecking = true;
    button.disabled = true;
    const originalContent = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ПРОВЕРКА...';

    try {
        const response = await fetch('/api/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ cookies: cookies })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentResults = data.results;
            currentSessionId = data.session_id;
            displayResults(data);
            
            const message = `Проверено: ${data.valid} валидных, ${data.invalid} невалидных`;
            showNotification(message, data.valid > 0 ? 'success' : 'warning');
            
            // Обновляем статистику и историю
            await loadUserStats();
            if (currentPage === 'history') {
                await loadHistory();
            }
        } else {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
    } catch (error) {
        console.error('Check error:', error);
        showNotification('Ошибка проверки: ' + error.message, 'error');
    } finally {
        isChecking = false;
        button.disabled = false;
        button.innerHTML = originalContent;
    }
}

// ==================== ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ ====================
function displayResults(data) {
    const container = document.getElementById('resultsContainer');
    const validResults = data.results.filter(r => r.valid);
    const invalidResults = data.results.filter(r => !r.valid);
    
    let html = `
        <div class="results-summary fade-in-up">
            <div class="stats-grid">
                <div class="cyber-stat">
                    <div class="stat-value">${data.total}</div>
                    <div class="stat-label">ВСЕГО</div>
                </div>
                <div class="cyber-stat valid">
                    <div class="stat-value">${data.valid}</div>
                    <div class="stat-label">ВАЛИДНЫХ</div>
                </div>
                <div class="cyber-stat invalid">
                    <div class="stat-value">${data.invalid}</div>
                    <div class="stat-label">НЕВАЛИДНЫХ</div>
                </div>
            </div>
    `;
    
    if (validResults.length > 0) {
        html += `
            <div class="download-section">
                <button class="cyber-button success large" onclick="downloadResults()">
                    <i class="fas fa-download"></i>
                    СКАЧАТЬ АРХИВ (${validResults.length})
                </button>
                <button class="cyber-button" onclick="viewCurrentResults()">
                    <i class="fas fa-eye"></i>
                    ПРОСМОТР РЕЗУЛЬТАТОВ
                </button>
            </div>
        `;
    }
    
    html += `</div>`;
    
    // Валидные аккаунты
    validResults.forEach((result, index) => {
        html += createAccountCard(result, index + 1);
    });
    
    // Невалидные куки
    if (invalidResults.length > 0) {
        html += `
            <div class="cyber-card error fade-in-up">
                <div class="card-header" onclick="toggleInvalidResults()" style="cursor: pointer;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h2>НЕВАЛИДНЫЕ КУКИ (${invalidResults.length})</h2>
                    <i class="fas fa-chevron-down" id="invalidToggle"></i>
                </div>
                <div class="invalid-list" id="invalidResults" style="display: none;">
                    ${invalidResults.map(result => `
                        <div class="invalid-item">
                            <code>${result.cookie.substring(0, 80)}...</code>
                            <span class="error-text">${result.error}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    // Прокрутка к результатам
    setTimeout(() => {
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

function createAccountCard(result, index) {
    const acc = result.account_info;
    const eco = result.economy;
    const prem = result.premium;
    const sec = result.security;
    
    return `
        <div class="cyber-card account-card fade-in-up">
            <div class="account-header">
                <div class="account-index">#${index}</div>
                <div class="account-main">
                    <h3 class="username">${acc.username}</h3>
                    <div class="account-details">
                        <span>ID: ${acc.user_id}</span>
                        <a href="${acc.profile_url}" target="_blank" class="profile-link">
                            <i class="fas fa-external-link-alt"></i> Профиль
                        </a>
                    </div>
                </div>
                <div class="account-value">$${result.account_value}</div>
            </div>
            
            <div class="account-grid">
                <div class="info-group">
                    <h4><i class="fas fa-id-card"></i> ИНФОРМАЦИЯ</h4>
                    <div class="info-row">
                        <span>Display Name:</span>
                        <span>${acc.display_name}</span>
                    </div>
                    <div class="info-row">
                        <span>Дата регистрации:</span>
                        <span>${acc.created_date}</span>
                    </div>
                    <div class="info-row">
                        <span>Возраст аккаунта:</span>
                        <span>${acc.account_age_years} лет (${acc.account_age_days} дней)</span>
                    </div>
                </div>
                
                <div class="info-group">
                    <h4><i class="fas fa-coins"></i> ЭКОНОМИКА</h4>
                    <div class="info-row">
                        <span>Баланс Robux:</span>
                        <span class="robux">${eco.robux_balance.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Pending Robux:</span>
                        <span>${eco.pending_robux.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Всего Robux:</span>
                        <span class="total-spent">${eco.total_robux.toLocaleString()} R$</span>
                    </div>
                </div>
                
                <div class="info-group">
                    <h4><i class="fas fa-shield-alt"></i> СТАТУС</h4>
                    <div class="info-row">
                        <span>Premium:</span>
                        <span class="status ${prem.isPremium ? 'success' : 'error'}">
                            ${prem.isPremium ? 'АКТИВНО' : 'НЕАКТИВНО'}
                        </span>
                    </div>
                    <div class="info-row">
                        <span>2FA:</span>
                        <span class="status ${sec['2fa_enabled'] ? 'success' : 'error'}">
                            ${sec['2fa_enabled'] ? 'ВКЛ' : 'ВЫКЛ'}
                        </span>
                    </div>
                    <div class="info-row">
                        <span>Друзья:</span>
                        <span>${result.social.friends_count}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// ==================== ИСТОРИЯ ПРОВЕРОК ====================
async function loadHistory() {
    const historyContent = document.getElementById('historyContent');
    historyContent.innerHTML = '<div class="empty-state"><div class="loading"></div><p>Загрузка истории...</p></div>';

    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        
        if (!response.ok) {
            throw new Error(history.error || 'Ошибка загрузки');
        }
        
        if (history.length === 0) {
            historyContent.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <h3>ИСТОРИЯ ПУСТА</h3>
                    <p>Здесь будут отображаться ваши предыдущие проверки</p>
                    <button class="cyber-button" onclick="navigateTo('home')">
                        <i class="fas fa-play"></i> НАЧАТЬ ПРОВЕРКУ
                    </button>
                </div>
            `;
            return;
        }

        let html = '<div class="history-list">';
        
        history.forEach(check => {
            const date = new Date(check.check_date);
            const formattedDate = date.toLocaleString('ru-RU');
            
            html += `
                <div class="history-item fade-in-up">
                    <div class="history-header">
                        <div class="history-id">#${check.id}</div>
                        <div class="history-date">${formattedDate}</div>
                        <div class="history-stats">
                            <span class="stat valid">${check.valid_cookies} ВАЛИД</span>
                            <span class="stat total">${check.total_cookies} ВСЕГО</span>
                            <span class="stat invalid">${check.total_cookies - check.valid_cookies} НЕВАЛИД</span>
                        </div>
                    </div>
                    
                    <div class="history-actions">
                        <button class="cyber-button small" onclick="viewResults('${check.session_id}')">
                            <i class="fas fa-eye"></i> ПРОСМОТР
                        </button>
                        <button class="cyber-button success small" onclick="downloadSession('${check.session_id}')">
                            <i class="fas fa-download"></i> СКАЧАТЬ
                        </button>
                        <button class="cyber-button error small" onclick="deleteSession('${check.session_id}')">
                            <i class="fas fa-trash"></i> УДАЛИТЬ
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        historyContent.innerHTML = html;
        
    } catch (error) {
        console.error('History load error:', error);
        historyContent.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>ОШИБКА ЗАГРУЗКИ</h3>
                <p>${error.message}</p>
                <button class="cyber-button" onclick="loadHistory()">
                    <i class="fas fa-sync-alt"></i> ПОВТОРИТЬ
                </button>
            </div>
        `;
    }
}

async function clearAllHistory() {
    if (!confirm('Вы уверены, что хотите очистить всю историю? Это действие нельзя отменить.')) {
        return;
    }

    try {
        const history = await fetch('/api/history').then(r => r.json());
        const deletePromises = history.map(check => 
            fetch(`/api/delete/${check.session_id}`, { method: 'DELETE' })
        );
        
        await Promise.all(deletePromises);
        showNotification('Вся история очищена', 'success');
        loadHistory();
    } catch (error) {
        showNotification('Ошибка очистки истории', 'error');
    }
}

// ==================== МОДАЛЬНЫЕ ОКНА ====================
async function viewResults(sessionId) {
    try {
        const response = await fetch(`/api/session/${sessionId}`);
        const data = await response.json();
        
        if (response.ok) {
            displayModalResults(data);
            document.getElementById('resultsModal').style.display = 'block';
        } else {
            throw new Error(data.error || 'Ошибка загрузки');
        }
    } catch (error) {
        showNotification('Ошибка загрузки результатов: ' + error.message, 'error');
    }
}

function viewCurrentResults() {
    if (!currentResults.length) return;
    
    displayModalResults({
        total: currentResults.length,
        valid: currentResults.filter(r => r.valid).length,
        invalid: currentResults.filter(r => !r.valid).length,
        results: currentResults
    });
    document.getElementById('resultsModal').style.display = 'block';
}

function displayModalResults(data) {
    const modalContent = document.getElementById('modalResults');
    const validResults = data.results.filter(r => r.valid);
    
    let html = `
        <div class="results-summary">
            <div class="stats-grid">
                <div class="cyber-stat">
                    <div class="stat-value">${data.total}</div>
                    <div class="stat-label">ВСЕГО</div>
                </div>
                <div class="cyber-stat valid">
                    <div class="stat-value">${data.valid}</div>
                    <div class="stat-label">ВАЛИДНЫХ</div>
                </div>
                <div class="cyber-stat invalid">
                    <div class="stat-value">${data.invalid}</div>
                    <div class="stat-label">НЕВАЛИДНЫХ</div>
                </div>
            </div>
        </div>
    `;
    
    if (validResults.length > 0) {
        html += `
            <div class="valid-accounts">
                <h4><i class="fas fa-user-check"></i> ВАЛИДНЫЕ АККАУНТЫ (${validResults.length})</h4>
                <div class="accounts-list">
                    ${validResults.map(result => `
                        <div class="account-preview">
                            <div class="preview-main">
                                <strong>${result.account_info.username}</strong>
                                <span>ID: ${result.account_info.user_id}</span>
                            </div>
                            <div class="preview-stats">
                                <span class="robux">${result.economy.total_robux} R$</span>
                                <span class="status ${result.premium.isPremium ? 'success' : 'error'}">
                                    ${result.premium.isPremium ? 'PREMIUM' : 'STANDARD'}
                                </span>
                                <span class="value">$${result.account_value}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    const invalidResults = data.results.filter(r => !r.valid);
    if (invalidResults.length > 0) {
        html += `
            <div class="invalid-accounts">
                <h4><i class="fas fa-times-circle"></i> НЕВАЛИДНЫЕ КУКИ (${invalidResults.length})</h4>
                <div class="invalid-list-modal">
                    ${invalidResults.map(result => `
                        <div class="invalid-item-modal">
                            <code>${result.cookie.substring(0, 60)}...</code>
                            <span class="error-text">${result.error}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    modalContent.innerHTML = html;
}

function closeModal() {
    document.getElementById('resultsModal').style.display = 'none';
}

// ==================== ДЕЙСТВИЯ С СЕССИЯМИ ====================
function downloadResults() {
    if (!currentSessionId) return;
    window.open(`/api/download/${currentSessionId}`, '_blank');
    showNotification('Архив скачивается...', 'success');
}

function downloadSession(sessionId) {
    window.open(`/api/download/${sessionId}`, '_blank');
    showNotification('Архив скачивается...', 'success');
}

async function deleteSession(sessionId) {
    if (!confirm('Удалить эту запись из истории?')) {
        return;
    }

    try {
        const response = await fetch(`/api/delete/${sessionId}`, { 
            method: 'DELETE' 
        });
        
        if (response.ok) {
            showNotification('Запись удалена', 'success');
            loadHistory();
        } else {
            const data = await response.json();
            throw new Error(data.error || 'Ошибка удаления');
        }
    } catch (error) {
        showNotification('Ошибка удаления: ' + error.message, 'error');
    }
}

// ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
function toggleInvalidResults() {
    const content = document.getElementById('invalidResults');
    const toggle = document.getElementById('invalidToggle');
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.classList.replace('fa-chevron-down', 'fa-chevron-up');
    } else {
        content.style.display = 'none';
        toggle.classList.replace('fa-chevron-up', 'fa-chevron-down');
    }
}

async function updateStats() {
    try {
        const history = await fetch('/api/history').then(r => r.json());
        const totalChecks = history.length;
        const validAccounts = history.reduce((sum, check) => sum + check.valid_cookies, 0);
        
        document.getElementById('totalChecks').textContent = totalChecks;
        document.getElementById('validAccounts').textContent = validAccounts;
        document.getElementById('activeUsers').textContent = Math.floor(validAccounts * 0.7); // Примерная статистика
    } catch (error) {
        console.error('Stats update error:', error);
    }
}

function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('notificationContainer');
    const notification = document.createElement('div');
    notification.className = `cyber-notification ${type}`;
    
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-triangle',
        'warning': 'exclamation-circle',
        'info': 'info-circle'
    };
    
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${icons[type] || 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <div class="notification-progress"></div>
    `;
    
    // Стили для прогрессбара
    const style = document.createElement('style');
    style.textContent = `
        .notification-progress {
            position: absolute;
            bottom: 0;
            left: 0;
            height: 3px;
            background: ${getNotificationColor(type)};
            width: 100%;
            transform: scaleX(1);
            transform-origin: left;
            animation: progress ${duration}ms linear forwards;
        }
        
        @keyframes progress {
            to { transform: scaleX(0); }
        }
    `;
    document.head.appendChild(style);
    
    container.appendChild(notification);
    
    // Анимация появления
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Автоматическое скрытие
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
            style.remove();
        }, 300);
    }, duration);
    
    // Закрытие по клику
    notification.addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
            style.remove();
        }, 300);
    });
}

function getNotificationColor(type) {
    const colors = {
        'success': '#00ff88',
        'error': '#ff3860',
        'warning': '#ffdd57',
        'info': '#209cee'
    };
    return colors[type] || '#209cee';
}


// ==================== SERVICE WORKER ====================
function setupServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('Service Worker registered');
            })
            .catch(error => {
                console.log('Service Worker registration failed:', error);
            });
    }
}

// ==================== ГЛОБАЛЬНЫЕ ФУНКЦИИ ====================
window.navigateTo = navigateTo;
window.checkCookies = checkCookies;
window.downloadResults = downloadResults;
window.downloadSession = downloadSession;
window.deleteSession = deleteSession;
window.viewResults = viewResults;
window.viewCurrentResults = viewCurrentResults;
window.toggleInvalidResults = toggleInvalidResults;
window.closeModal = closeModal;
window.loadHistory = loadHistory;
window.clearAllHistory = clearAllHistory;