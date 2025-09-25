import requests
import json
from datetime import datetime
import time

class AdvancedRobloxChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def check_cookie(self, cookie):
        """Проверка одной куки"""
        try:
            # Очистка куки
            cookie = cookie.strip()
            if '.ROBLOSECURITY=' in cookie:
                cookie = cookie.split('.ROBLOSECURITY=')[1].split(';')[0].strip()
            
            # Установка куки для сессии
            self.session.cookies.set('.ROBLOSECURITY', cookie)
            
            # Получение информации об аккаунте
            account_info = self._get_account_info()
            if not account_info:
                return self._create_invalid_result(cookie, "Invalid cookie")
            
            # Получение дополнительных данных
            robux_balance = self._get_robux_balance()
            premium_status = self._get_premium_status()
            two_step_verification = self._get_2fa_status()
            phone_status = self._get_phone_status()
            account_age = self._get_account_age(account_info)
            billing_info = self._get_billing_info()
            rap = self._get_rap(account_info['id'])
            group_robux = self._get_group_robux()
            total_donate = self._get_total_donate(account_info['id'])
            
            return {
                'valid': True,
                'cookie_preview': f"{cookie[:15]}...{cookie[-15:]}" if len(cookie) > 30 else cookie,
                'account_info': account_info,
                'robux_balance': robux_balance,
                'premium_status': premium_status,
                'two_step_verification': two_step_verification,
                'phone_status': phone_status,
                'account_age': account_age,
                'billing': billing_info,
                'rap': rap,
                'group_robux': group_robux,
                'total_donate': total_donate,
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return self._create_invalid_result(cookie, str(e))
    
    def check_multiple(self, cookies):
        """Проверка нескольких куки"""
        results = []
        for cookie in cookies:
            result = self.check_cookie(cookie)
            results.append(result)
            time.sleep(0.5)  # Задержка между запросами
        return results
    
    def _get_account_info(self):
        """Получение основной информации об аккаунте"""
        try:
            response = self.session.get('https://www.roblox.com/mobileapi/userinfo')
            if response.status_code == 200:
                data = response.json()
                return {
                    'id': data.get('UserID'),
                    'name': data.get('UserName'),
                    'display_name': data.get('DisplayName'),
                    'robux': data.get('RobuxBalance', 0)
                }
        except:
            pass
        return None
    
    def _get_robux_balance(self):
        """Получение баланса Robux"""
        try:
            response = self.session.get('https://economy.roblox.com/v1/user/currency')
            if response.status_code == 200:
                data = response.json()
                return {
                    'balance': data.get('robux', 0),
                    'pending': 0  # Нужен дополнительный запрос
                }
        except:
            pass
        return {'balance': 0, 'pending': 0}
    
    def _get_premium_status(self):
        """Проверка Premium статуса"""
        try:
            response = self.session.get('https://www.roblox.com/mobileapi/userinfo')
            if response.status_code == 200:
                data = response.json()
                return {'is_premium': data.get('IsPremium', False)}
        except:
            pass
        return {'is_premium': False}
    
    def _get_2fa_status(self):
        """Проверка 2FA"""
        try:
            response = self.session.get('https://www.roblox.com/account/settings')
            if response.status_code == 200:
                # Простая проверка наличия 2FA в HTML
                return {'is_enabled': 'TwoStepVerification' in response.text}
        except:
            pass
        return {'is_enabled': False}
    
    def _get_phone_status(self):
        """Проверка привязки телефона"""
        try:
            response = self.session.get('https://www.roblox.com/account/settings')
            if response.status_code == 200:
                return {'is_verified': 'PhoneNumber' in response.text}
        except:
            pass
        return {'is_verified': False}
    
    def _get_account_age(self, account_info):
        """Получение возраста аккаунта"""
        try:
            if account_info and 'id' in account_info:
                response = self.session.get(f'https://users.roblox.com/v1/users/{account_info["id"]}')
                if response.status_code == 200:
                    data = response.json()
                    created = datetime.fromisoformat(data['created'].replace('Z', '+00:00'))
                    age_days = (datetime.now() - created).days
                    return {
                        'created_date': created.strftime('%Y-%m-%d'),
                        'age_days': age_days
                    }
        except:
            pass
        return {'created_date': 'N/A', 'age_days': 0}
    
    def _get_billing_info(self):
        """Получение информации о платежных данных"""
        try:
            response = self.session.get('https://billing.roblox.com/v1/paymentmethods')
            if response.status_code == 200:
                data = response.json()
                return {'has_card': len(data.get('data', [])) > 0}
        except:
            pass
        return {'has_card': False}
    
    def _get_rap(self, user_id):
        """Получение RAP (Recent Average Price)"""
        try:
            if user_id:
                response = self.session.get(f'https://api.roblox.com/users/{user_id}/assets')
                if response.status_code == 200:
                    assets = response.json()
                    rap = sum(asset.get('rap', 0) for asset in assets)
                    return rap
        except:
            pass
        return 0
    
    def _get_group_robux(self):
        """Получение групповых Robux"""
        try:
            response = self.session.get('https://groups.roblox.com/v1/groups/group-id/currency')
            # Нужна доработка для получения групповых Robux
            return {'pending': 0, 'balance': 0}
        except:
            return {'pending': 0, 'balance': 0}
    
    def _get_total_donate(self, user_id):
        """Получение общей суммы донатов"""
        # Упрощенная реализация - нужно доработать
        return 0
    
    def _create_invalid_result(self, cookie, error):
        """Создание результата для невалидной куки"""
        return {
            'valid': False,
            'cookie_preview': f"{cookie[:15]}...{cookie[-15:]}" if len(cookie) > 30 else cookie,
            'error': error,
            'checked_at': datetime.now().isoformat()
        }