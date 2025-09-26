// Основные переменные
let currentSessionId = null;
let currentResults = [];
let isChecking = false;

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    initializeParticles();
    initializeEventListeners();
    loadGlobalStats();
    switchPage('home');
    
    // Загружаем историю если на странице истории
    if (document.getElementById('historySection').classList.contains('active')) {
        loadUserHistory();
    }
});

// Инициализация частиц
function initializeParticles() {
    const canvas = document.getElementById('particlesCanvas');
    const ctx = canvas.getContext('2d');
    
    // Устанавливаем размер canvas
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    
    // Создаем частицы
    const particles = [];
    const particleCount = 150; // Увеличили количество частиц
    
    for (let i = 0; i < particleCount; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 2 + 1,
            speedX: (Math.random() - 0.5) * 2,
            speedY: (Math.random() - 0.5) * 2,
            color: `rgba(${Math.random() * 100 + 155}, ${Math.random() * 100 + 155}, 255, ${Math.random() * 0.5 + 0.2})`
        });
    }
    
    // Обработчик движения мыши
    const mouse = { x: null, y: null, radius: 100 };
    
    canvas.addEventListener('mousemove', function(event) {
        mouse.x = event.x;
        mouse.y = event.y;
    });
    
    canvas.addEventListener('mouseout', function() {
        mouse.x = null;
        mouse.y = null;
    });
    
    // Анимация частиц
    function animateParticles() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            
            // Обновление позиции
            p.x += p.speedX;
            p.y += p.speedY;
            
            // Отскок от границ
            if (p.x < 0 || p.x > canvas.width) p.speedX *= -1;
            if (p.y < 0 || p.y > canvas.height) p.speedY *= -1;
            
            // Взаимодействие с курсором
            if (mouse.x !== null && mouse.y !== null) {
                const dx = mouse.x - p.x;
                const dy = mouse.y - p.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < mouse.radius) {
                    const force = (mouse.radius - distance) / mouse.radius;
                    const angle = Math.atan2(dy, dx);
                    p.x -= Math.cos(angle) * force * 5;
                    p.y -= Math.sin(angle) * force * 5;
                }
            }
            
            // Отрисовка частицы
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.fill();
            
            // Соединение частиц
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < 100) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(100, 100, 255, ${0.2 * (1 - distance/100)})`;
                    ctx.lineWidth = 0.5;
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
            }
        }
        
        requestAnimationFrame(animateParticles);
    }
    
    animateParticles();
}

// Инициализация обработчиков событий
function initializeEventListeners() {
    // Навигация
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const page = this.getAttribute('data-page');
            switchPage(page);
        });
    });
    
    // Вкладки ввода
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tab = this.getAttribute('data-tab');
            switchInputTab(tab);
        });
    });
    
    // Кнопка начала проверки
    document.getElementById('startCheck').addEventListener('click', startCheck);
    
    // Кнопка очистки
    document.getElementById('clearInput').addEventListener('click', clearInput);
    
    // Загрузка файла
    const fileInput = document.getElementById('fileInput');
    const fileUploadArea = document.getElementById('fileUploadArea');
    
    fileUploadArea.addEventListener('click', () => fileInput.click());
    fileUploadArea.addEventListener('dragover', handleDragOver);
    fileUploadArea.addEventListener('drop', handleFileDrop);
    fileInput.addEventListener('change', handleFileSelect);
    
    // Кнопки результатов
    document.getElementById('downloadResults').addEventListener('click', downloadResults);
    document.getElementById('copyValid').addEventListener('click', copyValidCookies);
    
    // Модальное окно
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('modalOverlay').addEventListener('click', function(e) {
        if (e.target === this) closeModal();
    });
    
    // Меню контактов
    document.getElementById('contactButton').addEventListener('click', openContactMenu);
    document.getElementById('closeContact').addEventListener('click', closeContactMenu);
    document.getElementById('menuOverlay').addEventListener('click', closeContactMenu);
    
    // Закрытие по ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeModal();
            closeContactMenu();
        }
    });
}

// Переключение страниц
function switchPage(page) {
    // Скрываем все страницы
    document.querySelectorAll('.page-section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Убираем активный класс со всех вкладок
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Показываем выбранную страницу
    document.getElementById(page + 'Section').classList.add('active');
    
    // Активируем соответствующую вкладку
    document.querySelector(`.main-tab[data-page="${page}"]`).classList.add('active');
    
    // Загружаем историю если переключились на страницу истории
    if (page === 'history') {
        loadUserHistory();
    }
}

// Переключение вкладок ввода
function switchInputTab(tab) {
    // Убираем активный класс со всех кнопок и контента
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Активируем выбранную вкладку
    document.querySelector(`.tab-btn[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(tab + '-tab').classList.add('active');
}

