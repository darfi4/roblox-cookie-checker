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
from threading import Timer

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['DATABASE'] = 'checker_history.db'

# Активные пользователи (сессии)
active_sessions = {}
session_lock = threading.Lock()
SESSION_TIMEOUT = 300  # 5 минут

# Очистка неактивных сессий
def cleanup_sessions():
    with session_lock:
        current_time = time.time()
        expired_sessions = []
        for session_id, session_data in active_sessions.items():
            if current_time - session_data['last_active'] > SESSION_TIMEOUT:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del active_sessions[session_id]
    
    # Запускаем следующую очистку через минуту
    Timer(60, cleanup_sessions).start()

# Запускаем очистку при старте
cleanup_sessions()

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
    with session_lock:
        current_time = time.time()
        active_count = 0
        for session_id, session_data in active_sessions.items():
            if current_time - session_data['last_active'] <= SESSION_TIMEOUT:
                active_count += 1
        return active_count

def update_user_session(session_id, user_data=None):
    with session_lock:
        active_sessions[session_id] = {
            'last_active': time.time(),
            'user_data': user_data or {},
            'created': active_sessions.get(session_id, {}).get('created', time.time())
        }

def get_user_id():
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        unique_string = f"{ip}-{user_agent}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    except:
        return str(uuid.uuid4())

