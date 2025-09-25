from flask import Flask, render_template, request, jsonify
import os
import requests
import time
from datetime import datetime
import json

app = Flask(__name__)

class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
    
    def check_cookie(self, cookie):
        """Расширенная проверка куки с множеством проверок"""
        try:
            headers = self.session.headers.copy()
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'
            
            # Основная проверка аутентификации
            auth_response = self.session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=10
            )
            
            if auth_response.status_code != 200:
                return self.get_error_result(cookie, f'Auth failed: HTTP {auth_response.status_code}')
            
            user_data = auth_response.json()
            user_id = user_data.get('id')
            
            # Параллельные проверки
            robux_data = self.get_robux_balance(headers)
            premium_data = self.check_premium(headers)
            account_age = self.get_account_age(headers, user_id)
            ban_status = self.check_ban_status(headers)
            friends_count = self.get_friends_count(headers, user_id)
            profile_data = self.get_profile_info(headers, user_id)
            
            return {
                'valid': True,
                'username': user_data.get('name', 'N/A'),
                'user_id': user_id,
                'display_name': user_data.get('displayName', 'N/A'),
                'robux': robux_data.get('balance', 0),
                'premium': premium_data.get('is_premium', False),
                'premium_since': premium_data.get('since'),
                'created_date': account_age.get('created'),
                'account_age_days': account_age.get('age_days'),
                'ban_status': ban_status.get('status', 'Unknown'),
                'last_ban_reason': ban_status.get('reason'),
                'friends_count': friends_count,
                'profile_visibility': profile_data.get('visibility', 'Unknown'),
                'is_verified': profile_data.get('is_verified', False),
                'cookie': cookie[:20] + '...' if len(cookie) > 20 else cookie,
                'security_analysis': self.analyze_security(cookie, user_data),
                'last_checked': datetime.now().isoformat()
            }
            
        except Exception as e:
            return self.get_error_result(cookie, str(e))
    
    def get_robux_balance(self, headers):
        """Получение баланса Robux"""
        try:
            response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                return {'balance': response.json().get('robux', 0)}
            return {'balance': 0}
        except:
            return {'balance': 0}
    
    def check_premium(self, headers):
        """Проверка Premium статуса"""
        try:
            response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'is_premium': data.get('isPremium', False),
                    'since': data.get('createdDate')
                }
            return {'is_premium': False}
        except:
            return {'is_premium': False}
    
    def get_account_age(self, headers, user_id):
        """Получение даты создания аккаунта"""
        try:
            response = self.session.get(
                f'https://users.roblox.com/v1/users/{user_id}',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                created = data.get('created')
                if created:
                    created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    age_days = (datetime.now() - created_date).days
                    return {
                        'created': created_date.strftime('%Y-%m-%d'),
                        'age_days': age_days
                    }
            return {'created': 'N/A', 'age_days': 0}
        except:
            return {'created': 'N/A', 'age_days': 0}
    
    def check_ban_status(self, headers):
        """Проверка статуса бана"""
        try:
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/account-status',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'Banned' if data.get('isBanned') else 'Active',
                    'reason': data.get('banReason', 'N/A')
                }
            return {'status': 'Unknown'}
        except:
            return {'status': 'Unknown'}
    
    def get_friends_count(self, headers, user_id):
        """Получение количества друзей"""
        try:
            response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get('count', 0)
            return 0
        except:
            return 0
    
    def get_profile_info(self, headers, user_id):
        """Получение информации о профиле"""
        try:
            response = self.session.get(
                f'https://users.roblox.com/v1/users/{user_id}',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'visibility': data.get('profileVisibility', 'Unknown'),
                    'is_verified': data.get('hasVerifiedBadge', False)
                }
            return {}
        except:
            return {}
    
    def analyze_security(self, cookie, user_data):
        """Анализ безопасности аккаунта"""
        analysis = {
            'cookie_length': len(cookie),
            'has_2fa': self.check_2fa(cookie),
            'account_age_score': 0,
            'premium_status': False,
            'verification_status': False
        }
        
        # Простой анализ безопасности
        if analysis['cookie_length'] > 100:
            analysis['cookie_strength'] = 'Strong'
        else:
            analysis['cookie_strength'] = 'Weak'
        
        return analysis
    
    def check_2fa(self, cookie):
        """Проверка наличия 2FA (упрощенная)"""
        try:
            headers = self.session.headers.copy()
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'
            
            response = self.session.get(
                'https://auth.roblox.com/v2/account/settings',
                headers=headers,
                timeout=5
            )
            # Упрощенная проверка - если доступны настройки, считаем что кука валидна
            return response.status_code == 200
        except:
            return False
    
    def get_error_result(self, cookie, error):
        """Форматирование результата ошибки"""
        return {
            'valid': False,
            'error': error,
            'cookie': cookie[:20] + '...' if len(cookie) > 20 else cookie,
            'last_checked': datetime.now().isoformat()
        }
    
    def check_multiple(self, cookies_list):
        """Проверка нескольких куки"""
        results = []
        for cookie in cookies_list:
            if cookie.strip():
                result = self.check_cookie(cookie.strip())
                results.append(result)
                time.sleep(0.3)  # Задержка чтобы не получить блокировку
        return results

# Инициализация проверщика
checker = AdvancedRobloxChecker()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_cookies():
    try:
        data = request.get_json()
        
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
        
        cookies = data['cookies']
        
        # Ограничение для безопасности
        if len(cookies) > 20:
            return jsonify({'error': 'Too many cookies. Maximum 20 per request.'}), 400
        
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies = [cookie.strip() for cookie in cookies if cookie.strip()]
        
        if not cookies:
            return jsonify({'error': 'No valid cookies provided'}), 400
        
        results = checker.check_multiple(cookies)
        
        return jsonify({
            'total': len(results),
            'valid': len([r for r in results if r['valid']]),
            'invalid': len([r for r in results if not r['valid']]),
            'results': results,
            'checked_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'service': 'Roblox Cookie Checker Pro'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))