// Загрузка глобальной статистики
async function loadGlobalStats() {
    try {
        const response = await fetch('/api/global_stats');
        const stats = await response.json();
        
        document.getElementById('totalChecked').textContent = 
            formatNumber(stats.total_checked || 0);
        document.getElementById('validAccounts').textContent = 
            formatNumber(stats.valid_accounts || 0);
        document.getElementById('activeUsers').textContent = 
            formatNumber(stats.unique_users || 0);
    } catch (error) {
        console.error('Error loading global stats:', error);
    }
}

// Начало проверки
async function startCheck() {
    if (isChecking) return;
    
    const activeTab = document.querySelector('.tab-content.active').id;
    let cookies = [];
    
    if (activeTab === 'text-tab') {
        const input = document.getElementById('cookieInput').value.trim();
        if (!input) {
            showNotification('Введите куки для проверки', 'error');
            return;
        }
        cookies = input.split('\n').filter(c => c.trim());
    } else {
        const fileInput = document.getElementById('fileInput');
        if (!fileInput.files.length) {
            showNotification('Выберите файл с куки', 'error');
            return;
        }
        cookies = await readCookiesFromFile(fileInput.files[0]);
    }
    
    if (cookies.length === 0) {
        showNotification('Не найдено валидных куки', 'error');
        return;
    }
    
    if (cookies.length > 3000) {
        showNotification('Максимум 3000 куки за раз', 'error');
        return;
    }
    
    // Начинаем проверку
    isChecking = true;
    document.getElementById('progressContainer').style.display = 'block';
    document.getElementById('resultsContainer').style.display = 'none';
    
    updateProgress(0, cookies.length, 0, 0);
    
    try {
        const response = await fetch('/api/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ cookies: cookies })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка сервера');
        }
        
        currentSessionId = data.session_id;
        currentResults = data.results;
        
        showResults(data);
        loadGlobalStats(); // Обновляем статистику
        
    } catch (error) {
        showNotification('Ошибка проверки: ' + error.message, 'error');
        console.error('Check error:', error);
    } finally {
        isChecking = false;
        document.getElementById('progressContainer').style.display = 'none';
    }
}

// Обновление прогресса
function updateProgress(checked, total, valid, invalid) {
    const percent = total > 0 ? (checked / total) * 100 : 0;
    
    document.getElementById('progressText').textContent = `${checked}/${total}`;
    document.getElementById('progressPercent').textContent = `${Math.round(percent)}%`;
    document.getElementById('progressFill').style.width = `${percent}%`;
    
    document.getElementById('validCount').textContent = valid;
    document.getElementById('invalidCount').textContent = invalid;
    document.getElementById('remainingCount').textContent = total - checked;
}

// Показ результатов
function showResults(data) {
    const results = data.results;
    const validResults = results.filter(r => r.valid);
    const invalidResults = results.filter(r => !r.valid);
    
    // Обновляем сводку
    document.getElementById('summaryTotal').textContent = results.length;
    document.getElementById('summaryValid').textContent = validResults.length;
    document.getElementById('summaryInvalid').textContent = invalidResults.length;
    
    // Заполняем таблицу
    const tableBody = document.getElementById('resultsTable');
    tableBody.innerHTML = '';
    
    results.forEach((result, index) => {
        const row = document.createElement('tr');
        
        if (result.valid) {
            row.innerHTML = `
                <td><span class="status-badge status-valid">VALID</span></td>
                <td>${escapeHtml(result.account_info.username)}</td>
                <td>${result.account_info.user_id}</td>
                <td>${formatNumber(result.economy.total_robux)}</td>
                <td>${result.premium.isPremium ? '✓' : '✗'}</td>
                <td>${formatNumber(result.social.friends_count)}</td>
                <td>$${result.account_value}</td>
                <td>
                    <button class="cyber-button-small view-details" data-index="${index}">
                        <i class="fas fa-eye"></i> ДЕТАЛИ
                    </button>
                </td>
            `;
        } else {
            row.innerHTML = `
                <td><span class="status-badge status-invalid">INVALID</span></td>
                <td colspan="2">${escapeHtml(result.error)}</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
            `;
        }
        
        tableBody.appendChild(row);
    });
    
    // Добавляем обработчики для кнопок деталей
    document.querySelectorAll('.view-details').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            showAccountDetails(results[index]);
        });
    });
    
    // Показываем контейнер результатов
    document.getElementById('resultsContainer').style.display = 'block';
    
    // Прокручиваем к результатам
    document.getElementById('resultsContainer').scrollIntoView({ 
        behavior: 'smooth' 
    });
    
    showNotification(`Проверка завершена! Валидных: ${validResults.length} из ${results.length}`, 'success');
}