def save_check_session(session_id, user_id, total, valid, results):
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.timeout = 30

    def clean_cookie(self, cookie):
        """Тщательная очистка куки"""
        if not cookie or len(cookie) < 100:
            return None
            
        cookie = cookie.strip()
        
        # Убираем кавычки
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        
        # Убираем лишние пробелы и переносы
        cookie = re.sub(r'\s+', '', cookie)
        
        # Проверяем базовый формат
        if not cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.'):
            return None
            
        return cookie if len(cookie) > 100 else None

    def get_csrf_token(self, cookie):
        """Получение CSRF токена с улучшенной логикой"""
        try:
            # Первый способ - через auth endpoint
            response = self.session.post(
                'https://auth.roblox.com/v2/login',
                cookies={'.ROBLOSECURITY': cookie},
                timeout=10,
                allow_redirects=False
            )
            
            if response.status_code == 403 and 'x-csrf-token' in response.headers:
                return response.headers['x-csrf-token']
            
            # Второй способ - через другие endpoints
            endpoints = [
                'https://www.roblox.com/game/GetCurrentUser',
                'https://accountsettings.roblox.com/v1/email',
                'https://users.roblox.com/v1/users/authenticated'
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.session.post(
                        endpoint,
                        cookies={'.ROBLOSECURITY': cookie},
                        timeout=5
                    )
                    if 'x-csrf-token' in response.headers:
                        return response.headers['x-csrf-token']
                except:
                    continue
                    
        except Exception as e:
            print(f"CSRF token error: {e}")
            
        return None

    def make_authenticated_request(self, url, cookie, csrf_token=None, method='GET', retry_count=3):
        """Улучшенный запрос с обработкой ошибок"""
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.roblox.com/'
        }
        
        if csrf_token:
            headers['X-CSRF-TOKEN'] = csrf_token
            
        for attempt in range(retry_count):
            try:
                if method.upper() == 'POST':
                    response = self.session.post(url, headers=headers, timeout=15)
                else:
                    response = self.session.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 401:
                    return None  # Неавторизован
                elif response.status_code == 403:
                    # Пробуем обновить CSRF токен
                    new_csrf = self.get_csrf_token(cookie)
                    if new_csrf and attempt < retry_count - 1:
                        headers['X-CSRF-TOKEN'] = new_csrf
                        time.sleep(1)
                        continue
                    return None
                elif response.status_code == 429:
                    # Rate limit - ждем и пробуем снова
                    time.sleep(3)
                    continue
                    
            except requests.exceptions.Timeout:
                if attempt < retry_count - 1:
                    time.sleep(2)
                    continue
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
                    
        return None

    def check_single_cookie(self, cookie):
        """Улучшенная проверка куки"""
        clean_cookie = self.clean_cookie(cookie)
        if not clean_cookie:
            return self.error_result(cookie, 'Invalid cookie format')
        
        try:
            # Получаем CSRF токен
            csrf_token = self.get_csrf_token(clean_cookie)
            
            # Проверяем базовую аутентификацию
            auth_response = self.make_authenticated_request(
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
            
            # Получаем расширенную информацию
            account_info = self.get_detailed_account_info(clean_cookie, csrf_token, user_id, auth_data)
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

    def get_detailed_account_info(self, cookie, csrf_token, user_id, auth_data):
        """Получение детальной информации об аккаунте"""
        try:
            # Базовая информация из auth response
            base_info = {
                'username': auth_data.get('name', 'N/A'),
                'display_name': auth_data.get('displayName', auth_data.get('name', 'N/A')),
                'user_id': user_id,
                'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                'created_date': auth_data.get('created', ''),
                'is_banned': auth_data.get('isBanned', False)
            }
            
            # Детальная информация профиля
            profile_info = self.get_profile_info(cookie, csrf_token, user_id)
            base_info.update(profile_info)
            
            # Экономика
            economy_info = self.get_economy_info(cookie, csrf_token)
            base_info.update(economy_info)
            
            # Premium статус
            premium_info = self.get_premium_status(cookie, csrf_token, user_id)
            base_info.update(premium_info)
            
            # Социальная информация
            social_info = self.get_social_info(cookie, csrf_token, user_id)
            base_info.update(social_info)
            
            # Безопасность
            security_info = self.get_security_info(cookie, csrf_token, user_id)
            base_info.update(security_info)
            
            # RAP и дополнительные метрики
            additional_info = self.get_additional_metrics(cookie, csrf_token, user_id)
            base_info.update(additional_info)
            
            # Расчет возраста аккаунта
            age_info = self.calculate_account_age(base_info['created_date'])
            base_info.update(age_info)
            
            # Расчет стоимости
            base_info['account_value'] = self.calculate_account_value(
                base_info['robux_balance'],
                base_info['premium'],
                base_info['account_age_years'],
                base_info['friends_count'],
                base_info['rap_value']
            )
            
            return base_info
            
        except Exception as e:
            print(f"Detailed account info error: {e}")
            return None

    def get_profile_info(self, cookie, csrf_token, user_id):
        """Информация профиля"""
        try:
            response = self.make_authenticated_request(
                f'https://users.roblox.com/v1/users/{user_id}',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                data = response.json()
                return {
                    'description': data.get('description', ''),
                    'followers_count': data.get('followersCount', 0),
                    'following_count': data.get('followingsCount', 0),
                }
        except:
            pass
        return {
            'description': '',
            'followers_count': 0,
            'following_count': 0
        }

    def get_economy_info(self, cookie, csrf_token):
        """Информация об экономике"""
        try:
            response = self.make_authenticated_request(
                'https://economy.roblox.com/v1/users/currency',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                data = response.json()
                return {
                    'robux_balance': data.get('robux', 0),
                    'pending_robux': data.get('pendingRobux', 0),
                    'total_robux': data.get('robux', 0) + data.get('pendingRobux', 0)
                }
        except:
            pass
        return {
            'robux_balance': 0,
            'pending_robux': 0,
            'total_robux': 0
        }

    def get_premium_status(self, cookie, csrf_token, user_id):
        """Статус Premium"""
        try:
            response = self.make_authenticated_request(
                f'https://premiumfeatures.roblox.com/v1/users/{user_id}/premium',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                data = response.json()
                return {
                    'premium': data.get('isPremium', False),
                    'premium_status': 'Active' if data.get('isPremium') else 'Inactive'
                }
        except:
            pass
        return {
            'premium': False,
            'premium_status': 'Inactive'
        }

    def get_social_info(self, cookie, csrf_token, user_id):
        """Социальная информация"""
        friends_count = 0
        try:
            response = self.make_authenticated_request(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                data = response.json()
                friends_count = data.get('count', 0)
        except:
            pass
            
        return {
            'friends_count': friends_count
        }

    def get_security_info(self, cookie, csrf_token, user_id):
        """Информация о безопасности"""
        tfa_enabled = False
        try:
            response = self.make_authenticated_request(
                'https://twostepverification.roblox.com/v1/users/' + str(user_id) + '/configuration',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                data = response.json()
                tfa_enabled = data.get('twoStepVerificationEnabled', False)
        except:
            pass
            
        return {
            '2fa_enabled': tfa_enabled
        }

    def get_additional_metrics(self, cookie, csrf_token, user_id):
        """Дополнительные метрики"""
        rap_value = 0
        try:
            # Простая оценка RAP на основе инвентаря
            response = self.make_authenticated_request(
                f'https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?limit=50',
                cookie,
                csrf_token
            )
            if response and response.status_code == 200:
                data = response.json()
                rap_value = len(data.get('data', [])) * 50  # Базовая оценка
        except:
            pass
            
        return {
            'rap_value': rap_value
        }

    def calculate_account_age(self, created_date_str):
        """Расчет возраста аккаунта"""
        if not created_date_str:
            return {'account_age_days': 0, 'account_age_years': 0, 'formatted_date': 'Unknown'}
        
        try:
            created_date = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
            now = datetime.now()
            
            age_delta = now - created_date
            age_days = age_delta.days
            age_years = age_days / 365.25
            
            return {
                'account_age_days': age_days,
                'account_age_years': round(age_years, 1),
                'formatted_date': created_date.strftime('%Y-%m-%d')
            }
        except:
            return {'account_age_days': 0, 'account_age_years': 0, 'formatted_date': 'Unknown'}

    def calculate_account_value(self, robux, is_premium, age_years, friends_count, rap_value):
        """Расчет стоимости аккаунта"""
        try:
            value = robux * 0.0035
            value += rap_value * 0.001
            value += age_years * 200
            value += friends_count * 2
            
            if is_premium:
                value += 300
                
            return round(max(value, 5), 2)
        except:
            return 5.0

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
        
        # Фильтрация и очистка куки
        for cookie in cookies:
            clean_cookie = self.clean_cookie(cookie)
            if clean_cookie:
                valid_cookies.append(clean_cookie)
        
        if not valid_cookies:
            return [self.error_result("", "No valid cookies found")]
        
        results = []
        max_workers = min(2, len(valid_cookies))  # Меньше потоков для стабильности
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_cookie = {
                executor.submit(self.check_single_cookie, cookie): cookie 
                for cookie in valid_cookies
            }
            
            for future in as_completed(future_to_cookie):
                try:
                    result = future.result(timeout=60)
                    results.append(result)
                    time.sleep(2)  # Большая задержка для избежания бана
                except Exception as e:
                    cookie = future_to_cookie[future]
                    results.append(self.error_result(cookie, f"Check timeout: {str(e)}"))
        
        return results

checker = AdvancedRobloxChecker()

@app.route('/')
def index():
    session_id = get_user_id()
    update_user_session(session_id)
    return render_template('index.html')

@app.route('/api/global_stats')
def api_global_stats():
    """API для получения глобальной статистики"""
    try:
        stats = get_global_stats()
        stats['active_users'] = get_active_users_count()  # Теперь реальные активные пользователи
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Stats error: {str(e)}'}), 500

@app.route('/api/history')
def api_history():
    """API для получения истории"""
    try:
        user_id = get_user_id()
        update_user_session(user_id)
        history = get_user_history(user_id, 20)
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/check', methods=['POST'])
def api_check_cookies():
    """API для проверки куки"""
    try:
        user_id = get_user_id()
        update_user_session(user_id)
        
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
        update_user_session(user_id)
        
        results = get_session_results(session_id, user_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        valid_cookies = [r for r in results if r.get('valid')]
        if not valid_cookies:
            return jsonify({'error': 'No valid cookies'}), 400
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('valid_cookies.txt', cookies_content)
            
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
                    'created_date': acc['formatted_date']
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
        update_user_session(user_id)
        
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
        update_user_session(user_id)
        
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