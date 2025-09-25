import requests
import json
import time
from datetime import datetime, timedelta  # Добавить timedelta
from typing import Dict, List, Any

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
            'X-CSRF-TOKEN': self.get_csrf_token(cookie)
        }

    def get_csrf_token(self, cookie: str) -> str:
        try:
            response = self.session.post(
                'https://auth.roblox.com/v2/login',
                headers={'Cookie': f'.ROBLOSECURITY={cookie}'},
                timeout=5
            )
            return response.headers.get('x-csrf-token', '')
        except:
            return ''

    def check_account(self, cookie: str) -> Dict[str, Any]:
        """Полная проверка аккаунта на основе MeowTool"""
        self.set_cookie(cookie)
        
        try:
            # Основная проверка аутентификации
            account_info = self.get_account_info()
            if not account_info:
                return self.error_result(cookie, "Не удалось получить информацию об аккаунте")

            user_id = account_info.get('id')
            if not user_id:
                return self.error_result(cookie, "Неверный ID пользователя")

            # Выполняем все проверки параллельно
            results = {
                'valid': True,
                'cookie_preview': cookie[:20] + '...' if len(cookie) > 20 else cookie,
                'account_info': account_info,
                'premium_status': self.check_premium(),
                'robux_balance': self.get_robux_balance(),
                'billing_info': self.get_billing_info(),
                'phone_status': self.check_phone_status(),
                'two_step_verification': self.check_2fa(),
                'account_age': self.get_account_age(account_info),
                'pending_robux': self.get_pending_robux(),
                'rap_value': self.get_rap_value(user_id),
                'group_earnings': self.get_group_earnings(user_id),
                'total_spent': self.get_total_spent(user_id),
                'ban_status': self.check_ban_status(),
                'email_verified': self.check_email_verified(),
                'profile_info': self.get_profile_info(user_id),
                'friends_count': self.get_friends_count(user_id),
                'followers_count': self.get_followers_count(user_id),
                'following_count': self.get_following_count(user_id),
                'profile_url': f"https://www.roblox.com/users/{user_id}/profile",
                'security_analysis': self.analyze_security(cookie, account_info),
                'account_value': self.calculate_account_value(user_id),
                'checked_at': datetime.now().isoformat()
            }

            return results

        except Exception as e:
            return self.error_result(cookie, f"Ошибка проверки: {str(e)}")

    def get_account_info(self) -> Dict[str, Any]:
        """Получение основной информации об аккаунте"""
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

    def check_premium(self) -> Dict[str, Any]:
        """Проверка Premium статуса"""
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
                    'since': data.get('createdDate'),
                    'status': 'Active' if data.get('isPremium') else 'Inactive',
                    'type': data.get('membershipType', 'None')
                }
            return {'is_premium': False, 'status': 'Unknown'}
        except:
            return {'is_premium': False, 'status': 'Error'}

    def get_robux_balance(self) -> Dict[str, Any]:
        """Получение баланса Robux (баланс + pending)"""
        try:
            response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                balance = data.get('robux', 0)
                pending = data.get('pendingRobux', 0)
                return {
                    'balance': balance,
                    'pending': pending,
                    'total': balance + pending,
                    'available': balance
                }
            return {'balance': 0, 'pending': 0, 'total': 0, 'available': 0}
        except:
            return {'balance': 0, 'pending': 0, 'total': 0, 'available': 0}

    def get_billing_info(self) -> Dict[str, Any]:
        """Информация о биллинге и картах"""
        try:
            response = self.session.get(
                'https://billing.roblox.com/v1/paymentmethods',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                credit_cards = [m for m in data.get('data', []) if m.get('type') == 'CreditCard']
                paypal = [m for m in data.get('data', []) if m.get('type') == 'PayPal']
                
                return {
                    'has_payment_methods': len(data.get('data', [])) > 0,
                    'payment_methods_count': len(data.get('data', [])),
                    'credit_cards_count': len(credit_cards),
                    'paypal_linked': len(paypal) > 0,
                    'total_methods': len(credit_cards) + len(paypal)
                }
            return {'has_payment_methods': False, 'payment_methods_count': 0}
        except:
            return {'has_payment_methods': False, 'payment_methods_count': 0}

    def check_phone_status(self) -> Dict[str, Any]:
        """Проверка привязки телефона"""
        try:
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/account/phone',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'is_verified': data.get('isVerified', False),
                    'phone_number': data.get('phoneNumber', ''),
                    'country_code': data.get('countryCode', ''),
                    'status': 'Verified' if data.get('isVerified') else 'Not Verified'
                }
            return {'is_verified': False, 'status': 'Unknown'}
        except:
            return {'is_verified': False, 'status': 'Error'}

    def check_2fa(self) -> Dict[str, Any]:
        """Проверка двухфакторной аутентификации"""
        try:
            response = self.session.get(
                'https://auth.roblox.com/v2/account/settings',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'is_enabled': data.get('isTwoStepVerificationEnabled', False),
                    'type': data.get('twoStepVerificationType', 'None'),
                    'status': 'Enabled' if data.get('isTwoStepVerificationEnabled') else 'Disabled',
                    'email_verified': data.get('isEmailVerified', False)
                }
            return {'is_enabled': False, 'status': 'Unknown'}
        except:
            return {'is_enabled': False, 'status': 'Error'}

    def get_account_age(self, account_info: Dict) -> Dict[str, Any]:
        """Возраст аккаунта и дата создания"""
        try:
            created = account_info.get('created')
            if created:
                created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                age_days = (datetime.now() - created_date).days
                age_years = age_days / 365.25
                
                return {
                    'created_date': created_date.strftime('%Y-%m-%d'),
                    'created_datetime': created_date.isoformat(),
                    'age_days': age_days,
                    'age_years': round(age_years, 2),
                    'age_category': 'Old' if age_days > 365 else 'New' if age_days < 30 else 'Medium'
                }
            return {'created_date': 'Unknown', 'age_days': 0, 'age_years': 0}
        except:
            return {'created_date': 'Unknown', 'age_days': 0, 'age_years': 0}

    def get_pending_robux(self) -> Dict[str, Any]:
        """Детальная информация о pending Robux"""
        try:
            # Получаем из баланса
            robux_data = self.get_robux_balance()
            pending = robux_data.get('pending', 0)
            
            # Дополнительная информация о pending
            return {
                'pending_amount': pending,
                'available_in': '3-5 days' if pending > 0 else 'None',
                'est_available_date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d') if pending > 0 else 'N/A',
                'sources': ['Sales', 'Group Payouts', 'Affiliate'] if pending > 0 else []
            }
        except:
            return {'pending_amount': 0, 'available_in': 'Unknown'}

    def get_rap_value(self, user_id: int) -> Dict[str, Any]:
        """Примерная стоимость инвентаря (RAP)"""
        try:
            # Упрощенная реализация RAP проверки
            response = self.session.get(
                f'https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?limit=10',
                headers=self.base_headers,
                timeout=10
            )
            
            estimated_rap = 0
            items_count = 0
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('data', [])
                items_count = len(items)
                
                # Примерная оценка RAP (упрощенно)
                for item in items:
                    # Базовая оценка based on asset type
                    estimated_rap += 100  # Базовая стоимость
                    
            return {
                'estimated_rap': estimated_rap,
                'items_count': items_count,
                'rap_per_item': round(estimated_rap / max(items_count, 1), 2),
                'value_category': 'High' if estimated_rap > 10000 else 'Medium' if estimated_rap > 1000 else 'Low'
            }
        except:
            return {'estimated_rap': 0, 'items_count': 0, 'rap_per_item': 0}

    def get_group_earnings(self, user_id: int) -> Dict[str, Any]:
        """Заработок в группах"""
        try:
            response = self.session.get(
                f'https://groups.roblox.com/v1/users/{user_id}/groups/roles',
                headers=self.base_headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                groups = data.get('data', [])
                
                total_earnings = 0
                group_count = len(groups)
                
                # Проверяем группы где пользователь может получать доход
                premium_groups = [g for g in groups if g.get('role', {}).get('rank', 0) >= 100]
                
                return {
                    'total_groups': group_count,
                    'premium_groups': len(premium_groups),
                    'estimated_earnings': total_earnings,
                    'has_group_earnings': len(premium_groups) > 0
                }
            return {'total_groups': 0, 'premium_groups': 0, 'estimated_earnings': 0}
        except:
            return {'total_groups': 0, 'premium_groups': 0, 'estimated_earnings': 0}

    def get_total_spent(self, user_id: int) -> Dict[str, Any]:
        """Общая сумма потраченного (оценка)"""
        try:
            # Оценка based on аккаунт возраст и Premium статус
            account_age = self.get_account_age(self.get_account_info())
            premium_status = self.check_premium()
            
            age_days = account_age.get('age_days', 0)
            is_premium = premium_status.get('is_premium', False)
            
            # Базовая формула оценки
            base_spent = age_days * 10  # Предполагаем 10 Robux в день
            premium_bonus = 1000 if is_premium else 0
            
            estimated_total = base_spent + premium_bonus
            
            return {
                'estimated_total_spent': estimated_total,
                'premium_spent': premium_bonus,
                'daily_average': round(estimated_total / max(age_days, 1), 2),
                'spending_category': 'High' if estimated_total > 10000 else 'Medium' if estimated_total > 1000 else 'Low'
            }
        except:
            return {'estimated_total_spent': 0, 'premium_spent': 0, 'daily_average': 0}

    def check_ban_status(self) -> Dict[str, Any]:
        """Проверка статуса бана"""
        try:
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/account-status',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'is_banned': data.get('isBanned', False),
                    'ban_reason': data.get('banReason', 'None'),
                    'ban_status': 'Banned' if data.get('isBanned') else 'Active',
                    'moderation_status': data.get('moderationStatus', 'Clear')
                }
            return {'is_banned': False, 'ban_status': 'Unknown'}
        except:
            return {'is_banned': False, 'ban_status': 'Error'}

    def check_email_verified(self) -> Dict[str, Any]:
        """Проверка верификации email"""
        try:
            response = self.session.get(
                'https://accountsettings.roblox.com/v1/email',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'is_verified': data.get('verified', False),
                    'email_address': data.get('emailAddress', ''),
                    'status': 'Verified' if data.get('verified') else 'Not Verified'
                }
            return {'is_verified': False, 'status': 'Unknown'}
        except:
            return {'is_verified': False, 'status': 'Error'}

    def get_profile_info(self, user_id: int) -> Dict[str, Any]:
        """Информация о профиле"""
        try:
            response = self.session.get(
                f'https://users.roblox.com/v1/users/{user_id}',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'display_name': data.get('displayName', ''),
                    'description': data.get('description', ''),
                    'is_verified': data.get('hasVerifiedBadge', False),
                    'created': data.get('created', ''),
                    'profile_visibility': data.get('profileVisibility', 'Public')
                }
            return {}
        except:
            return {}

    def get_friends_count(self, user_id: int) -> int:
        """Количество друзей"""
        try:
            response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/friends/count',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get('count', 0)
            return 0
        except:
            return 0

    def get_followers_count(self, user_id: int) -> int:
        """Количество подписчиков"""
        try:
            response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/followers/count',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get('count', 0)
            return 0
        except:
            return 0

    def get_following_count(self, user_id: int) -> int:
        """Количество подписок"""
        try:
            response = self.session.get(
                f'https://friends.roblox.com/v1/users/{user_id}/followings/count',
                headers=self.base_headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get('count', 0)
            return 0
        except:
            return 0

    def analyze_security(self, cookie: str, account_info: Dict) -> Dict[str, Any]:
        """Расширенный анализ безопасности аккаунта"""
        security_score = 0
        max_score = 100
        recommendations = []
        
        # Проверка 2FA (+30 баллов)
        two_fa = self.check_2fa()
        if two_fa.get('is_enabled'):
            security_score += 30
        else:
            recommendations.append("Включите двухфакторную аутентификацию")
        
        # Проверка телефона (+20 баллов)
        phone = self.check_phone_status()
        if phone.get('is_verified'):
            security_score += 20
        else:
            recommendations.append("Привяжите номер телефона")
        
        # Проверка email (+10 баллов)
        email = self.check_email_verified()
        if email.get('is_verified'):
            security_score += 10
        else:
            recommendations.append("Подтвердите email адрес")
        
        # Возраст аккаунта (+15 баллов за старый аккаунт)
        age = self.get_account_age(account_info)
        if age.get('age_days', 0) > 365:
            security_score += 15
        elif age.get('age_days', 0) < 30:
            security_score -= 10
            recommendations.append("Аккаунт новый - будьте осторожны")
        
        # Premium статус (+10 баллов)
        premium = self.check_premium()
        if premium.get('is_premium'):
            security_score += 10
        
        # Билллинг информация (+5 баллов)
        billing = self.get_billing_info()
        if billing.get('has_payment_methods'):
            security_score += 5
        
        # Длина куки (+5 баллов)
        if len(cookie) > 100:
            security_score += 5
        
        # Статус бана (-20 баллов за бан)
        ban_status = self.check_ban_status()
        if ban_status.get('is_banned'):
            security_score -= 20
            recommendations.append("Аккаунт забанен - высокий риск")
        
        # Ограничение score в пределах 0-100
        security_score = max(0, min(100, security_score))
        
        return {
            'security_score': security_score,
            'max_score': max_score,
            'security_level': self.get_security_level(security_score),
            'recommendations': recommendations if recommendations else ["Аккаунт хорошо защищен"],
            'risk_factor': self.get_risk_factor(security_score),
            'improvement_tips': self.get_improvement_tips(security_score)
        }

    def get_security_level(self, score: int) -> str:
        if score >= 80: return "Очень высокий"
        elif score >= 60: return "Высокий"
        elif score >= 40: return "Средний"
        elif score >= 20: return "Низкий"
        else: return "Очень низкий"

    def get_risk_factor(self, score: int) -> str:
        if score >= 70: return "Низкий"
        elif score >= 40: return "Средний"
        else: return "Высокий"

    def get_improvement_tips(self, score: int) -> List[str]:
        tips = []
        if score < 80:
            tips.append("Включите 2FA для максимальной защиты")
        if score < 60:
            tips.append("Привяжите телефон и email")
        if score < 40:
            tips.append("Рассмотрите Premium подписку")
        return tips

    def calculate_account_value(self, user_id: int) -> Dict[str, Any]:
        """Оценка общей стоимости аккаунта"""
        try:
            robux_data = self.get_robux_balance()
            rap_data = self.get_rap_value(user_id)
            premium_status = self.check_premium()
            
            # Базовая оценка стоимости
            robux_value = robux_data.get('balance', 0) * 0.0035  # Примерная стоимость Robux
            rap_value = rap_data.get('estimated_rap', 0) * 0.002  # Примерная стоимость RAP
            premium_value = 50 if premium_status.get('is_premium') else 0
            
            total_value = robux_value + rap_value + premium_value
            
            return {
                'total_value_usd': round(total_value, 2),
                'robux_value': round(robux_value, 2),
                'rap_value': round(rap_value, 2),
                'premium_value': premium_value,
                'value_category': 'High' if total_value > 100 else 'Medium' if total_value > 20 else 'Low'
            }
        except:
            return {'total_value_usd': 0, 'robux_value': 0, 'rap_value': 0, 'premium_value': 0}

    def error_result(self, cookie: str, error: str) -> Dict[str, Any]:
        return {
            'valid': False,
            'error': error,
            'cookie_preview': cookie[:20] + '...' if len(cookie) > 20 else cookie,
            'checked_at': datetime.now().isoformat()
        }

    def check_multiple(self, cookies: List[str]) -> List[Dict[str, Any]]:
        """Проверка нескольких куки"""
        results = []
        for i, cookie in enumerate(cookies):
            if cookie.strip():
                print(f"Checking cookie {i+1}/{len(cookies)}...")
                result = self.check_account(cookie.strip())
                results.append(result)
                time.sleep(0.5)  # Задержка для избежания блокировки
        return results