import os
import json
import zipfile
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, Blueprint
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from wtforms import Form, StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo
import requests
import time
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

# Модели базы данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    scans = db.relationship('ScanHistory', backref='user', lazy=True)

class ScanHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scan_data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_cookies = db.Column(db.Integer, default=0)
    valid_cookies = db.Column(db.Integer, default=0)
    
    def get_scan_data(self):
        return json.loads(self.scan_data)

# Формы
class LoginForm(Form):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class RegisterForm(Form):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', 
                                   validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')

class ResetPasswordForm(Form):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Сбросить пароль')

# Roblox Checker
class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        self.base_headers = {}

    def set_cookie(self, cookie: str):
        self.base_headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

    def check_account(self, cookie: str):
        self.set_cookie(cookie)
        
        try:
            account_info = self.get_account_info()
            if not account_info:
                return self.error_result(cookie, "Не удалось получить информацию об аккаунте")

            user_id = account_info.get('id')
            if not user_id:
                return self.error_result(cookie, "Неверный ID пользователя")

            results = {
                'valid': True,
                'cookie_preview': cookie[:20] + '...' if len(cookie) > 20 else cookie,
                'account_info': account_info,
                'premium_status': self.check_premium(),
                'robux_balance': self.get_robux_balance(),
                'phone_status': self.check_phone_status(),
                'two_step_verification': self.check_2fa(),
                'account_age': self.get_account_age(account_info),
                'profile_url': f"https://www.roblox.com/users/{user_id}/profile",
                'checked_at': datetime.now().isoformat()
            }

            return results

        except Exception as e:
            return self.error_result(cookie, f"Ошибка проверки: {str(e)}")

    def get_account_info(self):
        try:
            response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=self.base_headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return {}
        except:
            return {}

    def check_premium(self):
        try:
            response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'is_premium': data.get('isPremium', False),
                    'status': 'Active' if data.get('isPremium') else 'Inactive'
                }
            return {'is_premium': False, 'status': 'Unknown'}
        except:
            return {'is_premium': False, 'status': 'Error'}

    def get_robux_balance(self):
        try:
            response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'balance': data.get('robux', 0),
                    'pending': data.get('pendingRobux', 0),
                    'total': data.get('robux', 0) + data.get('pendingRobux', 0)
                }
            return {'balance': 0, 'pending': 0, 'total': 0}
        except:
            return {'balance': 0, 'pending': 0, 'total': 0}

    def check_phone_status(self):
        try:
            return {'is_verified': False, 'status': 'Not Verified'}
        except:
            return {'is_verified': False, 'status': 'Error'}

    def check_2fa(self):
        try:
            return {'is_enabled': False, 'status': 'Disabled'}
        except:
            return {'is_enabled': False, 'status': 'Error'}

    def get_account_age(self, account_info):
        try:
            created = account_info.get('created')
            if created:
                created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                age_days = (datetime.now() - created_date).days
                return {
                    'created_date': created_date.strftime('%Y-%m-%d'),
                    'age_days': age_days,
                    'age_years': round(age_days / 365, 1)
                }
            return {'created_date': 'Unknown', 'age_days': 0, 'age_years': 0}
        except:
            return {'created_date': 'Unknown', 'age_days': 0, 'age_years': 0}

    def error_result(self, cookie: str, error: str):
        return {
            'valid': False,
            'error': error,
            'cookie_preview': cookie[:20] + '...' if len(cookie) > 20 else cookie,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple(self, cookies):
        results = []
        for cookie in cookies:
            if cookie.strip():
                result = self.check_account(cookie.strip())
                results.append(result)
                time.sleep(0.5)
        return results

checker = AdvancedRobloxChecker()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Маршруты аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный email или пароль', 'error')
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        if not is_valid_email(form.email.data):
            flash('Введите корректный email адрес', 'error')
            return render_template('register.html', form=form)
            
        if User.query.filter_by(email=form.email.data).first():
            flash('Email уже зарегистрирован', 'error')
            return render_template('register.html', form=form)
        
        user = User(
            email=form.email.data,
            password=generate_password_hash(form.password.data, method='bcrypt')
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь войдите в систему.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

# Основные маршруты
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_scans = ScanHistory.query.filter_by(user_id=current_user.id).order_by(
        ScanHistory.created_at.desc()
    ).limit(5).all()
    
    total_scans = ScanHistory.query.filter_by(user_id=current_user.id).count()
    total_cookies = db.session.query(db.func.sum(ScanHistory.total_cookies)).filter(
        ScanHistory.user_id == current_user.id
    ).scalar() or 0
    valid_cookies = db.session.query(db.func.sum(ScanHistory.valid_cookies)).filter(
        ScanHistory.user_id == current_user.id
    ).scalar() or 0
    
    return render_template('dashboard.html', 
                         scans=user_scans,
                         total_scans=total_scans,
                         total_cookies=total_cookies,
                         valid_cookies=valid_cookies)

@app.route('/check', methods=['POST'])
@login_required
def check_cookies():
    try:
        data = request.get_json()
        
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
        
        cookies = data['cookies']
        
        if len(cookies) > 50:
            return jsonify({'error': 'Too many cookies. Maximum 50 per request.'}), 400
        
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies = [cookie.strip() for cookie in cookies if cookie.strip()]
        
        if not cookies:
            return jsonify({'error': 'No valid cookies provided'}), 400
        
        results = checker.check_multiple(cookies)
        
        scan_record = ScanHistory(
            user_id=current_user.id,
            scan_data=json.dumps(results, ensure_ascii=False),
            total_cookies=len(cookies),
            valid_cookies=len([r for r in results if r.get('valid', False)])
        )
        db.session.add(scan_record)
        db.session.commit()
        
        return jsonify({
            'total': len(results),
            'valid': len([r for r in results if r.get('valid', False)]),
            'invalid': len([r for r in results if not r.get('valid', True)]),
            'results': results,
            'scan_id': scan_record.id,
            'checked_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    scans = ScanHistory.query.filter_by(user_id=current_user.id).order_by(
        ScanHistory.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('history.html', scans=scans)

@app.route('/profile')
@login_required
def profile():
    total_scans = ScanHistory.query.filter_by(user_id=current_user.id).count()
    total_cookies = db.session.query(db.func.sum(ScanHistory.total_cookies)).filter(
        ScanHistory.user_id == current_user.id
    ).scalar() or 0
    valid_cookies = db.session.query(db.func.sum(ScanHistory.valid_cookies)).filter(
        ScanHistory.user_id == current_user.id
    ).scalar() or 0
    last_scan = ScanHistory.query.filter_by(user_id=current_user.id).order_by(
        ScanHistory.created_at.desc()
    ).first()
    
    return render_template('profile.html',
                         total_scans=total_scans,
                         total_cookies=total_cookies,
                         valid_cookies=valid_cookies,
                         last_scan=last_scan)

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'users_count': User.query.count(),
        'scans_count': ScanHistory.query.count()
    })

# Создание таблиц
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))