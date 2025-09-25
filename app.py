from flask import Flask, render_template, request, jsonify, send_file, make_response
import requests
import json
import uuid
from datetime import datetime
import os
import zipfile
import io
from database import db, UserSession, CookieCheck

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cookie_checker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Добавьте секретный ключ
db.init_app(app)

class RobloxCookieChecker:
    def __init__(self, cookie):
        self.cookie = cookie
        self.session = requests.Session()
        self.session.cookies['.ROBLOSECURITY'] = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def get_account_info(self):
        try:
            response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Account info error: {e}")
            return None

    def get_economy_info(self):
        try:
            # Получаем информацию о балансе
            response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return {'robux': 0}
        except Exception as e:
            print(f"Economy error: {e}")
            return {'robux': 0}

    def get_premium_status(self):
        try:
            response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=self.headers
            )
            return response.status_code == 200
        except:
            return False

    def get_2fa_status(self):
        try:
            response = self.session.get(
                'https://twostepverification.roblox.com/v1/metadata',
                headers=self.headers
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('isEnabled', False)
            return False
        except:
            return False

    def check_billing(self):
        try:
            response = self.session.get(
                'https://billing.roblox.com/v1/credit',
                headers=self.headers
            )
            return response.status_code == 200
        except:
            return False

    def check_phone_verification(self):
        try:
            response = self.session.get(
                'https://accountinformation.roblox.com/v1/phone',
                headers=self.headers
            )
            return response.status_code == 200
        except:
            return False

    def get_avatar_info(self):
        try:
            response = self.session.get(
                'https://avatar.roblox.com/v1/avatar',
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def check_cookie(self):
        try:
            account_info = self.get_account_info()
            if not account_info:
                return {"error": "Invalid or expired cookie"}

            economy_info = self.get_economy_info()
            avatar_info = self.get_avatar_info()
            
            # Получаем дату создания аккаунта
            created_date = datetime.fromisoformat(account_info.get('created', '').replace('Z', '+00:00'))
            account_age_days = (datetime.utcnow() - created_date).days

            result = {
                "account_id": account_info.get('id'),
                "username": account_info.get('name'),
                "profile_link": f"https://www.roblox.com/users/{account_info.get('id')}/profile",
                "account_created": account_info.get('created', 'Unknown'),
                "account_age_days": account_age_days,
                "balance": economy_info.get('robux', 0),
                "pending_robux": 0,
                "premium": self.get_premium_status(),
                "2fa": self.get_2fa_status(),
                "card": self.check_billing(),
                "phone": self.check_phone_verification(),
                "rap": avatar_info is not None,
                "pending_group_robux": 0,
                "total_spent": 0,
                "display_name": account_info.get('displayName', '')
            }
            
            return result
        except Exception as e:
            return {"error": f"Check failed: {str(e)}"}

def get_user_session(request):
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
    
    session = UserSession.query.filter_by(session_id=session_id).first()
    if not session:
        session = UserSession(
            session_id=session_id, 
            browser_info=request.headers.get('User-Agent', '')
        )
        db.session.add(session)
        db.session.commit()
    
    return session

@app.route('/')
def index():
    resp = make_response(render_template('index.html'))
    if not request.cookies.get('session_id'):
        resp.set_cookie('session_id', str(uuid.uuid4()), max_age=365*24*60*60)
    return resp

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/api/check_cookie', methods=['POST'])
def check_cookie():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        cookie = data.get('cookie', '').strip()
        
        if not cookie:
            return jsonify({"error": "Cookie is required"}), 400
        
        checker = RobloxCookieChecker(cookie)
        result = checker.check_cookie()
        
        if "error" not in result:
            session = get_user_session(request)
            check_id = str(uuid.uuid4())
            
            cookie_check = CookieCheck(
                session_id=session.session_id,
                check_id=check_id,
                cookie_data=cookie[:50] + "..." if len(cookie) > 50 else cookie,
                result_data=json.dumps(result, ensure_ascii=False),
                account_age=result.get('account_age_days', 0),
                balance=result.get('balance', 0),
                rap=100 if result.get('rap') else 0,
                total_spent=result.get('total_spent', 0),
                has_2fa=result.get('2fa', False),
                has_premium=result.get('premium', False),
                has_phone=result.get('phone', False),
                has_card=result.get('card', False)
            )
            
            db.session.add(cookie_check)
            db.session.commit()
            
            result['check_id'] = check_id
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/history')
def get_history():
    try:
        session = get_user_session(request)
        checks = CookieCheck.query.filter_by(session_id=session.session_id).order_by(CookieCheck.created_at.desc()).all()
        
        history_data = []
        for check in checks:
            try:
                result_data = json.loads(check.result_data)
                history_data.append({
                    'check_id': check.check_id,
                    'created_at': check.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'username': result_data.get('username', 'Unknown'),
                    'balance': check.balance,
                    'premium': check.has_premium,
                    '2fa': check.has_2fa,
                    'account_age': check.account_age
                })
            except:
                continue
        
        return jsonify(history_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/<check_id>')
def download_history(check_id):
    try:
        check = CookieCheck.query.filter_by(check_id=check_id).first()
        if not check:
            return "Check not found", 404
        
        result_data = json.loads(check.result_data)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Основная информация
            main_info = f"""Проверка куки: {check_id}
Дата проверки: {check.created_at.strftime('%Y-%m-%d %H:%M:%S')}
Аккаунт: {result_data.get('username', 'Unknown')} (ID: {result_data.get('account_id')})
Display Name: {result_data.get('display_name', 'N/A')}

=== ОСНОВНАЯ ИНФОРМАЦИЯ ===
Баланс Robux: {result_data.get('balance', 0)}
Возраст аккаунта: {result_data.get('account_age_days', 0)} дней
Pending Robux: {result_data.get('pending_robux', 0)}
Premium: {'✅' if result_data.get('premium') else '❌'}
2FA: {'✅' if result_data.get('2fa') else '❌'}
Привязанная карта: {'✅' if result_data.get('card') else '❌'}
Привязанный телефон: {'✅' if result_data.get('phone') else '❌'}
RAP: {'✅' if result_data.get('rap') else '❌'}

Ссылка на профиль: {result_data.get('profile_link')}
Дата создания: {result_data.get('account_created', 'Unknown')}
"""
            zip_file.writestr(f"Проверка_{check_id}/Основная_информация.txt", main_info.encode('utf-8'))
            
            # Сортировка по балансу
            balance_info = f"""=== СОРТИРОВКА ПО БАЛАНСУ ===
Аккаунт: {result_data.get('username', 'Unknown')}
Баланс: {result_data.get('balance', 0)} Robux
Рейтинг: {'Высокий' if result_data.get('balance', 0) > 1000 else 'Средний' if result_data.get('balance', 0) > 100 else 'Низкий'}
"""
            zip_file.writestr(f"Проверка_{check_id}/Сортировка_по_балансу.txt", balance_info.encode('utf-8'))
            
            # Сортировка по тоталу
            total_info = f"""=== СОРТИРОВКА ПО ТОТАЛЬНЫМ ТРАТАМ ===
Аккаунт: {result_data.get('username', 'Unknown')}
Всего потрачено: {result_data.get('total_spent', 0)} Robux
Статус: {'Большие траты' if result_data.get('total_spent', 0) > 5000 else 'Средние траты' if result_data.get('total_spent', 0) > 500 else 'Маленькие траты'}
"""
            zip_file.writestr(f"Проверка_{check_id}/Сортировка_по_тоталу.txt", total_info.encode('utf-8'))
            
            # Сортировка по RAP
            rap_info = f"""=== СОРТИРОВКА ПО RAP ===
Аккаунт: {result_data.get('username', 'Unknown')}
RAP статус: {'Есть коллекционные предметы' if result_data.get('rap') else 'Нет коллекционных предметов'}
Оценка: {'Высокий RAP' if result_data.get('rap') else 'Низкий RAP'}
"""
            zip_file.writestr(f"Проверка_{check_id}/Сортировка_по_RAP.txt", rap_info.encode('utf-8'))
            
            # Сортировка по возрасту аккаунта
            age_info = f"""=== СОРТИРОВКА ПО ВОЗРАСТУ АККАУНТА ===
Аккаунт: {result_data.get('username', 'Unknown')}
Возраст: {result_data.get('account_age_days', 0)} дней
Статус: {'Старый аккаунт' if result_data.get('account_age_days', 0) > 365 else 'Средний возраст' if result_data.get('account_age_days', 0) > 30 else 'Новый аккаунт'}
"""
            zip_file.writestr(f"Проверка_{check_id}/Сортировка_по_возрасту.txt", age_info.encode('utf-8'))
        
        zip_buffer.seek(0)
        
        response = make_response(zip_buffer.getvalue())
        response.headers.set('Content-Type', 'application/zip')
        response.headers.set('Content-Disposition', f'attachment; filename=cookie_check_{check_id}.zip')
        
        return response
        
    except Exception as e:
        return f"Error creating archive: {str(e)}", 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=False)