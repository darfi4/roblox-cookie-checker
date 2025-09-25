from flask import Flask, render_template, request, jsonify, send_file
from flask_login import LoginManager, login_required, current_user
from database import db, User, ScanHistory
from auth import auth
from checker import AdvancedRobloxChecker
import os
import json
import zipfile
import io
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

app.register_blueprint(auth)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

checker = AdvancedRobloxChecker()

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

@app.route('/download/<int:scan_id>')
@login_required
def download_scan(scan_id):
    scan = ScanHistory.query.filter_by(id=scan_id, user_id=current_user.id).first_or_404()
    results = scan.get_scan_data()
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        valid_results = [r for r in results if r.get('valid')]
        
        sorted_by_balance = sorted(valid_results, 
                                 key=lambda x: x.get('robux_balance', {}).get('balance', 0), 
                                 reverse=True)
        balance_content = format_results(sorted_by_balance, 'балансу')
        zip_file.writestr('Сортировка по балансу.txt', balance_content.encode('utf-8'))
        
        premium_first = sorted(valid_results, 
                             key=lambda x: x.get('premium_status', {}).get('is_premium', False), 
                             reverse=True)
        premium_content = format_results(premium_first, 'Premium статусу')
        zip_file.writestr('Сортировка по Premium.txt', premium_content.encode('utf-8'))
        
        sorted_by_security = sorted(valid_results, 
                                  key=lambda x: x.get('security_analysis', {}).get('security_score', 0), 
                                  reverse=True)
        security_content = format_results(sorted_by_security, 'безопасности')
        zip_file.writestr('Сортировка по безопасности.txt', security_content.encode('utf-8'))
        
        sorted_by_age = sorted(valid_results, 
                             key=lambda x: x.get('account_age', {}).get('age_days', 0), 
                             reverse=True)
        age_content = format_results(sorted_by_age, 'возрасту аккаунта')
        zip_file.writestr('Сортировка по возрасту.txt', age_content.encode('utf-8'))
        
        all_valid_content = format_results(valid_results, 'всем параметрам')
        zip_file.writestr('Все валидные куки.txt', all_valid_content.encode('utf-8'))
        
        zip_file.writestr('полные_данные.json', json.dumps(results, ensure_ascii=False, indent=2).encode('utf-8'))
    
    zip_buffer.seek(0)
    
    filename = f"scan_results_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(zip_buffer, 
                     as_attachment=True, 
                     download_name=filename,
                     mimetype='application/zip')

def format_results(results, sort_type):
    content = f"Результаты проверки - Сортировка по {sort_type}\n"
    content += "=" * 50 + "\n\n"
    
    for i, result in enumerate(results, 1):
        if result.get('valid'):
            content += f"Аккаунт #{i}\n"
            content += f"Имя: {result.get('account_info', {}).get('name', 'N/A')}\n"
            content += f"ID: {result.get('account_info', {}).get('id', 'N/A')}\n"
            content += f"Баланс Robux: {result.get('robux_balance', {}).get('balance', 0):,}\n"
            content += f"Pending Robux: {result.get('robux_balance', {}).get('pending', 0):,}\n"
            content += f"Premium: {'Да' if result.get('premium_status', {}).get('is_premium') else 'Нет'}\n"
            content += f"2FA: {'Вкл' if result.get('two_step_verification', {}).get('is_enabled') else 'Выкл'}\n"
            content += f"Телефон: {'Привязан' if result.get('phone_status', {}).get('is_verified') else 'Не привязан'}\n"
            content += f"Возраст: {result.get('account_age', {}).get('age_days', 0)} дней\n"
            content += f"Безопасность: {result.get('security_analysis', {}).get('security_score', 0)}/100\n"
            content += f"Карты: {'Есть' if result.get('billing_info', {}).get('has_payment_methods') else 'Нет'}\n"
            content += f"Кука: {result.get('cookie_preview', 'N/A')}\n"
            content += "-" * 40 + "\n"
    
    return content

@app.route('/profile')
@login_required
def profile():
    # Получаем статистику для профиля
    total_scans = ScanHistory.query.filter_by(user_id=current_user.id).count()
    total_cookies = db.session.query(db.func.sum(ScanHistory.total_cookies)).filter(
        ScanHistory.user_id == current_user.id
    ).scalar() or 0
    last_scan = ScanHistory.query.filter_by(user_id=current_user.id).order_by(
        ScanHistory.created_at.desc()
    ).first()
    
    return render_template('profile.html',
                         total_scans=total_scans,
                         total_cookies=total_cookies,
                         last_scan=last_scan)

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'users_count': User.query.count(),
        'scans_count': ScanHistory.query.count()
    })

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))