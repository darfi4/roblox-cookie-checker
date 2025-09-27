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
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['DATABASE'] = 'checker_history.db'

# Глобальные переменные для активных пользователей
active_users = {}
active_users_lock = threading.Lock()

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
            CREATE TABLE IF NOT EXISTS global_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_checked INTEGER DEFAULT 0,
                valid_accounts INTEGER DEFAULT 0,
                last_updated TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

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
                INSERT INTO global_stats (total_checked, valid_accounts, last_updated)
                VALUES (?, ?, ?)
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
                'last_updated': result[3]
            }
        return {'total_checked': 0, 'valid_accounts': 0, 'last_updated': datetime.now().isoformat()}
    except Exception as e:
        return {'total_checked': 0, 'valid_accounts': 0, 'last_updated': datetime.now().isoformat()}

def get_active_users_count():
    """Получение количества активных пользователей"""
    with active_users_lock:
        # Удаляем неактивных пользователей (более 5 минут)
        current_time = time.time()
        inactive_users = [user_id for user_id, last_active in active_users.items() 
                         if current_time - last_active > 300]  # 5 минут
        for user_id in inactive_users:
            del active_users[user_id]
        
        return len(active_users)

def update_user_activity(user_id):
    """Обновление активности пользователя"""
    with active_users_lock:
        active_users[user_id] = time.time()

def get_user_id():
    """Генерируем уникальный ID пользователя"""
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        unique_string = f"{ip}-{user_agent}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    except:
        return str(uuid.uuid4())

def save_check_session(session_id, user_id, total, valid, results):
    """Сохраняем проверку"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('''
            INSERT INTO check_history 
            (session_id, user_id, total_cookies, valid_cookies, check_date, results)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, user_id, total, valid, datetime.now().isoformat(), json.dumps(results)))
        conn.commit()
        conn.close()
        
        update_global_stats(total, valid)
        return True
    except Exception as e:
        print(f"Error saving session: {e}")
        return False

def get_user_history(user_id, limit=20):
    """Получаем историю пользователя"""
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
        return []

def get_session_results(session_id, user_id):
    """Получаем результаты сессии"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT results FROM check_history WHERE session_id = ? AND user_id = ?', (session_id, user_id))
        result = c.fetchone()
        conn.close()
        return json.loads(result[0]) if result else None
    except:
        return None

