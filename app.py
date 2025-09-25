import os
import json
import zipfile
import io
import sqlite3
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def get_account_details(self, cookie: str):
        """Улучшенная проверка куки на основе MeowTool"""
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-CSRF-TOKEN': ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=32))
        }
        
        try:
            # Проверка валидности куки через аутентификацию
            auth_response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=15
            )
            
            if auth_response.status_code != 200:
                return self.error_result(cookie, f"Auth failed: {auth_response.status_code}")
            
            user_data = auth_response.json()
            if not user_data.get('id'):
                return self.error_result(cookie, "Invalid user data")
            
            user_id = user_data['id']
            
            # Получение расширенной информации об аккаунте
            account_info = self.get_extended_account_info(headers, user_id)
            economy_info = self.get_economy_info(headers, user_id)
            premium_info = self.get_premium_status(headers)
            security_info = self.get_security_info(headers, user_id)
            
            # Расчет возраста аккаунта
            created_date_str = user_data.get('created', '')
            created_date, account_age_years = self.calculate_account_age(created_date_str)
            
            # Оценка стоимости
            account_value = self.calculate_account_value(
                economy_info.get('robux', 0),
                premium_info.get('isPremium', False),
                account_age_years,
                economy_info.get('total_spent', 0)
            )
            
            return {
                'valid': True,
                'cookie': cookie,
                'account_info': {
                    'username': user_data.get('name', 'N/A'),
                    'display_name': user_data.get('displayName', user_data.get('name', 'N/A')),
                    'user_id': user_id,
                    'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                    'created_date': created_date.strftime('%Y-%m-%d') if created_date else 'Unknown',
                    'account_age_days': (datetime.now() - created_date).days if created_date else 0,
                    'account_age_years': round(account_age_years, 1)
                },
                'economy': {
                    'robux_balance': economy_info.get('robux', 0),
                    'pending_robux': economy_info.get('pendingRobux', 0),
                    'total_robux': economy_info.get('robux', 0) + economy_info.get('pendingRobux', 0),
                    'all_time_spent': economy_info.get('total_spent', 0)
                },
                'premium': premium_info,
                'security': security_info,
                'account_value': account_value,
                'checked_at': datetime.now().isoformat(),
                'friends_count': account_info.get('friends_count', 0),
                'followers_count': account_info.get('followers_count', 0),
                'following_count': account_info.get('following_count', 0)
            }

        except Exception as e:
            return self.error_result(cookie, f"Check error: {str(e)}")

    def get_extended_account_info(self, headers, user_id):
        """Получение расширенной информации об аккаунте"""
        try:
            # Информация о профиле
            profile_response = self.session.get(
                f'https://users.roblox.com/v1/users/{user_id}',
                headers=headers,
                timeout=10
            )
            profile_data = profile_response.json() if profile_response.status_code == 200 else {}
            
            # Количество друзей
            friends_response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                headers=headers,
                timeout=10
            )
            friends_data = friends_response.json() if friends_response.status_code == 200 else {}
            
            # Подписчики и подписки
            followers_response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/followers/count',
                headers=headers,
                timeout=10
            )
            followers_data = followers_response.json() if followers_response.status_code == 200 else {}
            
            following_response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/followings/count',
                headers=headers,
                timeout=10
            )
            following_data = following_response.json() if following_response.status_code == 200 else {}
            
            return {
                'friends_count': friends_data.get('count', 0),
                'followers_count': followers_data.get('count', 0),
                'following_count': following_data.get('count', 0),
                'description': profile_data.get('description', ''),
                'is_banned': profile_data.get('isBanned', False)
            }
            
        except:
            return {}

    def get_economy_info(self, headers, user_id):
        """Информация об экономике аккаунта"""
        try:
            # Баланс Robux
            economy_response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=headers,
                timeout=10
            )
            economy_data = economy_response.json() if economy_response.status_code == 200 else {}
            
            # История трат (приблизительная)
            transactions_response = self.session.get(
                f'https://economy.roblox.com/v1/users/{user_id}/transactions?transactionType=Purchase&limit=1',
                headers=headers,
                timeout=10
            )
            total_spent = 0
            if transactions_response.status_code == 200:
                transactions_data = transactions_response.json()
                # Примерная оценка трат
                total_spent = len(transactions_data.get('data', [])) * 100
            
            return {
                'robux': economy_data.get('robux', 0),
                'pendingRobux': economy_data.get('pendingRobux', 0),
                'total_spent': total_spent
            }
            
        except:
            return {'robux': 0, 'pendingRobux': 0, 'total_spent': 0}

    def get_premium_status(self, headers):
        """Статус Premium подписки"""
        try:
            premium_response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=headers,
                timeout=10
            )
            if premium_response.status_code == 200:
                premium_data = premium_response.json()
                return {
                    'isPremium': premium_data.get('isPremium', False),
                    'status': 'Active' if premium_data.get('isPremium') else 'Inactive'
                }
        except:
            pass
        return {'isPremium': False, 'status': 'Unknown'}

    def get_security_info(self, headers, user_id):
        """Информация о безопасности аккаунта"""
        try:
            # Проверка 2FA
            settings_response = self.session.get(
                'https://accountsettings.roblox.com/v1/email',
                headers=headers,
                timeout=10
            )
            email_verified = settings_response.status_code == 200
            
            # Проверка телефона
            phone_response = self.session.get(
                'https://accountsettings.roblox.com/v1/phone',
                headers=headers,
                timeout=10
            )
            phone_verified = phone_response.status_code == 200
            
            return {
                '2fa_enabled': email_verified,  # Упрощенная проверка
                'phone_verified': phone_verified,
                'email_verified': email_verified,
                'pin_enabled': False  # Сложно проверить без дополнительных запросов
            }
            
        except:
            return {'2fa_enabled': False, 'phone_verified': False, 'email_verified': False, 'pin_enabled': False}

    def calculate_account_age(self, created_date_str):
        """Расчет возраста аккаунта"""
        if not created_date_str:
            return datetime.now(), 0
            
        try:
            # Пробуем разные форматы даты
            for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    created_date = datetime.strptime(created_date_str, fmt)
                    age_days = (datetime.now() - created_date).days
                    age_years = age_days / 365.25
                    return created_date, age_years
                except ValueError:
                    continue
        except:
            pass
            
        return datetime.now(), 0

    def calculate_account_value(self, robux, is_premium, age_years, total_spent):
        """Оценка стоимости аккаунта"""
        value = 0
        value += robux * 0.003  # Примерная стоимость Robux
        value += 500 if is_premium else 0  # Стоимость Premium
        value += age_years * 300  # Чем старше аккаунт, тем дороже
        value += total_spent * 0.001  # Учитываем траты
        return round(max(value, 10), 2)  # Минимальная стоимость $10

    def error_result(self, cookie: str, error: str):
        return {
            'valid': False,
            'cookie': cookie,
            'error': error,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple(self, cookies):
        """Проверка нескольких куки с разумными задержками"""
        results = []
        for i, cookie in enumerate(cookies):
            if cookie.strip():
                try:
                    result = self.get_account_details(cookie.strip())
                    results.append(result)
                    
                    # Задержка между запросами чтобы избежать блокировки
                    if i < len(cookies) - 1:
                        time.sleep(1.5)
                        
                except Exception as e:
                    results.append(self.error_result(cookie, f"Check failed: {str(e)}"))
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
        
        if len(cookies) > 30:  # Уменьшаем лимит для стабильности
            return jsonify({'error': 'Too many cookies. Maximum 30 per request.'}), 400
        
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
        '1-10_robux': [r for r in valid_cookies if 1 <= r['economy']['total_robux'] <= 10],
        '10-25_robux': [r for r in valid_cookies if 10 < r['economy']['total_robux'] <= 25],
        '25-50_robux': [r for r in valid_cookies if 25 < r['economy']['total_robux'] <= 50],
        '50-100_robux': [r for r in valid_cookies if 50 < r['economy']['total_robux'] <= 100],
        '100-500_robux': [r for r in valid_cookies if 100 < r['economy']['total_robux'] <= 500],
        '500-1000_robux': [r for r in valid_cookies if 500 < r['economy']['total_robux'] <= 1000],
        '1000+_robux': [r for r in valid_cookies if r['economy']['total_robux'] > 1000]
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
    
    # Сортировка по Premium
    premium_cookies = [r for r in valid_cookies if r['premium']['isPremium']]
    non_premium_cookies = [r for r in valid_cookies if not r['premium']['isPremium']]
    
    if premium_cookies:
        content = "\n".join([r['cookie'] for r in premium_cookies])
        zip_file.writestr('Сортировка/По Premium/С Premium.txt', content)
    
    if non_premium_cookies:
        content = "\n".join([r['cookie'] for r in non_premium_cookies])
        zip_file.writestr('Сортировка/По Premium/Без Premium.txt', content)

def get_year_categories(valid_cookies, current_year):
    """Категории по годам регистрации"""
    categories = {}
    
    for cookie in valid_cookies:
        year = get_year_from_date(cookie['account_info']['created_date'])
        if year:
            if 2004 <= year <= 2010:
                categories.setdefault('2004-2010', []).append(cookie)
            elif 2011 <= year <= 2015:
                categories.setdefault('2011-2015', []).append(cookie)
            elif 2016 <= year <= 2019:
                categories.setdefault('2016-2019', []).append(cookie)
            elif 2020 <= year <= 2022:
                categories.setdefault('2020-2022', []).append(cookie)
            elif 2023 <= year <= current_year:
                categories.setdefault('2023-now', []).append(cookie)
    
    return categories

def get_year_from_date(date_str):
    """Извлечение года из даты"""
    try:
        return int(date_str.split('-')[0])
    except:
        return None

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

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

if __name__ == '__main__':
    import random
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))