// Показ деталей аккаунта
function showAccountDetails(account) {
    if (!account.valid) return;
    
    const modalBody = document.getElementById('modalBody');
    
    modalBody.innerHTML = `
        <div class="account-details">
            <div class="detail-row">
                <span class="detail-label">Имя пользователя:</span>
                <span class="detail-value">${escapeHtml(account.account_info.username)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Отображаемое имя:</span>
                <span class="detail-value">${escapeHtml(account.account_info.display_name)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">ID пользователя:</span>
                <span class="detail-value">${account.account_info.user_id}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Дата создания:</span>
                <span class="detail-value">${account.account_info.created_date}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Возраст аккаунта:</span>
                <span class="detail-value">${account.account_info.account_age_days} дней (${account.account_info.account_age_years} лет)</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Баланс Robux:</span>
                <span class="detail-value">${formatNumber(account.economy.robux_balance)} R$</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Ожидающие Robux:</span>
                <span class="detail-value">${formatNumber(account.economy.pending_robux)} R$</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Всего Robux:</span>
                <span class="detail-value">${formatNumber(account.economy.total_robux)} R$</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Premium статус:</span>
                <span class="detail-value">${account.premium.status}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">2FA включена:</span>
                <span class="detail-value">${account.security['2fa_enabled'] ? 'Да' : 'Нет'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Количество друзей:</span>
                <span class="detail-value">${formatNumber(account.social.friends_count)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Подписчики:</span>
                <span class="detail-value">${formatNumber(account.social.followers_count)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Подписки:</span>
                <span class="detail-value">${formatNumber(account.social.following_count)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Примерная стоимость:</span>
                <span class="detail-value">$${account.account_value}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Ссылка на профиль:</span>
                <span class="detail-value">
                    <a href="${account.account_info.profile_url}" target="_blank" style="color: var(--primary);">Открыть профиль</a>
                </span>
            </div>
        </div>
    `;
    
    document.getElementById('modalOverlay').style.display = 'flex';
}

// Закрытие модального окна
function closeModal() {
    document.getElementById('modalOverlay').style.display = 'none';
}

// Загрузка истории пользователя
async function loadUserHistory() {
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        
        if (!response.ok) {
            throw new Error(history.error || 'Ошибка загрузки истории');
        }
        
        displayHistory(history);
        updateHistoryStats(history);
        
    } catch (error) {
        console.error('Error loading history:', error);
        showNotification('Ошибка загрузки истории', 'error');
    }
}

// Отображение истории
function displayHistory(history) {
    const historyList = document.getElementById('historyList');
    
    if (history.length === 0) {
        historyList.innerHTML = `
            <div class="history-item" style="text-align: center; color: var(--gray);">
                <i class="fas fa-history" style="font-size: 3rem; margin-bottom: 15px;"></i>
                <p>История проверок пуста</p>
            </div>
        `;
        return;
    }
    
    historyList.innerHTML = history.map(item => `
        <div class="history-item" data-session="${item.session_id}">
            <div class="history-item-header">
                <h4>Проверка от ${formatDate(item.check_date)}</h4>
                <span class="history-item-date">ID: ${item.session_id}</span>
            </div>
            <div class="history-item-stats">
                <div class="history-stat">
                    <i class="fas fa-cookie" style="color: var(--primary);"></i>
                    <span>Всего: ${item.total_cookies}</span>
                </div>
                <div class="history-stat">
                    <i class="fas fa-check-circle" style="color: var(--success);"></i>
                    <span>Валидные: ${item.valid_cookies}</span>
                </div>
                <div class="history-stat">
                    <i class="fas fa-times-circle" style="color: var(--error);"></i>
                    <span>Невалидные: ${item.total_cookies - item.valid_cookies}</span>
                </div>
            </div>
            <div class="history-item-actions" style="margin-top: 15px; display: flex; gap: 10px;">
                <button class="cyber-button-small view-session" data-session="${item.session_id}">
                    <i class="fas fa-eye"></i> Просмотреть
                </button>
                <button class="cyber-button-small download-session" data-session="${item.session_id}">
                    <i class="fas fa-download"></i> Скачать
                </button>
                <button class="cyber-button-small delete-session" data-session="${item.session_id}" style="background: rgba(255, 51, 102, 0.1); border-color: var(--error);">
                    <i class="fas fa-trash"></i> Удалить
                </button>
            </div>
        </div>
    `).join('');
    
    // Добавляем обработчики событий
    document.querySelectorAll('.view-session').forEach(btn => {
        btn.addEventListener('click', function() {
            const sessionId = this.getAttribute('data-session');
            viewSessionResults(sessionId);
        });
    });
    
    document.querySelectorAll('.download-session').forEach(btn => {
        btn.addEventListener('click', function() {
            const sessionId = this.getAttribute('data-session');
            downloadSessionResults(sessionId);
        });
    });
    
    document.querySelectorAll('.delete-session').forEach(btn => {
        btn.addEventListener('click', function() {
            const sessionId = this.getAttribute('data-session');
            deleteSession(sessionId);
        });
    });
}