class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.timeout = 30

    def clean_cookie(self, cookie):
        """Очистка и валидация куки"""
        if not cookie or len(cookie) < 100:
            return None
            
        cookie = cookie.strip()
        
        # Убираем кавычки если есть
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        
        # Проверяем базовый формат
        if not cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.'):
            return None
            
        # Убираем лишние пробелы и переносы
        cookie = re.sub(r'\s+', '', cookie)
        
        return cookie if len(cookie) > 100 else None

    def get_csrf_token(self, cookie):
        """Получение CSRF токена"""
        try:
            response = self.session.post(
                'https://auth.roblox.com/v2/login',
                cookies={'.ROBLOSECURITY': cookie},
                timeout=10
            )
            if response.status_code == 403 and 'x-csrf-token' in response.headers:
                return response.headers['x-csrf-token']
        except:
            pass
        return None

    def make_request(self, url, cookie, csrf_token=None, method='GET'):
        """Универсальный метод для запросов"""
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        if csrf_token:
            headers['X-CSRF-TOKEN'] = csrf_token
            
        try:
            if method == 'GET':
                response = self.session.get(url, headers=headers, timeout=10)
            else:
                response = self.session.post(url, headers=headers, timeout=10)
                
            if response.status_code == 429:  # Rate limit
                time.sleep(2)
                return self.make_request(url, cookie, csrf_token, method)
                
            return response
        except:
            return None

    def check_single_cookie(self, cookie):
        """Проверка одной куки с полной информацией"""
        clean_cookie = self.clean_cookie(cookie)
        if not clean_cookie:
            return self.error_result(cookie, 'Invalid cookie format')
        
        try:
            # Получаем CSRF токен
            csrf_token = self.get_csrf_token(clean_cookie)
            
            # Проверяем аутентификацию
            auth_response = self.make_request(
                'https://users.roblox.com/v1/users/authenticated',
                clean_cookie,
                csrf_token
            )
            
            if not auth_response or auth_response.status_code != 200:
                return self.error_result(clean_cookie, 'Authentication failed')
                
            auth_data = auth_response.json()
            if not auth_data.get('id'):
                return self.error_result(clean_cookie, 'Invalid user data')
                
            user_id = auth_data['id']
            
            # Получаем полную информацию об аккаунте
            account_info = self.get_account_info(clean_cookie, csrf_token, user_id)
            if not account_info:
                return self.error_result(clean_cookie, 'Failed to get account info')
                
            return {
                'valid': True,
                'cookie': clean_cookie,
                'account_info': account_info,
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return self.error_result(clean_cookie, f'Check error: {str(e)}')

    def get_account_info(self, cookie, csrf_token, user_id):
        """Получение полной информации об аккаунте"""
        try:
            # Базовая информация
            profile_response = self.make_request(
                f'https://users.roblox.com/v1/users/{user_id}',
                cookie,
                csrf_token
            )
            
            if not profile_response or profile_response.status_code != 200:
                return None
                
            profile_data = profile_response.json()
            
            # Экономика
            economy_data = self.get_economy_info(cookie, csrf_token)
            
            # Premium статус
            premium_data = self.get_premium_status(cookie, csrf_token, user_id)
            
            # Друзья
            friends_data = self.get_friends_count(cookie, csrf_token, user_id)
            
            # 2FA статус
            tfa_enabled = self.check_2fa_status(cookie, csrf_token)
            
            # RAP и другие метрики
            rap_data = self.get_rap_info(cookie, csrf_token, user_id)
            
            # Собираем всю информацию
            created_date = profile_data.get('created', '')
            account_age = self.calculate_account_age(created_date)
            
            return {
                'username': profile_data.get('name', 'N/A'),
                'display_name': profile_data.get('displayName', profile_data.get('name', 'N/A')),
                'user_id': user_id,
                'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                'created_date': account_age['formatted_date'],
                'account_age_days': account_age['days'],
                'account_age_years': account_age['years'],
                'description': profile_data.get('description', ''),
                'is_banned': profile_data.get('isBanned', False),
                'robux_balance': economy_data.get('robux', 0),
                'pending_robux': economy_data.get('pending_robux', 0),
                'total_robux': economy_data.get('robux', 0) + economy_data.get('pending_robux', 0),
                'premium': premium_data.get('isPremium', False),
                'premium_status': premium_data.get('status', 'Inactive'),
                'friends_count': friends_data.get('count', 0),
                'followers_count': profile_data.get('followersCount', 0),
                'following_count': profile_data.get('followingsCount', 0),
                '2fa_enabled': tfa_enabled,
                'rap_value': rap_data.get('rap', 0),
                'account_value': self.calculate_account_value(
                    economy_data.get('robux', 0),
                    premium_data.get('isPremium', False),
                    account_age['years'],
                    friends_data.get('count', 0),
                    rap_data.get('rap', 0)
                )
            }
            
        except Exception as e:
            print(f"Account info error: {e}")
            return None

    def get_economy_info(self, cookie, csrf_token):
        """Информация об экономике"""
        try:
            response = self.make_request(
                'https://economy.roblox.com/v1/users/currency',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                return response.json()
        except:
            pass
        return {'robux': 0, 'pendingRobux': 0}

    def get_premium_status(self, cookie, csrf_token, user_id):
        """Статус Premium"""
        try:
            response = self.make_request(
                f'https://premiumfeatures.roblox.com/v1/users/{user_id}/premium',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                data = response.json()
                return {
                    'isPremium': data.get('isPremium', False),
                    'status': 'Active' if data.get('isPremium') else 'Inactive'
                }
        except:
            pass
        return {'isPremium': False, 'status': 'Inactive'}

    def get_friends_count(self, cookie, csrf_token, user_id):
        """Количество друзей"""
        try:
            response = self.make_request(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                return response.json()
        except:
            pass
        return {'count': 0}

    def check_2fa_status(self, cookie, csrf_token):
        """Проверка 2FA"""
        try:
            response = self.make_request(
                'https://accountsettings.roblox.com/v1/email',
                cookie,
                csrf_token
            )
            return response is not None and response.status_code == 200
        except:
            return False

    def get_rap_info(self, cookie, csrf_token, user_id):
        """Получение RAP (Recent Average Price) информации"""
        try:
            # Используем API для получения информации об активе
            response = self.make_request(
                f'https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?assetType=All&limit=10',
                cookie,
                csrf_token
            )
            
            if response and response.status_code == 200:
                data = response.json()
                # Простая оценка RAP (можно улучшить)
                rap_value = len(data.get('data', [])) * 100  # Базовая оценка
                return {'rap': rap_value}
        except:
            pass
        return {'rap': 0}

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
        except:
            return {'days': 0, 'years': 0, 'formatted_date': 'Unknown'}

    def calculate_account_value(self, robux, is_premium, age_years, friends_count, rap_value):
        """Расчет стоимости аккаунта"""
        try:
            value = robux * 0.0035  # Базовая стоимость Robux
            value += rap_value * 0.001  # Стоимость RAP
            value += age_years * 300  # За возраст
            value += friends_count * 2  # За друзей
            
            if is_premium:
                value += 500  # Премиум бонус
                
            return round(max(value, 10), 2)
        except:
            return 10.0

    def error_result(self, cookie, error):
        return {
            'valid': False,
            'cookie': cookie,
            'error': error,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple_cookies(self, cookies):
        """Проверка нескольких куки"""
        valid_cookies = []
        
        # Фильтрация куки
        for cookie in cookies:
            clean_cookie = self.clean_cookie(cookie)
            if clean_cookie:
                valid_cookies.append(clean_cookie)
        
        if not valid_cookies:
            return [self.error_result("", "No valid cookies found")]
        
        results = []
        max_workers = min(3, len(valid_cookies))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_cookie = {
                executor.submit(self.check_single_cookie, cookie): cookie 
                for cookie in valid_cookies
            }
            
            for future in as_completed(future_to_cookie):
                try:
                    result = future.result(timeout=45)
                    results.append(result)
                    time.sleep(1)  # Задержка между запросами
                except Exception as e:
                    cookie = future_to_cookie[future]
                    results.append(self.error_result(cookie, f"Check timeout: {str(e)}"))
        
        return results

checker = AdvancedRobloxChecker()

@app.route('/')
def index():
    user_id = get_user_id()
    update_user_activity(user_id)
    return render_template('index.html')

@app.route('/api/global_stats')
def api_global_stats():
    """API для получения глобальной статистики"""
    try:
        stats = get_global_stats()
        stats['active_users'] = get_active_users_count()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Stats error: {str(e)}'}), 500

@app.route('/api/history')
def api_history():
    """API для получения истории"""
    try:
        user_id = get_user_id()
        update_user_activity(user_id)
        history = get_user_history(user_id, 20)
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/check', methods=['POST'])
def api_check_cookies():
    """API для проверки куки"""
    try:
        user_id = get_user_id()
        update_user_activity(user_id)
        
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
        
        cookies = data['cookies']
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies = [c.strip() for c in cookies if c.strip()]
        
        if not cookies:
            return jsonify({'error': 'No valid cookies provided'}), 400
        
        if len(cookies) > 3000:
            return jsonify({'error': 'Too many cookies. Maximum 3000 per request.'}), 400
        
        results = checker.check_multiple_cookies(cookies)
        
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S_') + ''.join(random.choices('0123456789abcdef', k=8))
        valid_count = len([r for r in results if r.get('valid', False)])
        
        save_check_session(session_id, user_id, len(cookies), valid_count, results)
        
        return jsonify({
            'total': len(results),
            'valid': valid_count,
            'invalid': len(results) - valid_count,
            'results': results,
            'session_id': session_id,
            'checked_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/download/<session_id>')
def api_download_results(session_id):
    """API для скачивания результатов"""
    try:
        user_id = get_user_id()
        update_user_activity(user_id)
        
        results = get_session_results(session_id, user_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        valid_cookies = [r for r in results if r.get('valid')]
        if not valid_cookies:
            return jsonify({'error': 'No valid cookies'}), 400
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Файл с куки
            cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('valid_cookies.txt', cookies_content)
            
            # Детальный отчет
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
                acc = result['account_info']
                detailed_report['valid_accounts'].append({
                    'username': acc['username'],
                    'user_id': acc['user_id'],
                    'robux': acc['total_robux'],
                    'premium': acc['premium'],
                    'account_age': acc['account_age_days'],
                    'friends': acc['friends_count'],
                    'rap_value': acc['rap_value'],
                    'account_value': acc['account_value'],
                    'created_date': acc['created_date']
                })
            
            zip_file.writestr('detailed_report.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
        
        zip_buffer.seek(0)
        filename = f'roblox_cookies_{session_id}.zip'
        
        return send_file(zip_buffer, as_attachment=True, download_name=filename, mimetype='application/zip')
        
    except Exception as e:
        return jsonify({'error': f'Archive error: {str(e)}'}), 500

@app.route('/api/session/<session_id>')
def api_get_session(session_id):
    """API для получения результатов сессии"""
    try:
        user_id = get_user_id()
        update_user_activity(user_id)
        
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
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/delete/<session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    """API для удаления сессии"""
    try:
        user_id = get_user_id()
        update_user_activity(user_id)
        
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('DELETE FROM check_history WHERE session_id = ? AND user_id = ?', (session_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Delete failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)