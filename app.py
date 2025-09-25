from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from database import db, User, ScanHistory
from auth import auth
from checker import AdvancedRobloxChecker
import os
import json
import zipfile
import io
from datetime import datetime
from forms import LoginForm, RegisterForm, ResetPasswordForm
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
import smtplib
from email.mime.text import MimeText

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

# Регистрация blueprint
app.register_blueprint(auth)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

checker = AdvancedRobloxChecker()

def send_reset_email(user):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    token = serializer.dumps(user.email, salt='password-reset-salt')
    
    reset_url = url_for('reset_password_token', token=token, _external=True)
    
    msg = MimeText(f'''
    Для сброса пароля перейдите по ссылке:
    {reset_url}
    
    Если вы не запрашивали сброс пароля, проигнорируйте это письмо.
    ''')
    msg['Subject'] = 'Сброс пароля'
    msg['From'] = app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = user.email
    
    try:
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

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
    
    return render_template('dashboard.html', 
                         scans=user_scans,
                         total_scans=total_scans,
                         total_cookies=total_cookies)

@app.route('/check', methods=['POST'])
@login_required
def check_cookies():
    try:
        data = request.get_json()
        
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
        
        cookies = data['cookies']
        
        # Ограничение для безопасности
        if len(cookies) > 50:
            return jsonify({'error': 'Too many cookies. Maximum 50 per request.'}), 400
        
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies = [cookie.strip() for cookie in cookies if cookie.strip()]
        
        if not cookies:
            return jsonify({'error': 'No valid cookies provided'}), 400
        
        # Выполнение проверки
        results = checker.check_multiple(cookies)
        
        # Сохранение в историю
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

@app.route('/download/<int:scan_id>')
@login_required
def download_scan(scan_id):
    scan = ScanHistory.query.filter_by(id=scan_id, user_id=current_user.id).first_or_404()
    results = scan.get_scan_data()
    
    # Создание ZIP архива в памяти
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        # Сортировка по балансу
        valid_results = [r for r in results if r.get('valid')]
        
        # Баланс Robux
        sorted_by_balance = sorted(valid_results, 
                                 key=lambda x: x.get('robux_balance', {}).get('balance', 0), 
                                 reverse=True)
        balance_content = _format_results(sorted_by_balance, 'balance')
        zip_file.writestr('Сортировка по балансу.txt', balance_content.encode('utf-8'))
        
        # RAP (Recent Average Price)
        sorted_by_rap = sorted(valid_results, 
                             key=lambda x: x.get('rap', 0), 
                             reverse=True)
        rap_content = _format_results(sorted_by_rap, 'rap')
        zip_file.writestr('Сортировка по RAP.txt', rap_content.encode('utf-8'))
        
        # Total Donate
        sorted_by_donate = sorted(valid_results, 
                                key=lambda x: x.get('total_donate', 0), 
                                reverse=True)
        donate_content = _format_results(sorted_by_donate, 'donate')
        zip_file.writestr('Сортировка по total donate.txt', donate_content.encode('utf-8'))
        
        # Premium статус
        premium_first = sorted(valid_results, 
                             key=lambda x: x.get('premium_status', {}).get('is_premium', False), 
                             reverse=True)
        premium_content = _format_results(premium_first, 'premium')
        zip_file.writestr('Сортировка по Premium.txt', premium_content.encode('utf-8'))
        
        # Возраст аккаунта
        sorted_by_age = sorted(valid_results, 
                             key=lambda x: x.get('account_age', {}).get('age_days', 0), 
                             reverse=True)
        age_content = _format_results(sorted_by_age, 'age')
        zip_file.writestr('Сортировка по возрасту.txt', age_content.encode('utf-8'))
        
        # Все валидные куки
        all_valid_content = _format_results(valid_results, 'all')
        zip_file.writestr('Все валидные куки.txt', all_valid_content.encode('utf-8'))
        
        # JSON файл со всеми данными
        zip_file.writestr('полные_данные.json', json.dumps(results, ensure_ascii=False, indent=2).encode('utf-8'))
    
    zip_buffer.seek(0)
    
    filename = f"scan_results_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(zip_buffer, 
                     as_attachment=True, 
                     download_name=filename,
                     mimetype='application/zip')

def _format_results(results, sort_type):
    """Форматирование результатов для текстовых файлов"""
    content = f"Результаты проверки - Сортировка по {sort_type}\n"
    content += "=" * 50 + "\n\n"
    
    for i, result in enumerate(results, 1):
        if result.get('valid'):
            content += f"Аккаунт #{i}\n"
            content += f"Имя: {result.get('account_info', {}).get('name', 'N/A')}\n"
            content += f"ID: {result.get('account_info', {}).get('id', 'N/A')}\n"
            content += f"Ссылка: https://www.roblox.com/users/{result.get('account_info', {}).get('id', '')}/profile\n"
            content += f"Баланс Robux: {result.get('robux_balance', {}).get('balance', 0):,}\n"
            content += f"Pending Robux: {result.get('robux_balance', {}).get('pending', 0):,}\n"
            content += f"RAP: {result.get('rap', 0):,}\n"
            content += f"Total Donate: {result.get('total_donate', 0):,}\n"
            content += f"Premium: {'Да' if result.get('premium_status', {}).get('is_premium') else 'Нет'}\n"
            content += f"2FA: {'Вкл' if result.get('two_step_verification', {}).get('is_enabled') else 'Выкл'}\n"
            content += f"Телефон: {'Привязан' if result.get('phone_status', {}).get('is_verified') else 'Не привязан'}\n"
            content += f"Карта: {'Привязана' if result.get('billing', {}).get('has_card') else 'Не привязана'}\n"
            content += f"Возраст: {result.get('account_age', {}).get('age_days', 0)} дней\n"
            content += f"Дата создания: {result.get('account_age', {}).get('created_date', 'N/A')}\n"
            content += f"Pending Group Robux: {result.get('group_robux', {}).get('pending', 0):,}\n"
            content += "-" * 50 + "\n\n"
    
    return content

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if send_reset_email(user):
                flash('Письмо с инструкциями по сбросу пароля отправлено на вашу почту.', 'info')
            else:
                flash('Ошибка при отправке письма. Попробуйте позже.', 'error')
        else:
            flash('Аккаунт с такой почтой не найден.', 'error')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    try:
        serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('Неверная или устаревшая ссылка для сброса пароля.', 'error')
        return redirect(url_for('reset_password'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Аккаунт не найден.', 'error')
        return redirect(url_for('reset_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Пароли не совпадают.', 'error')
        elif len(new_password) < 6:
            flash('Пароль должен содержать минимум 6 символов.', 'error')
        else:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash('Пароль успешно изменен. Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
    
    return render_template('reset_password_token.html', token=token)

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'users_count': User.query.count(),
        'scans_count': ScanHistory.query.count()
    })

# Создание таблиц при первом запуске
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))