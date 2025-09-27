// Глобальные переменные
let currentSessionId = null;
let currentResults = [];
let isChecking = false;

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    initializeParticles();
    initializeNavigation();
    initializeTabs();
    initializeFileUpload();
    initializeContactMenu();
    initializeEventListeners();
    loadGlobalStats();
    
    // Обновляем статистику каждые 30 секунд
    setInterval(loadGlobalStats, 30000);
}

// Безопасные функции для работы с числами
function safeToLocaleString(num, defaultValue = 0) {
    if (num === undefined || num === null) {
        return defaultValue.toLocaleString();
    }
    try {
        return Number(num).toLocaleString();
    } catch (e) {
        return defaultValue.toLocaleString();
    }
}

function safeNumber(num, defaultValue = 0) {
    if (num === undefined || num === null) {
        return defaultValue;
    }
    try {
        return Number(num);
    } catch (e) {
        return defaultValue;
    }
}

// Инициализация частиц
function initializeParticles() {
    const canvas = document.getElementById('particlesCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    
    const particles = [];
    const particleCount = 100;
    
    for (let i = 0; i < particleCount; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 2 + 1,
            speedX: (Math.random() - 0.5) * 0.5,
            speedY: (Math.random() - 0.5) * 0.5,
            color: `hsl(${Math.random() * 360}, 100%, 60%)`
        });
    }
    
    const mouse = { x: undefined, y: undefined, radius: 100 };
    
    window.addEventListener('mousemove', function(event) {
        mouse.x = event.x;
        mouse.y = event.y;
    });
    
    window.addEventListener('mouseout', function() {
        mouse.x = undefined;
        mouse.y = undefined;
    });
    
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        for (let i = 0; i < particles.length; i++) {
            let p = particles[i];
            
            p.x += p.speedX;
            p.y += p.speedY;
            
            if (p.x < 0 || p.x > canvas.width) p.speedX *= -1;
            if (p.y < 0 || p.y > canvas.height) p.speedY *= -1;
            
            if (mouse.x && mouse.y) {
                let dx = mouse.x - p.x;
                let dy = mouse.y - p.y;
                let distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < mouse.radius) {
                    let angle = Math.atan2(dy, dx);
                    let force = (mouse.radius - distance) / mouse.radius;
                    p.x -= Math.cos(angle) * force * 2;
                    p.y -= Math.sin(angle) * force * 2;
                }
            }
            
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.fill();
            
            for (let j = i + 1; j < particles.length; j++) {
                let p2 = particles[j];
                let dx = p.x - p2.x;
                let dy = p.y - p2.y;
                let distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < 100) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(139, 92, 246, ${0.2 * (1 - distance/100)})`;
                    ctx.lineWidth = 0.5;
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
            }
        }
        
        requestAnimationFrame(animate);
    }
    
    animate();
}

// Навигация
function initializeNavigation() {
    const tabs = document.querySelectorAll('.main-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetPage = this.getAttribute('data-page');
            switchPage(targetPage);
        });
    });
}

function switchPage(pageName) {
    document.querySelectorAll('.page-section').forEach(section => {
        section.classList.remove('active');
    });
    
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    const targetSection = document.getElementById(pageName + 'Section');
    if (targetSection) {
        targetSection.classList.add('active');
    }
    
    const activeTab = document.querySelector(`[data-page="${pageName}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }
    
    if (pageName === 'history') {
        loadHistory();
    }
}

// Вкладки
function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    const activeButton = document.querySelector(`[data-tab="${tabName}"]`);
    if (activeButton) {
        activeButton.classList.add('active');
    }
    
    const activeContent = document.getElementById(tabName + '-tab');
    if (activeContent) {
        activeContent.classList.add('active');
    }
}

// Загрузка файлов
function initializeFileUpload() {
    const fileInput = document.getElementById('fileInput');
    const uploadZone = document.getElementById('fileUploadZone');
    
    if (uploadZone && fileInput) {
        uploadZone.addEventListener('click', () => fileInput.click());
        uploadZone.addEventListener('dragover', handleDragOver);
        uploadZone.addEventListener('drop', handleFileDrop);
        fileInput.addEventListener('change', handleFileSelect);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.style.borderColor = 'var(--neon-purple)';
    e.currentTarget.style.background = 'rgba(139, 92, 246, 0.1)';
}

function handleFileDrop(e) {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFiles(files[0]);
    }
}

