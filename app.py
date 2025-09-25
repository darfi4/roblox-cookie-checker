import os
import json
import zipfile
import io
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, flash
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
            
            # Получаем дополнительные данные
            profile_response = self.session.get(
                f'https://users.roblox.com/v1/users/{user_id}',
                headers=headers,
                timeout=5
            )
            profile_data = profile_response.json() if profile_response.status_code == 200 else {}
            
            # Получаем данные о группах
            groups_response = self.session.get(
                f'https://groups.roblox.com/v2/users/{user_id}/groups/roles',
                headers=headers,
                timeout=5
            )
            groups_data = groups_response.json() if groups_response.status_code == 200 else {}
            
            # Получаем данные о друзьях (для оценки активности)
            friends_response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                headers=headers,
                timeout=5
            )
            friends_data = friends_response.json() if friends_response.status_code == 200 else {}
            
            # Получаем данные об аватаре (оценка стоимости)
            avatar_response = self.session.get(
                f'https://avatar.roblox.com/v1/users/{user_id}/avatar',
                headers=headers,
                timeout=5
            )
            avatar_data = avatar_response.json() if avatar_response.status_code == 200 else {}
            
            # Получаем транзакции (оценка трат)
            transactions_response = self.session.get(
                f'https://economy.roblox.com/v1/users/{user_id}/transaction-totals?transactionType=Purchase',
                headers=headers,
                timeout=5
            )
            transactions_data = transactions_response.json() if transactions_response.status_code == 200 else {}

            # Расчет возраста аккаунта
            created_date = datetime.fromisoformat(user_data['created'].replace('Z', '+00:00'))
            account_age_days = (datetime.now() - created_date).days
            account_age_years = account_age_days / 365.25

            # Оценка стоимости аккаунта
            account_value = self.calculate_account_value(
                economy_data.get('robux', 0),
                premium_data.get('isPremium', False),
                account_age_years,
                len(groups_data.get('data', [])),
                friends_data.get('count', 0),
                transactions_data.get('purchaseTotal', 0)
            )

            return {
                'valid': True,
                'cookie': cookie,
                'account_info': {
                    'username': user_data.get('name', 'N/A'),
                    'display_name': user_data.get('displayName', 'N/A'),
                    'user_id': user_id,
                    'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                    'created_date': created_date.strftime('%Y-%m-%d'),
                    'account_age_days': account_age_days,
                    'account_age_years': round(account_age_years, 1)
                },
                'economy': {
                    'robux_balance': economy_data.get('robux', 0),
                    'pending_robux': economy_data.get('pendingRobux', 0),
                    'total_robux': economy_data.get('robux', 0) + economy_data.get('pendingRobux', 0),
                    'all_time_spent': transactions_data.get('purchaseTotal', 0)
                },
                'premium': {
                    'is_premium': premium_data.get('isPremium', False),
                    'status': 'Active' if premium_data.get('isPremium') else 'Inactive'
                },
                'security': {
                    '2fa_enabled': self.check_2fa_status(headers),
                    'phone_verified': self.check_phone_status(headers),
                    'email_verified': True  # Предполагаем что email верифицирован
                },
                'social': {
                    'friends_count': friends_data.get('count', 0),
                    'groups_count': len(groups_data.get('data', [])),
                    'followers_count': profile_data.get('followersCount', 0),
                    'following_count': profile_data.get('followingsCount', 0)
                },
                'account_value': account_value,
                'checked_at': datetime.now().isoformat()
            }

        except Exception as e:
            return self.error_result(cookie, f"Ошибка проверки: {str(e)}")

    def calculate_account_value(self, robux, is_premium, age_years, groups_count, friends_count, total_spent):
        value = 0
        value += robux * 0.003  # Примерная стоимость Robux
        value += 1000 if is_premium else 0  # Стоимость Premium
        value += age_years * 500  # Чем старше аккаунт, тем дороже
        value += groups_count * 50  # Активность в группах
        value += friends_count * 10  # Социальная активность
        value += total_spent * 0.001  # Учитываем траты
        return round(value, 2)

    def check_2fa_status(self, headers):
        try:
            response = self.session.get(
                'https://twostepverification.roblox.com/v1/metadata',
                headers=headers,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def check_phone_status(self, headers):
        try:
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/phone',
                headers=headers,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

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
                # Добавляем задержку между запросами
                if i < len(cookies) - 1:
                    time.sleep(1)
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
        
        # Создаем ZIP архив
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Папка КУКИ
            all_cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('КУКИ/Все проверенные куки.txt', all_cookies_content)
            
            # Папка Сортировка
            self.create_sorted_files(zip_file, valid_cookies)
            
            # Детальный отчет
            detailed_report = self.create_detailed_report(results)
            zip_file.writestr('Детальный отчет.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
            
            # README
            readme_content = self.create_readme(results)
            zip_file.writestr('README.txt', readme_content)
        
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

    def create_sorted_files(self, zip_file, valid_cookies):
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
        year_categories = {
            '2004-2010': [r for r in valid_cookies if 2004 <= int(r['account_info']['created_date'][:4]) <= 2010],
            '2011-2015': [r for r in valid_cookies if 2011 <= int(r['account_info']['created_date'][:4]) <= 2015],
            '2016-2019': [r for r in valid_cookies if 2016 <= int(r['account_info']['created_date'][:4]) <= 2019],
            '2020-2022': [r for r in valid_cookies if 2020 <= int(r['account_info']['created_date'][:4]) <= 2022],
            '2023-2024': [r for r in valid_cookies if 2023 <= int(r['account_info']['created_date'][:4]) <= 2024]
        }
        
        for category, cookies in year_categories.items():
            if cookies:
                content = "\n".join([r['cookie'] for r in cookies])
                zip_file.writestr(f'Сортировка/По дате регистрации/{category}.txt', content)
        
        # Сортировка по Premium статусу
        premium_cookies = [r for r in valid_cookies if r['premium']['is_premium']]
        non_premium_cookies = [r for r in valid_cookies if not r['premium']['is_premium']]
        
        if premium_cookies:
            content = "\n".join([r['cookie'] for r in premium_cookies])
            zip_file.writestr('Сортировка/По Premium/С Premium.txt', content)
        
        if non_premium_cookies:
            content = "\n".join([r['cookie'] for r in non_premium_cookies])
            zip_file.writestr('Сортировка/По Premium/Без Premium.txt', content)
        
        # Сортировка по стоимости аккаунта
        value_categories = {
            '0-10$': [r for r in valid_cookies if 0 <= r['account_value'] <= 10],
            '10-25$': [r for r in valid_cookies if 10 < r['account_value'] <= 25],
            '25-50$': [r for r in valid_cookies if 25 < r['account_value'] <= 50],
            '50-100$': [r for r in valid_cookies if 50 < r['account_value'] <= 100],
            '100-250$': [r for r in valid_cookies if 100 < r['account_value'] <= 250],
            '250-500$': [r for r in valid_cookies if 250 < r['account_value'] <= 500],
            '500+$': [r for r in valid_cookies if r['account_value'] > 500]
        }
        
        for category, cookies in value_categories.items():
            if cookies:
                content = "\n".join([r['cookie'] for r in cookies])
                zip_file.writestr(f'Сортировка/По стоимости/{category}.txt', content)

    def create_detailed_report(self, results):
        return {
            'check_date': datetime.now().isoformat(),
            'summary': {
                'total_checked': len(results),
                'valid': len([r for r in results if r['valid']]),
                'invalid': len([r for r in results if not r['valid']])
            },
            'cookies': results
        }

    def create_readme(self, results):
        valid_count = len([r for r in results if r['valid']])
        return f"""Roblox Cookie Checker Pro - Результаты проверки

Дата проверки: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Всего проверено: {len(results)}
Валидных: {valid_count}
Невалидных: {len(results) - valid_count}

Структура архива:
📁 КУКИ/
  └── Все проверенные куки.txt - Все валидные куки в одном файле

📁 Сортировка/
  📁 По балансу/ - Сортировка по количеству Robux
  📁 По дате регистрации/ - Сортировка по возрасту аккаунта  
  📁 По Premium/ - Сортировка по наличию Premium подписки
  📁 По стоимости/ - Сортировка по примерной стоимости аккаунта

📄 Детальный отчет.json - Полная информация по всем куки
📄 README.txt - Этот файл

Каждая кука проверена через официальные API Roblox.
"""

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))