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

# Roblox Checker
class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })

    def check_account(self, cookie: str):
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        try:
            # Проверка аккаунта
            response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                return self.error_result(cookie, "Невалидная кука")
            
            account_info = response.json()
            if not account_info.get('id'):
                return self.error_result(cookie, "Неверный ID пользователя")

            # Проверка баланса
            robux_response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=headers,
                timeout=5
            )
            
            robux_data = robux_response.json() if robux_response.status_code == 200 else {}
            robux_balance = robux_data.get('robux', 0)

            # Проверка Premium
            premium_response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=headers,
                timeout=5
            )
            
            premium_data = premium_response.json() if premium_response.status_code == 200 else {}
            is_premium = premium_data.get('isPremium', False)

            return {
                'valid': True,
                'cookie': cookie,
                'account_info': account_info,
                'robux_balance': robux_balance,
                'is_premium': is_premium,
                'checked_at': datetime.now().isoformat()
            }

        except Exception as e:
            return self.error_result(cookie, f"Ошибка проверки: {str(e)}")

    def error_result(self, cookie: str, error: str):
        return {
            'valid': False,
            'cookie': cookie,
            'error': error,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple(self, cookies):
        results = []
        for cookie in cookies:
            if cookie.strip():
                result = self.check_account(cookie.strip())
                results.append(result)
                time.sleep(0.5)  # Задержка чтобы не блокировали
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
        
        if len(cookies) > 100:
            return jsonify({'error': 'Too many cookies. Maximum 100 per request.'}), 400
        
        results = checker.check_multiple(cookies)
        
        # Сохраняем результаты в сессии для скачивания
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
        
        # Сортируем куки по категориям
        valid_cookies = [r for r in results if r.get('valid')]
        invalid_cookies = [r for r in results if not r.get('valid')]
        
        premium_cookies = [r for r in valid_cookies if r.get('is_premium')]
        non_premium_cookies = [r for r in valid_cookies if not r.get('is_premium')]
        
        # Сортируем по балансу Robux
        rich_cookies = [r for r in valid_cookies if r.get('robux_balance', 0) > 1000]
        normal_cookies = [r for r in valid_cookies if 0 < r.get('robux_balance', 0) <= 1000]
        zero_balance_cookies = [r for r in valid_cookies if r.get('robux_balance', 0) == 0]
        
        # Создаем ZIP архив в памяти
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Все валидные куки
            if valid_cookies:
                valid_content = "\n".join([r['cookie'] for r in valid_cookies])
                zip_file.writestr('valid_cookies.txt', valid_content)
            
            # 2. Премиум куки
            if premium_cookies:
                premium_content = "\n".join([r['cookie'] for r in premium_cookies])
                zip_file.writestr('premium_cookies.txt', premium_content)
            
            # 3. Куки с балансом > 1000 Robux
            if rich_cookies:
                rich_content = "\n".join([r['cookie'] for r in rich_cookies])
                zip_file.writestr('rich_cookies_1000+_robux.txt', rich_content)
            
            # 4. Куки с балансом 1-1000 Robux
            if normal_cookies:
                normal_content = "\n".join([r['cookie'] for r in normal_cookies])
                zip_file.writestr('normal_cookies_1-1000_robux.txt', normal_content)
            
            # 5. Куки без Robux
            if zero_balance_cookies:
                zero_content = "\n".join([r['cookie'] for r in zero_balance_cookies])
                zip_file.writestr('zero_balance_cookies.txt', zero_content)
            
            # 6. Невалидные куки
            if invalid_cookies:
                invalid_content = "\n".join([r['cookie'] for r in invalid_cookies])
                zip_file.writestr('invalid_cookies.txt', invalid_content)
            
            # 7. Детальный отчет JSON
            detailed_report = {
                'summary': {
                    'total_checked': len(results),
                    'valid': len(valid_cookies),
                    'invalid': len(invalid_cookies),
                    'premium': len(premium_cookies),
                    'with_robux': len(rich_cookies) + len(normal_cookies),
                    'check_date': datetime.now().isoformat()
                },
                'cookies': results
            }
            zip_file.writestr('detailed_report.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
            
            # 8. README файл с инструкциями
            readme_content = """Roblox Cookie Checker Pro - Результаты проверки

Файлы в архиве:
1. valid_cookies.txt - Все валидные куки
2. premium_cookies.txt - Куки с активной Premium подпиской
3. rich_cookies_1000+_robux.txt - Куки с балансом более 1000 Robux
4. normal_cookies_1-1000_robux.txt - Куки с балансом от 1 до 1000 Robux
5. zero_balance_cookies.txt - Валидные куки без Robux
6. invalid_cookies.txt - Невалидные куки
7. detailed_report.json - Детальный отчет в JSON формате

Проверка выполнена: {date}
Всего проверено: {total}
Валидных: {valid}
Невалидных: {invalid}
""".format(
    date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    total=len(results),
    valid=len(valid_cookies),
    invalid=len(invalid_cookies)
)
            zip_file.writestr('README.txt', readme_content)
        
        zip_buffer.seek(0)
        
        # Очищаем сессию
        app.config.pop(f'session_{session_id}', None)
        
        filename = f'roblox_cookies_results_{datetime.now().strftime("%Y%m%d_%H%M")}.zip'
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        return f"Ошибка при создании архива: {str(e)}", 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))