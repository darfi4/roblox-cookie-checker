import os
import json
import zipfile
import io
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
import requests
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })

    def get_account_details(self, cookie: str):
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        try:
            # Основная информация аккаунта
            user_response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=10
            )
            
            if user_response.status_code != 200:
                return self.error_result(cookie, "Невалидная кука")
            
            user_data = user_response.json()
            user_id = user_data.get('id')
            
            if not user_id:
                return self.error_result(cookie, "Неверный ID пользователя")

            # Баланс Robux
            economy_response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=headers,
                timeout=5
            )
            economy_data = economy_response.json() if economy_response.status_code == 200 else {}
            
            # Premium статус
            premium_response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=headers,
                timeout=5
            )
            premium_data = premium_response.json() if premium_response.status_code == 200 else {}
            
            # Расчет возраста аккаунта
            created_date_str = user_data.get('created', '')
            if created_date_str:
                try:
                    created_date = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
                    account_age_days = (datetime.now() - created_date).days
                    account_age_years = account_age_days / 365.25
                    created_formatted = created_date.strftime('%Y-%m-%d')
                except:
                    created_date = datetime.now()
                    account_age_days = 0
                    account_age_years = 0
                    created_formatted = 'Unknown'
            else:
                created_date = datetime.now()
                account_age_days = 0
                account_age_years = 0
                created_formatted = 'Unknown'

            # Оценка стоимости аккаунта
            account_value = self.calculate_account_value(
                economy_data.get('robux', 0),
                premium_data.get('isPremium', False),
                account_age_years
            )

            return {
                'valid': True,
                'cookie': cookie,
                'account_info': {
                    'username': user_data.get('name', 'N/A'),
                    'display_name': user_data.get('displayName', 'N/A'),
                    'user_id': user_id,
                    'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                    'created_date': created_formatted,
                    'account_age_days': account_age_days,
                    'account_age_years': round(account_age_years, 1)
                },
                'economy': {
                    'robux_balance': economy_data.get('robux', 0),
                    'pending_robux': economy_data.get('pendingRobux', 0),
                    'total_robux': economy_data.get('robux', 0) + economy_data.get('pendingRobux', 0)
                },
                'premium': {
                    'is_premium': premium_data.get('isPremium', False),
                    'status': 'Active' if premium_data.get('isPremium') else 'Inactive'
                },
                'security': {
                    '2fa_enabled': False,  # Упрощаем проверку
                    'phone_verified': False
                },
                'account_value': account_value,
                'checked_at': datetime.now().isoformat()
            }

        except Exception as e:
            return self.error_result(cookie, f"Ошибка проверки: {str(e)}")

    def calculate_account_value(self, robux, is_premium, age_years):
        value = 0
        value += robux * 0.003
        value += 1000 if is_premium else 0
        value += age_years * 500
        return round(max(value, 0), 2)

    def error_result(self, cookie: str, error: str):
        return {
            'valid': False,
            'cookie': cookie,
            'error': error,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple(self, cookies):
        results = []
        for i, cookie in enumerate(cookies):
            if cookie.strip():
                result = self.get_account_details(cookie.strip())
                results.append(result)
                if i < len(cookies) - 1:
                    time.sleep(0.5)  # Уменьшаем задержку
        return results

checker = AdvancedRobloxChecker()

@app.route('/')
def index():
    return render_template('index.html')

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
        
        if len(cookies) > 50:
            return jsonify({'error': 'Too many cookies. Maximum 50 per request.'}), 400
        
        results = checker.check_multiple(cookies)
        
        session_id = datetime.now().strftime('%Y%m%d%H%M%S')
        app.config[f'session_{session_id}'] = results
        
        return jsonify({
            'total': len(results),
            'valid': len([r for r in results if r.get('valid', False)]),
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
        results = app.config.get(f'session_{session_id}')
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
        app.config.pop(f'session_{session_id}', None)
        
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
    year_categories = {
        '2004-2010': [r for r in valid_cookies if 2004 <= get_year(r['account_info']['created_date']) <= 2010],
        '2011-2015': [r for r in valid_cookies if 2011 <= get_year(r['account_info']['created_date']) <= 2015],
        '2016-2019': [r for r in valid_cookies if 2016 <= get_year(r['account_info']['created_date']) <= 2019],
        '2020-2022': [r for r in valid_cookies if 2020 <= get_year(r['account_info']['created_date']) <= 2022],
        '2023-now': [r for r in valid_cookies if 2023 <= get_year(r['account_info']['created_date']) <= current_year]
    }
    
    for category, cookies in year_categories.items():
        if cookies:
            content = "\n".join([r['cookie'] for r in cookies])
            zip_file.writestr(f'Сортировка/По дате регистрации/{category}.txt', content)

def get_year(date_str):
    try:
        return int(date_str.split('-')[0])
    except:
        return 2024

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))