// Обновление статистики истории
function updateHistoryStats(history) {
    const totalChecks = history.length;
    const totalCookies = history.reduce((sum, item) => sum + item.total_cookies, 0);
    const validCookies = history.reduce((sum, item) => sum + item.valid_cookies, 0);
    const successRate = totalCookies > 0 ? (validCookies / totalCookies * 100) : 0;
    
    document.getElementById('historyTotalChecks').textContent = totalChecks;
    document.getElementById('historyTotalCookies').textContent = totalCookies;
    document.getElementById('historySuccessRate').textContent = successRate.toFixed(1) + '%';
}

// Просмотр результатов сессии
async function viewSessionResults(sessionId) {
    try {
        const response = await fetch(`/api/session/${sessionId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка загрузки сессии');
        }
        
        // Переключаемся на главную страницу и показываем результаты
        switchPage('home');
        setTimeout(() => {
            currentSessionId = sessionId;
            currentResults = data.results;
            showResults(data);
        }, 100);
        
    } catch (error) {
        showNotification('Ошибка загрузки сессии: ' + error.message, 'error');
    }
}

// Скачивание результатов сессии
async function downloadSessionResults(sessionId) {
    try {
        const response = await fetch(`/api/download/${sessionId}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка скачивания');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `roblox_cookies_${sessionId}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification('Файл успешно скачан', 'success');
        
    } catch (error) {
        showNotification('Ошибка скачивания: ' + error.message, 'error');
    }
}

// Удаление сессии
async function deleteSession(sessionId) {
    if (!confirm('Вы уверены, что хотите удалить эту проверку?')) return;
    
    try {
        const response = await fetch(`/api/delete/${sessionId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка удаления');
        }
        
        showNotification('Проверка удалена', 'success');
        loadUserHistory(); // Перезагружаем историю
        
    } catch (error) {
        showNotification('Ошибка удаления: ' + error.message, 'error');
    }
}

// Скачивание текущих результатов
async function downloadResults() {
    if (!currentSessionId) {
        showNotification('Нет результатов для скачивания', 'error');
        return;
    }
    
    await downloadSessionResults(currentSessionId);
}

// Копирование валидных куки
function copyValidCookies() {
    const validCookies = currentResults
        .filter(r => r.valid)
        .map(r => r.cookie)
        .join('\n');
    
    if (!validCookies) {
        showNotification('Нет валидных куки для копирования', 'error');
        return;
    }
    
    navigator.clipboard.writeText(validCookies)
        .then(() => showNotification('Валидные куки скопированы в буфер', 'success'))
        .catch(() => showNotification('Ошибка копирования', 'error'));
}

// Очистка ввода
function clearInput() {
    document.getElementById('cookieInput').value = '';
    document.getElementById('fileInput').value = '';
    document.getElementById('resultsContainer').style.display = 'none';
    currentSessionId = null;
    currentResults = [];
}

// Работа с файлами
function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.style.borderColor = 'var(--primary)';
    e.currentTarget.style.background = 'rgba(0, 243, 255, 0.1)';
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
    const cookies = await readCookiesFromFile(file);
    if (cookies.length > 0) {
        document.getElementById('cookieInput').value = cookies.join('\n');
        switchInputTab('text');
        showNotification(`Загружено ${cookies.length} куки из файла`, 'success');
    } else {
        showNotification('Не удалось загрузить куки из файла', 'error');
    }
}

async function readCookiesFromFile(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = function(e) {
            const content = e.target.result;
            const cookies = content.split('\n')
                .map(line => line.trim())
                .filter(line => line && line.startsWith('_|WARNING:-DO-NOT-SHARE-THIS.'));
            resolve(cookies);
        };
        reader.readAsText(file);
    });
}

// Меню контактов
function openContactMenu() {
    document.getElementById('menuOverlay').style.display = 'block';
    document.getElementById('contactMenu').style.display = 'block';
}

function closeContactMenu() {
    document.getElementById('menuOverlay').style.display = 'none';
    document.getElementById('contactMenu').style.display = 'none';
}

// Утилиты
function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('ru-RU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showNotification(message, type = 'info') {
    // Создаем уведомление
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-triangle' : 'info'}"></i>
        <span>${message}</span>
    `;
    
    // Стили уведомления
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'rgba(0, 255, 136, 0.9)' : type === 'error' ? 'rgba(255, 51, 102, 0.9)' : 'rgba(0, 243, 255, 0.9)'};
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 10px;
        max-width: 400px;
        animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Удаляем через 5 секунд
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
    
    // Добавляем CSS анимации если их нет
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
}