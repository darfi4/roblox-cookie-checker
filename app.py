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

def get_check_history(limit=20):
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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })

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
        except:
            pass
        return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=32))

    def get_account_details(self, cookie: str):
        """Проверка куки"""
        cookie = cookie.strip()
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-CSRF-TOKEN': self.get_csrf_token(cookie),
        }
        
        try:
            # Проверка аутентификации
            auth_response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=15
            )
            
            if auth_response.status_code == 401:
                return self.error_result(cookie, 'Invalid cookie (Unauthorized)')
            elif auth_response.status_code != 200:
                return self.error_result(cookie, f'Auth failed: {auth_response.status_code}')
            
            auth_data = auth_response.json()
            if not auth_data.get('id'):
                return self.error_result(cookie, 'Invalid user data')
            
            user_id = auth_data['id']
            
            # Получение информации
            profile_data = self.get_profile_info(headers, user_id)
            economy_data = self.get_economy_info(headers, user_id)
            premium_data = self.get_premium_status(headers, user_id)
            friends_data = self.get_friends_count(headers, user_id)
            
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
                    '2fa_enabled': self.check_2fa_status(headers),
                },
                'social': {
                    'friends_count': friends_data['count'],
                    'followers_count': profile_data.get('followers_count', 0),
                },
                'account_value': account_value,
                'checked_at': datetime.now().isoformat()
            }

        except Exception as e:
            return self.error_result(cookie, f"Check error: {str(e)}")

    def get_profile_info(self, headers, user_id):
        """Информация о профиле"""
        try:
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
                }
        except:
            pass
        return {'followers_count': 0, 'following_count': 0}

    def get_economy_info(self, headers, user_id):
        """Информация об экономике"""
        try:
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
        except:
            pass
        return {'robux': 0, 'pending_robux': 0}

    def get_premium_status(self, headers, user_id):
        """Статус Premium"""
        try:
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
        except:
            pass
        return {'isPremium': False, 'status': 'Inactive'}

    def get_friends_count(self, headers, user_id):
        """Количество друзей"""
        try:
            response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {'count': data.get('count', 0)}
        except:
            pass
        return {'count': 0}

    def check_2fa_status(self, headers):
        """Проверка 2FA"""
        try:
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/email',
                headers=headers,
                timeout=5
            )
            return response.status_code == 200
        except:
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
        except:
            return {'days': 0, 'years': 0, 'formatted_date': 'Unknown'}

    def calculate_account_value(self, robux, is_premium, age_years, friends_count):
        """Расчет стоимости аккаунта"""
        value = robux * 0.0035
        
        if is_premium:
            value += 500
        
        value += age_years * 300
        value += min(friends_count * 10, 1000)
        
        return round(max(value, 10), 2)

    def error_result(self, cookie: str, error: str):
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
                    result = self.get_account_details(cookie.strip())
                    results.append(result)
                    
                    if i < len(cookies) - 1:
                        time.sleep(1.5)
                        
                except Exception as e:
                    results.append(self.error_result(cookie, f"Check failed: {str(e)}"))
                    time.sleep(0.5)
                    
        return results

checker = AdvancedRobloxChecker()

# Маршруты
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/history')
def api_history():
    """API для получения истории"""
    check_history = get_check_history(20)
    return jsonify(check_history)

@app.route('/api/check', methods=['POST'])
def api_check_cookies():
    """API для проверки куки"""
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
        
        if len(cookies) > 25:
            return jsonify({'error': 'Too many cookies. Maximum 25 per request.'}), 400
        
        results = checker.check_multiple(cookies)
        
        session_id = datetime.now().strftime('%Y%m%d%H%M%S')
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

@app.route('/api/download/<session_id>')
def api_download_results(session_id):
    """API для скачивания результатов"""
    try:
        results = get_session_results(session_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        valid_cookies = [r for r in results if r.get('valid')]
        
        if not valid_cookies:
            return jsonify({'error': 'No valid cookies'}), 400
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            all_cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('cookies.txt', all_cookies_content)
            
            detailed_report = {
                'check_date': datetime.now().isoformat(),
                'summary': {
                    'total_checked': len(results),
                    'valid': len(valid_cookies),
                    'invalid': len([r for r in results if not r['valid']])
                },
                'cookies': results
            }
            zip_file.writestr('detailed_report.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
            
        zip_buffer.seek(0)
        
        filename = f'roblox_cookies_{datetime.now().strftime("%Y%m%d_%H%M")}.zip'
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({'error': f'Archive error: {str(e)}'}), 500

@app.route('/api/session/<session_id>')
def api_get_session(session_id):
    """API для получения результатов сессии"""
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

@app.route('/api/delete/<session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    """API для удаления сессии"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('DELETE FROM check_history WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Delete failed'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))