function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        handleFiles(e.target.files[0]);
    }
}

async function handleFiles(file) {
    try {
        const text = await readFileAsText(file);
        const cookies = extractCookiesFromText(text);
        
        if (cookies.length > 0) {
            document.getElementById('cookiesInput').value = cookies.join('\n');
            switchTab('text');
            showNotification(`Загружено ${cookies.length} куки из файла`, 'success');
        } else {
            showNotification('В файле не найдено валидных куки', 'warning');
        }
    } catch (error) {
        showNotification('Ошибка чтения файла', 'error');
    }
}

function extractCookiesFromText(text) {
    // Упрощенное извлечение куки - берем все что похоже на куки
    const lines = text.split('\n');
    const cookies = [];
    
    for (let line of lines) {
        line = line.trim();
        if (line.length > 100 && line.includes('WARNING:-DO-NOT-SHARE-THIS')) {
            // Очищаем куки от мусора
            let cookie = line.replace(/\s+/g, ' ').trim();
            
            // Убираем кавычки если есть
            if (cookie.startsWith('"') && cookie.endsWith('"')) {
                cookie = cookie.slice(1, -1);
            }
            if (cookie.startsWith("'") && cookie.endsWith("'")) {
                cookie = cookie.slice(1, -1);
            }
            
            // Убираем лишние пробелы
            cookie = cookie.replace(/\s+/g, '');
            
            if (cookie.length > 100) {
                cookies.push(cookie);
            }
        }
    }
    
    return cookies.slice(0, 3000);
}

function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsText(file);
    });
}

// Меню контактов
function initializeContactMenu() {
    const contactButton = document.getElementById('contactButton');
    const closeButton = document.getElementById('closeContact');
    const overlay = document.getElementById('menuOverlay');
    
    if (contactButton) contactButton.addEventListener('click', openContactMenu);
    if (closeButton) closeButton.addEventListener('click', closeContactMenu);
    if (overlay) overlay.addEventListener('click', closeContactMenu);
    
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeContactMenu();
    });
}

function openContactMenu() {
    const overlay = document.getElementById('menuOverlay');
    const menu = document.getElementById('contactMenu');
    
    if (overlay && menu) {
        overlay.style.display = 'block';
        menu.style.display = 'block';
        setTimeout(() => {
            overlay.classList.add('active');
            menu.classList.add('active');
        }, 10);
    }
}

function closeContactMenu() {
    const overlay = document.getElementById('menuOverlay');
    const menu = document.getElementById('contactMenu');
    
    if (overlay && menu) {
        overlay.classList.remove('active');
        menu.classList.remove('active');
        setTimeout(() => {
            overlay.style.display = 'none';
            menu.style.display = 'none';
        }, 300);
    }
}

// Обработчики событий
function initializeEventListeners() {
    const checkButton = document.getElementById('checkButton');
    if (checkButton) {
        checkButton.addEventListener('click', checkCookies);
    }
    
    const closeModalBtn = document.querySelector('.close-btn');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }
    
    const modal = document.getElementById('resultsModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
    }
}

// Загрузка статистики
async function loadGlobalStats() {
    try {
        const response = await fetch('/api/global_stats');
        if (response.ok) {
            const stats = await response.json();
            updateGlobalStats(stats);
        }
    } catch (error) {
        console.error('Error loading global stats:', error);
    }
}

function updateGlobalStats(stats) {
    const elements = {
        'totalChecked': stats.total_checked || 0,
        'validAccounts': stats.valid_accounts || 0,
        'activeUsers': stats.active_users || 0
    };
    
    Object.keys(elements).forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = formatNumber(elements[id]);
        }
    });
}

