from flask import Flask, render_template, request, jsonify, send_file
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
db.init_app(app)

class RobloxCookieChecker:
    def __init__(self, cookie):
        self.cookie = cookie
        self.session = requests.Session()
        self.session.cookies['.ROBLOSECURITY'] = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_account_info(self):
        try:
            # Получение основной информации об аккаунте
            response = self.session.get('https://www.roblox.com/mobileapi/userinfo', headers=self.headers)
            if response.status_code != 200:
                return None
            return response.json()
        except:
            return None

    def get_economy_info(self):
        try:
            response = self.session.get('https://economy.roblox.com/v1/user/currency', headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def get_premium_status(self):
        try:
            response = self.session.get('https://premiumfeatures.roblox.com/v1/users/premium/membership', headers=self.headers)
            return response.status_code == 200
        except:
            return False

    def get_2fa_status(self):
        try:
            response = self.session.get('https://auth.roblox.com/v2/account/settings/metadata', headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                return data.get('isTwoStepVerificationEnabled', False)
            return False
        except:
            return False

    def check_billing(self):
        try:
            response = self.session.get('https://billing.roblox.com/v1/paymentmethods', headers=self.headers)
            return response.status_code == 200
        except:
            return False

    def check_phone_verification(self):
        try:
            response = self.session.get('https://accountsettings.roblox.com/v1/email', headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                return data.get('verified', False)
            return False
        except:
            return False

    def get_rap_stats(self):
        try:
            response = self.session.get('https://inventory.roblox.com/v1/users/1/items/Collectibles?limit=10', headers=self.headers)
            if response.status_code == 200:
                # Упрощенная проверка наличия коллекционных предметов
                data = response.json()
                return len(data.get('data', [])) > 0
            return False
        except:
            return False

    def check_cookie(self):
        account_info = self.get_account_info()
        if not account_info:
            return {"error": "Invalid cookie"}

        economy_info = self.get_economy_info()
        
        result = {
            "account_id": account_info.get('UserID'),
            "username": account_info.get('UserName'),
            "profile_link": f"https://www.roblox.com/users/{account_info.get('UserID')}/profile",
            "account_created": account_info.get('Created'),
            "balance": economy_info.get('robux', 0) if economy_info else 0,
            "pending_robux": 0,  # Упрощенная реализация
            "premium": self.get_premium_status(),
            "2fa": self.get_2fa_status(),
            "card": self.check_billing(),
            "phone": self.check_phone_verification(),
            "rap": self.get_rap_stats(),
            "pending_group_robux": 0,  # Упрощенная реализация
            "total_spent": 0  # Упрощенная реализация
        }
        
        return result

def get_user_session():
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
    
    session = UserSession.query.filter_by(session_id=session_id).first()
    if not session:
        session = UserSession(session_id=session_id, browser_info=request.headers.get('User-Agent', ''))
        db.session.add(session)
        db.session.commit()
    
    return session

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/check_cookie', methods=['POST'])
def check_cookie():
    data = request.json
    cookie = data.get('cookie', '').strip()
    
    if not cookie:
        return jsonify({"error": "Cookie is required"})
    
    checker = RobloxCookieChecker(cookie)
    result = checker.check_cookie()
    
    if "error" not in result:
        # Сохраняем результат в базу
        session = get_user_session()
        check_id = str(uuid.uuid4())
        
        cookie_check = CookieCheck(
            session_id=session.session_id,
            check_id=check_id,
            cookie_data=cookie[:50] + "..." if len(cookie) > 50 else cookie,
            result_data=json.dumps(result),
            account_age=0,  # Расчет возраста аккаунта
            balance=result.get('balance', 0),
            rap=100 if result.get('rap') else 0,  # Упрощенное значение RAP
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

@app.route('/get_history')
def get_history():
    session = get_user_session()
    checks = CookieCheck.query.filter_by(session_id=session.session_id).order_by(CookieCheck.created_at.desc()).all()
    
    history_data = []
    for check in checks:
        history_data.append({
            'check_id': check.check_id,
            'created_at': check.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'username': json.loads(check.result_data).get('username', 'Unknown'),
            'balance': check.balance,
            'premium': check.has_premium,
            '2fa': check.has_2fa
        })
    
    return jsonify(history_data)

@app.route('/download_history/<check_id>')
def download_history(check_id):
    check = CookieCheck.query.filter_by(check_id=check_id).first()
    if not check:
        return "Check not found", 404
    
    result_data = json.loads(check.result_data)
    
    # Создаем ZIP архив в памяти
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        # Основная информация
        main_info = f"""
Проверка куки: {check_id}
Дата проверки: {check.created_at}
Аккаунт: {result_data.get('username', 'Unknown')} (ID: {result_data.get('account_id')})

=== ОСНОВНАЯ ИНФОРМАЦИЯ ===
Баланс Robux: {result_data.get('balance', 0)}
Pending Robux: {result_data.get('pending_robux', 0)}
Premium: {'✅' if result_data.get('premium') else '❌'}
2FA: {'✅' if result_data.get('2fa') else '❌'}
Привязанная карта: {'✅' if result_data.get('card') else '❌'}
Привязанный телефон: {'✅' if result_data.get('phone') else '❌'}
RAP: {'✅' if result_data.get('rap') else '❌'}

Ссылка на профиль: {result_data.get('profile_link')}
Дата создания: {result_data.get('account_created', 'Unknown')}
        """
        zip_file.writestr(f"Проверка куки {check_id}/Основная информация.txt", main_info)
        
        # Сортировка по балансу
        balance_sort = f"Баланс: {result_data.get('balance', 0)} Robux"
        zip_file.writestr(f"Проверка куки {check_id}/Сортировка по балансу.txt", balance_sort)
        
        # Сортировка по тоталу
        total_sort = f"Всего потрачено: {result_data.get('total_spent', 0)} Robux"
        zip_file.writestr(f"Проверка куки {check_id}/Сортировка по тоталу.txt", total_sort)
        
        # Сортировка по RAP
        rap_sort = f"RAP статус: {'Есть коллекционные предметы' if result_data.get('rap') else 'Нет коллекционных предметов'}"
        zip_file.writestr(f"Проверка куки {check_id}/Сортировка по RAP.txt", rap_sort)
        
        # Дополнительная информация
        additional_info = f"""
=== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ===
Pending Group Robux: {result_data.get('pending_group_robux', 0)}
Billing доступ: {'✅' if result_data.get('card') else '❌'}
        """
        zip_file.writestr(f"Проверка куки {check_id}/Дополнительная информация.txt", additional_info)
    
    zip_buffer.seek(0)
    
    response = send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"cookie_check_{check_id}.zip",
        mimetype='application/zip'
    )
    
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)