// Проверка куки
async function checkCookies() {
    if (isChecking) {
        showNotification('Проверка уже выполняется', 'warning');
        return;
    }
    
    const input = document.getElementById('cookiesInput');
    if (!input) return;
    
    const cookiesText = input.value.trim();
    if (!cookiesText) {
        showNotification('Введите куки для проверки', 'error');
        return;
    }
    
    // Просто разбиваем на строки - бекенд сам разберется
    const cookies = cookiesText.split('\n')
        .map(c => c.trim())
        .filter(c => c.length > 0);
    
    if (cookies.length === 0) {
        showNotification('Не найдено куки для проверки', 'error');
        return;
    }
    
    if (cookies.length > 3000) {
        showNotification('Максимум 3000 куки за раз', 'error');
        return;
    }
    
    isChecking = true;
    const button = document.getElementById('checkButton');
    const originalText = button.innerHTML;
    
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ПРОВЕРКА...';
    button.disabled = true;
    
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
            currentSessionId = data.session_id;
            currentResults = data.results;
            displayResults(data);
            showNotification(`Проверка завершена! Валидных: ${data.valid} из ${data.total}`, 'success');
            loadGlobalStats();
        } else {
            throw new Error(data.error || 'Ошибка сервера');
        }
        
    } catch (error) {
        showNotification('Ошибка проверки: ' + error.message, 'error');
    } finally {
        isChecking = false;
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

// Отображение результатов
function displayResults(data) {
    const container = document.getElementById('resultsContainer');
    if (!container) return;
    
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
                    <i class="fas fa-download"></i> СКАЧАТЬ АРХИВ (${validResults.length})
                </button>
                <button class="cyber-button" onclick="viewCurrentResults()">
                    <i class="fas fa-eye"></i> ПРОСМОТР РЕЗУЛЬТАТОВ
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
            <div class="cyber-card fade-in-up">
                <div class="card-header" onclick="toggleInvalidResults()" style="cursor: pointer;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h2>НЕВАЛИДНЫЕ КУКИ (${invalidResults.length})</h2>
                    <i class="fas fa-chevron-down" id="invalidToggle"></i>
                </div>
                <div class="invalid-list" id="invalidResults" style="display: none;">
                    ${invalidResults.map(result => `
                        <div class="invalid-item" style="padding: 0.5rem; border-bottom: 1px solid var(--card-border);">
                            <code style="color: var(--text-secondary); font-size: 0.8rem;">${result.cookie.substring(0, 80)}...</code>
                            <span style="color: var(--error); font-size: 0.8rem;">${result.error}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    setTimeout(() => {
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

function createAccountCard(result, index) {
    const acc = result.account_info || {};
    
    // Безопасные функции
    const safeGet = (obj, key, defaultValue = 'N/A') => {
        return obj && obj[key] !== undefined && obj[key] !== null ? obj[key] : defaultValue;
    };
    
    const safeNumber = (num, defaultValue = 0) => {
        const value = safeGet({num}, 'num', defaultValue);
        return typeof value === 'number' ? value : defaultValue;
    };
    
    const safeString = (str, defaultValue = 'N/A') => {
        const value = safeGet({str}, 'str', defaultValue);
        return String(value);
    };
    
    const safeBoolean = (bool, defaultValue = false) => {
        const value = safeGet({bool}, 'bool', defaultValue);
        return Boolean(value);
    };
    
    // Извлекаем данные с защитой от ошибок
    const username = safeString(acc.username, 'N/A');
    const user_id = safeString(acc.user_id, 'N/A');
    const display_name = safeString(acc.display_name, username);
    const formatted_date = safeString(acc.formatted_date, 'Unknown');
    const account_age_days = safeNumber(acc.account_age_days, 0);
    const account_age_years = safeNumber(acc.account_age_years, 0);
    const robux_balance = safeNumber(acc.robux_balance, 0);
    const pending_robux = safeNumber(acc.pending_robux, 0);
    const total_spent_robux = safeNumber(acc.total_spent_robux, 0); // Всего потрачено
    const rap_value = safeNumber(acc.rap_value, 0);
    const premium = safeBoolean(acc.premium, false);
    const two_fa_enabled = safeBoolean(acc['2fa_enabled'], false);
    const friends_count = safeNumber(acc.friends_count, 0);
    const followers_count = safeNumber(acc.followers_count, 0);
    const following_count = safeNumber(acc.following_count, 0);
    const account_value = safeNumber(acc.account_value, 0);
    const description = safeString(acc.description, '');
    const profile_url = safeString(acc.profile_url, `https://www.roblox.com/users/${user_id}/profile`);
    
    // Дополнительные поля
    const billing_robux = safeNumber(acc.billing_robux, 0);
    const card_count = safeNumber(acc.card_count, 0);
    const inventory_privacy = safeString(acc.inventory_privacy, 'Unknown');
    const trade_privacy = safeString(acc.trade_privacy, 'Unknown');
    const can_trade = safeBoolean(acc.can_trade, false);
    const sessions_count = safeNumber(acc.sessions_count, 0);
    const email_status = safeString(acc.email_status, 'Unknown');
    const phone_status = safeString(acc.phone_status, 'No');
    const pin_enabled = safeBoolean(acc.pin_enabled, false);
    const groups_owned = safeNumber(acc.groups_owned, 0);
    const groups_pending = safeNumber(acc.groups_pending, 0);
    const groups_funds = safeNumber(acc.groups_funds, 0);
    const above_13 = safeString(acc.above_13, 'Unknown');
    const verified_age = safeString(acc.verified_age, 'No');
    const voice_enabled = safeString(acc.voice_enabled, 'No');
    const roblox_badges_count = safeNumber(acc.roblox_badges_count, 0);
    
    return `
        <div class="cyber-card account-card fade-in-up">
            <div class="account-header">
                <div class="account-index">#${index}</div>
                <div class="account-main">
                    <h3 class="username">${escapeHtml(username)}</h3>
                    <div class="account-details">
                        <span>ID: ${user_id}</span>
                        <a href="${profile_url}" target="_blank" class="profile-link">
                            <i class="fas fa-external-link-alt"></i> Профиль
                        </a>
                    </div>
                </div>
                <div class="account-value">$${account_value.toLocaleString()}</div>
            </div>
            
            <div class="account-grid">
                <div class="info-group">
                    <h4><i class="fas fa-id-card"></i> ОСНОВНАЯ ИНФОРМАЦИЯ</h4>
                    <div class="info-row">
                        <span>Display Name:</span>
                        <span>${escapeHtml(display_name)}</span>
                    </div>
                    <div class="info-row">
                        <span>Дата создания:</span>
                        <span>${formatted_date}</span>
                    </div>
                    <div class="info-row">
                        <span>Возраст аккаунта:</span>
                        <span>${account_age_days.toLocaleString()} дней (${account_age_years.toFixed(1)} лет)</span>
                    </div>
                    <div class="info-row">
                        <span>Наличие карты:</span>
                        <span class="status ${card_count > 0 ? 'success' : 'error'}">
                            ${card_count > 0 ? 'ДА' : 'НЕТ'} (${card_count})
                        </span>
                    </div>
                </div>
                
                <div class="info-group">
                    <h4><i class="fas fa-coins"></i> ЭКОНОМИКА</h4>
                    <div class="info-row">
                        <span>Баланс Robux:</span>
                        <span class="robux">${robux_balance.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Pending Robux:</span>
                        <span>${pending_robux.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Всего потрачено:</span>
                        <span class="total-spent">${total_spent_robux.toLocaleString()} R$</span>
                    </div>
                    <div class="info-row">
                        <span>RAP стоимость:</span>
                        <span>${rap_value.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Billing Robux:</span>
                        <span>${billing_robux.toLocaleString()}</span>
                    </div>
                </div>
                
                <div class="info-group">
                    <h4><i class="fas fa-chart-bar"></i> СТАТИСТИКА</h4>
                    <div class="info-row">
                        <span>Premium:</span>
                        <span class="status ${premium ? 'success' : 'error'}">
                            ${premium ? 'АКТИВНО' : 'НЕАКТИВНО'}
                        </span>
                    </div>
                    <div class="info-row">
                        <span>2FA:</span>
                        <span class="status ${two_fa_enabled ? 'success' : 'error'}">
                            ${two_fa_enabled ? 'ВКЛ' : 'ВЫКЛ'}
                        </span>
                    </div>
                    <div class="info-row">
                        <span>Друзья:</span>
                        <span>${friends_count.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Подписчики:</span>
                        <span>${followers_count.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Подписки:</span>
                        <span>${following_count.toLocaleString()}</span>
                    </div>
                </div>
            </div>
            
            <div class="account-grid">
                <div class="info-group">
                    <h4><i class="fas fa-shield-alt"></i> БЕЗОПАСНОСТЬ</h4>
                    <div class="info-row">
                        <span>Приватность инвентаря:</span>
                        <span>${inventory_privacy}</span>
                    </div>
                    <div class="info-row">
                        <span>Приватность трейдов:</span>
                        <span>${trade_privacy}</span>
                    </div>
                    <div class="info-row">
                        <span>Может трейдить:</span>
                        <span class="status ${can_trade ? 'success' : 'error'}">
                            ${can_trade ? 'ДА' : 'НЕТ'}
                        </span>
                    </div>
                    <div class="info-row">
                        <span>Активные сессии:</span>
                        <span>${sessions_count}</span>
                    </div>
                </div>
                
                <div class="info-group">
                    <h4><i class="fas fa-envelope"></i> КОНТАКТЫ</h4>
                    <div class="info-row">
                        <span>Email:</span>
                        <span>${email_status}</span>
                    </div>
                    <div class="info-row">
                        <span>Телефон:</span>
                        <span class="status ${phone_status === 'Yes' ? 'success' : 'error'}">
                            ${phone_status === 'Yes' ? 'ПРИВЯЗАН' : 'НЕТ'}
                        </span>
                    </div>
                    <div class="info-row">
                        <span>PIN код:</span>
                        <span class="status ${pin_enabled ? 'success' : 'error'}">
                            ${pin_enabled ? 'ВКЛ' : 'ВЫКЛ'}
                        </span>
                    </div>
                    <div class="info-row">
                        <span>Возраст >13:</span>
                        <span>${above_13}</span>
                    </div>
                    <div class="info-row">
                        <span>Подтвержденный возраст:</span>
                        <span>${verified_age}</span>
                    </div>
                </div>
                
                <div class="info-group">
                    <h4><i class="fas fa-users"></i> ГРУППЫ И БЕЙДЖИ</h4>
                    <div class="info-row">
                        <span>Владелец групп:</span>
                        <span>${groups_owned}</span>
                    </div>
                    <div class="info-row">
                        <span>Pending в группах:</span>
                        <span>${groups_pending}</span>
                    </div>
                    <div class="info-row">
                        <span>Фонды групп:</span>
                        <span>${groups_funds.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span>Голосовой чат:</span>
                        <span>${voice_enabled}</span>
                    </div>
                    <div class="info-row">
                        <span>Бейджи Roblox:</span>
                        <span>${roblox_badges_count}</span>
                    </div>
                </div>
            </div>
            
            ${description ? `
            <div class="info-group" style="margin-top: 1rem;">
                <h4><i class="fas fa-file-alt"></i> ОПИСАНИЕ</h4>
                <div style="color: var(--text-secondary); font-size: 0.9rem; line-height: 1.4;">
                    ${escapeHtml(description.substring(0, 200))}${description.length > 200 ? '...' : ''}
                </div>
            </div>
            ` : ''}
        </div>
    `;
}

// Загрузка истории
async function loadHistory() {
    const historyContent = document.getElementById('historyContent');
    if (!historyContent) return;
    
    historyContent.innerHTML = '<div style="text-align: center; padding: 2rem;"><div class="loading"></div><p>Загрузка истории...</p></div>';
    
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        
        if (!response.ok) {
            throw new Error(history.error || 'Ошибка загрузки');
        }
        
        if (history.length === 0) {
            historyContent.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox" style="font-size: 3rem; color: var(--neon-purple); margin-bottom: 1rem;"></i>
                    <h3>ИСТОРИЯ ПУСТА</h3>
                    <p>Здесь будут отображаться ваши предыдущие проверки</p>
                </div>
            `;
            return;
        }
        
        let html = '<div class="history-list">';
        
        history.forEach(check => {
            const date = new Date(check.check_date);
            const formattedDate = date.toLocaleString('ru-RU');
            
            html += `
                <div class="history-item">
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
                        <button class="cyber-button small" onclick="viewSessionResults('${check.session_id}')">
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
            </div>
        `;
    }
}

// Просмотр результатов сессии
async function viewSessionResults(sessionId) {
    try {
        const response = await fetch(`/api/session/${sessionId}`);
        const data = await response.json();
        
        if (response.ok) {
            currentSessionId = sessionId;
            currentResults = data.results;
            switchPage('home');
            setTimeout(() => {
                displayResults(data);
            }, 100);
        } else {
            throw new Error(data.error || 'Ошибка загрузки');
        }
    } catch (error) {
        showNotification('Ошибка загрузки сессии: ' + error.message, 'error');
    }
}

// Скачивание результатов
function downloadResults() {
    if (!currentSessionId) {
        showNotification('Нет результатов для скачивания', 'error');
        return;
    }
    window.open(`/api/download/${currentSessionId}`, '_blank');
}

function downloadSession(sessionId) {
    window.open(`/api/download/${sessionId}`, '_blank');
}

// Удаление сессии
async function deleteSession(sessionId) {
    if (!confirm('Удалить эту запись из истории?')) return;
    
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

// Просмотр текущих результатов в модальном окне - исправленная версия
function viewCurrentResults() {
    if (!currentResults.length) return;
    
    const modal = document.getElementById('resultsModal');
    const modalBody = document.getElementById('modalResults');
    
    if (!modal || !modalBody) return;
    
    const validResults = currentResults.filter(r => r.valid);
    
    let html = `
        <div class="results-summary">
            <div class="stats-grid">
                <div class="cyber-stat">
                    <div class="stat-value">${currentResults.length}</div>
                    <div class="stat-label">ВСЕГО</div>
                </div>
                <div class="cyber-stat valid">
                    <div class="stat-value">${validResults.length}</div>
                    <div class="stat-label">ВАЛИДНЫХ</div>
                </div>
                <div class="cyber-stat invalid">
                    <div class="stat-value">${currentResults.length - validResults.length}</div>
                    <div class="stat-label">НЕВАЛИДНЫХ</div>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 1.5rem;">
            <h4 style="color: var(--neon-cyan); margin-bottom: 1rem;">Валидные аккаунты:</h4>
            <div style="max-height: 300px; overflow-y: auto;">
    `;
    
    validResults.forEach(result => {
        const acc = result.account_info || {};
        const username = acc.username || 'N/A';
        const user_id = acc.user_id || 'N/A';
        const total_robux = acc.total_robux || 0;
        const friends_count = acc.friends_count || 0;
        const premium = acc.premium || false;
        const two_fa_enabled = acc['2fa_enabled'] || false;
        
        html += `
            <div style="padding: 0.8rem; border-bottom: 1px solid var(--card-border);">
                <strong>${escapeHtml(username)}</strong>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                    ID: ${user_id} | 
                    Robux: ${total_robux.toLocaleString()} | 
                    Друзья: ${friends_count.toLocaleString()} |
                    Premium: ${premium ? 'Да' : 'Нет'} |
                    2FA: ${two_fa_enabled ? 'Вкл' : 'Выкл'}
                </div>
            </div>
        `;
    });
    
    html += `</div></div>`;
    
    modalBody.innerHTML = html;
    
    // Плавное открытие модалки
    modal.style.display = 'block';
    setTimeout(() => {
        modal.style.opacity = '1';
    }, 10);
}

// Закрытие модального окна - исправленная версия
function closeModal() {
    const modal = document.getElementById('resultsModal');
    if (modal) {
        modal.style.opacity = '0';
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
}

// Переключение отображения невалидных результатов
function toggleInvalidResults() {
    const content = document.getElementById('invalidResults');
    const toggle = document.getElementById('invalidToggle');
    
    if (content && toggle) {
        if (content.style.display === 'none') {
            content.style.display = 'block';
            toggle.className = 'fas fa-chevron-up';
        } else {
            content.style.display = 'none';
            toggle.className = 'fas fa-chevron-down';
        }
    }
}

// Утилиты
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

function showNotification(message, type = 'info') {
    const container = document.getElementById('notificationContainer');
    if (!container) return;
    
    const notification = document.createElement('div');
    notification.className = `cyber-notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-triangle' : 'info'}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(notification);
    
    setTimeout(() => notification.classList.add('show'), 100);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

// Глобальные функции
window.checkCookies = checkCookies;
window.downloadResults = downloadResults;
window.downloadSession = downloadSession;
window.deleteSession = deleteSession;
window.viewSessionResults = viewSessionResults;
window.viewCurrentResults = viewCurrentResults;
window.toggleInvalidResults = toggleInvalidResults;
window.closeModal = closeModal;
window.loadHistory = loadHistory;
window.switchPage = switchPage;