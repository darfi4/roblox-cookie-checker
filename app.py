import os
import json
import zipfile
import io
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
import requests
import time
import re
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from threading import Timer
import asyncio
import aiohttp
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['DATABASE'] = 'checker_history.db'

# Активные пользователи (сессии)
active_sessions = {}
session_lock = threading.Lock()
SESSION_TIMEOUT = 300  # 5 минут

def cleanup_sessions():
    with session_lock:
        current_time = time.time()
        expired_sessions = []
        for session_id, session_data in active_sessions.items():
            if current_time - session_data['last_active'] > SESSION_TIMEOUT:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del active_sessions[session_id]
    
    Timer(60, cleanup_sessions).start()

cleanup_sessions()

def init_db():
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                user_id TEXT,
                total_cookies INTEGER,
                valid_cookies INTEGER,
                check_date TEXT,
                results TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS global_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_checked INTEGER DEFAULT 0,
                valid_accounts INTEGER DEFAULT 0,
                last_updated TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

init_db()

def update_global_stats(total_checked=0, valid_accounts=0):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        c.execute('SELECT * FROM global_stats WHERE id = 1')
        existing = c.fetchone()
        
        if existing:
            c.execute('''
                UPDATE global_stats SET 
                total_checked = total_checked + ?,
                valid_accounts = valid_accounts + ?,
                last_updated = ?
                WHERE id = 1
            ''', (total_checked, valid_accounts, now))
        else:
            c.execute('''
                INSERT INTO global_stats (total_checked, valid_accounts, last_updated)
                VALUES (?, ?, ?)
            ''', (total_checked, valid_accounts, now))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating global stats: {e}")

def get_global_stats():
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT * FROM global_stats WHERE id = 1')
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'total_checked': result[1],
                'valid_accounts': result[2],
                'last_updated': result[3]
            }
        return {'total_checked': 0, 'valid_accounts': 0, 'last_updated': datetime.now().isoformat()}
    except Exception as e:
        return {'total_checked': 0, 'valid_accounts': 0, 'last_updated': datetime.now().isoformat()}

def get_active_users_count():
    with session_lock:
        current_time = time.time()
        active_count = 0
        for session_id, session_data in active_sessions.items():
            if current_time - session_data['last_active'] <= SESSION_TIMEOUT:
                active_count += 1
        return active_count

def update_user_session(session_id, user_data=None):
    with session_lock:
        active_sessions[session_id] = {
            'last_active': time.time(),
            'user_data': user_data or {},
            'created': active_sessions.get(session_id, {}).get('created', time.time())
        }

def get_user_id():
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        unique_string = f"{ip}-{user_agent}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    except:
        return str(uuid.uuid4())

def save_check_session(session_id, user_id, total, valid, results):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('''
            INSERT INTO check_history 
            (session_id, user_id, total_cookies, valid_cookies, check_date, results)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, user_id, total, valid, datetime.now().isoformat(), json.dumps(results)))
        conn.commit()
        conn.close()
        
        update_global_stats(total, valid)
        return True
    except Exception as e:
        print(f"Error saving session: {e}")
        return False

def get_user_history(user_id, limit=20):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('''
            SELECT * FROM check_history 
            WHERE user_id = ?
            ORDER BY check_date DESC 
            LIMIT ?
        ''', (user_id, limit))
        history = c.fetchall()
        conn.close()
        
        result = []
        for item in history:
            result.append({
                'id': item[0],
                'session_id': item[1],
                'user_id': item[2],
                'total_cookies': item[3],
                'valid_cookies': item[4],
                'check_date': item[5],
                'results': json.loads(item[6]) if item[6] else []
            })
        return result
    except Exception as e:
        return []

def get_session_results(session_id, user_id):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT results FROM check_history WHERE session_id = ? AND user_id = ?', (session_id, user_id))
        result = c.fetchone()
        conn.close()
        return json.loads(result[0]) if result else None
    except:
        return None

# Улучшенный класс для проверки Roblox куки с полной информацией
class AdvancedRobloxChecker:
    def __init__(self):
        self.timeout = 30
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.roblox.com/',
            'Origin': 'https://www.roblox.com'
        }

    def clean_cookie(self, cookie):
        """Тщательная очистка куки"""
        if not cookie or len(cookie) < 100:
            return None
            
        cookie = cookie.strip()
        
        # Убираем кавычки
        if cookie.startswith('"') and cookie.endswith('"'):
            cookie = cookie[1:-1]
        if cookie.startswith("'") and cookie.endswith("'"):
            cookie = cookie[1:-1]
        
        # Убираем лишние пробелы и переносы
        cookie = re.sub(r'\s+', '', cookie)
        
        # Проверяем базовый формат Roblox куки
        if not cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.'):
            # Попробуем найти куки в строке
            cookie_match = re.search(r'_\|WARNING:-DO-NOT-SHARE-THIS\.[^_]*_', cookie)
            if cookie_match:
                cookie = cookie_match.group(0)
            else:
                return None
            
        return cookie if len(cookie) > 100 else None

    async def get_csrf_token(self, session, cookie):
        """Получение CSRF токена"""
        try:
            async with session.post(
                'https://auth.roblox.com/v2/login',
                headers={'Cookie': f'.ROBLOSECURITY={cookie}'},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 403 and 'x-csrf-token' in response.headers:
                    return response.headers['x-csrf-token']
            
            endpoints = [
                'https://www.roblox.com/game/GetCurrentUser',
                'https://accountsettings.roblox.com/v1/email',
                'https://users.roblox.com/v1/users/authenticated'
            ]
            
            for endpoint in endpoints:
                try:
                    async with session.post(
                        endpoint,
                        headers={'Cookie': f'.ROBLOSECURITY={cookie}'},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if 'x-csrf-token' in response.headers:
                            return response.headers['x-csrf-token']
                except:
                    continue
                    
        except Exception as e:
            print(f"CSRF token error: {e}")
            
        return None

    async def make_authenticated_request(self, session, url, cookie, method='GET', retry_count=2):
        """Улучшенный запрос с обработкой CSRF токена"""
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            **self.headers
        }
        
        for attempt in range(retry_count):
            try:
                if method.upper() == 'POST':
                    csrf_token = await self.get_csrf_token(session, cookie)
                    if csrf_token:
                        headers['X-CSRF-TOKEN'] = csrf_token
                
                if method.upper() == 'POST':
                    async with session.post(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            return None
                        elif response.status == 403 and attempt < retry_count - 1:
                            await asyncio.sleep(1)
                            continue
                        elif response.status == 429:
                            await asyncio.sleep(3)
                            continue
                else:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            return None
                        elif response.status == 429 and attempt < retry_count - 1:
                            await asyncio.sleep(3)
                            continue
                            
            except asyncio.TimeoutError:
                if attempt < retry_count - 1:
                    await asyncio.sleep(2)
                    continue
            except Exception as e:
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)
                    continue
                    
        return None

    async def get_account_info(self, cookie):
        """Основная функция получения информации об аккаунте"""
        try:
            async with aiohttp.ClientSession() as session:
                # Проверка аутентификации
                auth_url = 'https://users.roblox.com/v1/users/authenticated'
                auth_data = await self.make_authenticated_request(session, auth_url, cookie, 'GET')
                
                if not auth_data or 'id' not in auth_data:
                    alt_url = 'https://www.roblox.com/mobileapi/userinfo'
                    alt_data = await self.make_authenticated_request(session, alt_url, cookie, 'GET')
                    
                    if alt_data and 'UserID' in alt_data:
                        auth_data = {
                            'id': alt_data['UserID'],
                            'name': alt_data['UserName'],
                            'displayName': alt_data.get('DisplayName', alt_data['UserName']),
                            'isBanned': False
                        }
                    else:
                        return None
                
                user_id = auth_data['id']
                
                # Получаем полную информацию об аккаунте
                account_info = await self.get_complete_account_info(session, cookie, user_id, auth_data)
                return account_info
                
        except Exception as e:
            print(f"Account info error: {e}")
            return None

    async def get_complete_account_info(self, session, cookie, user_id, auth_data):
        """Получение полной информации об аккаунте"""
        try:
            # Базовая информация
            base_info = {
                'username': auth_data.get('name', 'N/A'),
                'display_name': auth_data.get('displayName', auth_data.get('name', 'N/A')),
                'user_id': user_id,
                'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                'is_banned': auth_data.get('isBanned', False),
                'created': auth_data.get('created', '')
            }
            
            # Все необходимые проверки параллельно
            tasks = [
                self.get_economy_info(session, cookie, user_id),
                self.get_premium_status(session, cookie, user_id),
                self.get_social_info(session, cookie, user_id),
                self.get_security_info(session, cookie, user_id),
                self.get_profile_info(session, cookie, user_id),
                self.get_rap_value(session, cookie, user_id),
                self.get_billing_info(session, cookie),
                self.get_card_info(session, cookie),
                self.get_inventory_privacy(session, cookie),
                self.get_trade_privacy(session, cookie),
                self.get_can_trade(session, cookie, user_id),
                self.get_sessions_info(session, cookie),
                self.get_email_info(session, cookie, user_id),
                self.get_phone_info(session, cookie),
                self.get_pin_info(session, cookie, user_id),
                self.get_groups_info(session, cookie, user_id),
                self.get_age_info(session, cookie, user_id),
                self.get_voice_info(session, cookie),
                self.get_roblox_badges(session, cookie, user_id)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Безопасное извлечение результатов
            economy = results[0] if not isinstance(results[0], Exception) else {}
            premium = results[1] if not isinstance(results[1], Exception) else {}
            social = results[2] if not isinstance(results[2], Exception) else {}
            security = results[3] if not isinstance(results[3], Exception) else {}
            profile = results[4] if not isinstance(results[4], Exception) else {}
            rap_value = results[5] if not isinstance(results[5], Exception) else {}
            billing = results[6] if not isinstance(results[6], Exception) else {}
            card = results[7] if not isinstance(results[7], Exception) else {}
            inventory_privacy = results[8] if not isinstance(results[8], Exception) else {}
            trade_privacy = results[9] if not isinstance(results[9], Exception) else {}
            can_trade = results[10] if not isinstance(results[10], Exception) else {}
            sessions = results[11] if not isinstance(results[11], Exception) else {}
            email = results[12] if not isinstance(results[12], Exception) else {}
            phone = results[13] if not isinstance(results[13], Exception) else {}
            pin = results[14] if not isinstance(results[14], Exception) else {}
            groups = results[15] if not isinstance(results[15], Exception) else {}
            age = results[16] if not isinstance(results[16], Exception) else {}
            voice = results[17] if not isinstance(results[17], Exception) else {}
            roblox_badges = results[18] if not isinstance(results[18], Exception) else {}
            
            # Объединяем все результаты
            base_info.update(economy if isinstance(economy, dict) else {})
            base_info.update(premium if isinstance(premium, dict) else {})
            base_info.update(social if isinstance(social, dict) else {})
            base_info.update(security if isinstance(security, dict) else {})
            base_info.update(profile if isinstance(profile, dict) else {})
            base_info.update(rap_value if isinstance(rap_value, dict) else {})
            base_info.update(billing if isinstance(billing, dict) else {})
            base_info.update(card if isinstance(card, dict) else {})
            base_info.update(inventory_privacy if isinstance(inventory_privacy, dict) else {})
            base_info.update(trade_privacy if isinstance(trade_privacy, dict) else {})
            base_info.update(can_trade if isinstance(can_trade, dict) else {})
            base_info.update(sessions if isinstance(sessions, dict) else {})
            base_info.update(email if isinstance(email, dict) else {})
            base_info.update(phone if isinstance(phone, dict) else {})
            base_info.update(pin if isinstance(pin, dict) else {})
            base_info.update(groups if isinstance(groups, dict) else {})
            base_info.update(age if isinstance(age, dict) else {})
            base_info.update(voice if isinstance(voice, dict) else {})
            base_info.update(roblox_badges if isinstance(roblox_badges, dict) else {})
            
            # Расчет возраста аккаунта
            if auth_data.get('created'):
                age_info = self.calculate_account_age(auth_data['created'])
                base_info.update(age_info)
            else:
                base_info.update({
                    'account_age_days': 0,
                    'account_age_years': 0,
                    'formatted_date': 'Unknown'
                })
            
            # Расчет стоимости аккаунта
            base_info['account_value'] = self.calculate_account_value(base_info)
            
            return base_info
            
        except Exception as e:
            print(f"Complete account info error: {e}")
            return self.get_basic_account_info(auth_data, user_id)

    def get_basic_account_info(self, auth_data, user_id):
        """Базовая информация при ошибке"""
        return {
            'username': auth_data.get('name', 'N/A'),
            'display_name': auth_data.get('displayName', auth_data.get('name', 'N/A')),
            'user_id': user_id,
            'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
            'is_banned': auth_data.get('isBanned', False),
            'account_age_days': 0,
            'account_age_years': 0,
            'formatted_date': 'Unknown',
            'robux_balance': 0,
            'pending_robux': 0,
            'total_robux': 0,
            'premium': False,
            'premium_status': 'Inactive',
            'friends_count': 0,
            'followers_count': 0,
            'following_count': 0,
            '2fa_enabled': False,
            'rap_value': 0,
            'billing_robux': 0,
            'card_count': 0,
            'inventory_privacy': 'Unknown',
            'trade_privacy': 'Unknown',
            'can_trade': False,
            'sessions_count': 0,
            'email_status': 'Unknown',
            'phone_status': 'No',
            'pin_enabled': False,
            'groups_owned': 0,
            'groups_members': 0,
            'groups_pending': 0,
            'groups_funds': 0,
            'above_13': 'Unknown',
            'verified_age': 'No',
            'voice_enabled': 'No',
            'roblox_badges_count': 0,
            'account_value': 0
        }

    async def get_economy_info(self, session, cookie, user_id):
        """Информация об экономике"""
        try:
            url = f'https://economy.roblox.com/v1/users/{user_id}/currency'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {
                    'robux_balance': data.get('robux', 0),
                    'pending_robux': data.get('pendingRobux', 0),
                    'total_robux': data.get('robux', 0) + data.get('pendingRobux', 0)
                }
        except Exception as e:
            print(f"Economy info error: {e}")
        
        return {'robux_balance': 0, 'pending_robux': 0, 'total_robux': 0}

    async def get_premium_status(self, session, cookie, user_id):
        """Статус Premium"""
        try:
            url = f'https://premiumfeatures.roblox.com/v1/users/{user_id}/premium'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {
                    'premium': data.get('isPremium', False),
                    'premium_status': 'Active' if data.get('isPremium') else 'Inactive'
                }
        except Exception as e:
            print(f"Premium status error: {e}")
        
        return {'premium': False, 'premium_status': 'Inactive'}

    async def get_social_info(self, session, cookie, user_id):
        """Социальная информация"""
        try:
            friends_url = f'https://friends.roblox.com/v1/users/{user_id}/friends/count'
            followers_url = f'https://friends.roblox.com/v1/users/{user_id}/followers/count'
            following_url = f'https://friends.roblox.com/v1/users/{user_id}/followings/count'
            
            friends_data = await self.make_authenticated_request(session, friends_url, cookie, 'GET')
            followers_data = await self.make_authenticated_request(session, followers_url, cookie, 'GET')
            following_data = await self.make_authenticated_request(session, following_url, cookie, 'GET')
            
            return {
                'friends_count': friends_data.get('count', 0) if friends_data else 0,
                'followers_count': followers_data.get('count', 0) if followers_data else 0,
                'following_count': following_data.get('count', 0) if following_data else 0
            }
        except Exception as e:
            print(f"Social info error: {e}")
        
        return {'friends_count': 0, 'followers_count': 0, 'following_count': 0}

    async def get_security_info(self, session, cookie, user_id):
        """Информация о безопасности"""
        try:
            url = f'https://twostepverification.roblox.com/v1/users/{user_id}/configuration'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {'2fa_enabled': data.get('twoStepVerificationEnabled', False)}
        except Exception as e:
            print(f"Security info error: {e}")
        
        return {'2fa_enabled': False}

    async def get_profile_info(self, session, cookie, user_id):
        """Информация профиля"""
        try:
            url = f'https://users.roblox.com/v1/users/{user_id}'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {
                    'description': data.get('description', '')[:200],
                    'followers_count': data.get('followersCount', 0),
                    'following_count': data.get('followingsCount', 0),
                }
        except Exception as e:
            print(f"Profile info error: {e}")
        
        return {'description': '', 'followers_count': 0, 'following_count': 0}

    async def get_rap_value(self, session, cookie, user_id):
        """RAP стоимость инвентаря"""
        try:
            rap_value = 0
            next_cursor = ''
            max_pages = 3  # Ограничиваем для скорости
            
            for page in range(max_pages):
                url = f'https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?sortOrder=Asc&limit=100&cursor={next_cursor}'
                data = await self.make_authenticated_request(session, url, cookie, 'GET')
                
                if not data or 'data' not in data:
                    break
                    
                for item in data['data']:
                    if item.get('recentAveragePrice'):
                        rap_value += item['recentAveragePrice']
                
                next_cursor = data.get('nextPageCursor')
                if not next_cursor:
                    break
            
            return {'rap_value': rap_value}
        except Exception as e:
            print(f"RAP value error: {e}")
        
        return {'rap_value': 0}

    async def get_billing_info(self, session, cookie):
        """Информация о биллинге"""
        try:
            url = 'https://billing.roblox.com/v1/credit'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {'billing_robux': data.get('robuxAmount', 0)}
        except Exception as e:
            print(f"Billing info error: {e}")
        
        return {'billing_robux': 0}

    async def get_card_info(self, session, cookie):
        """Информация о привязанных картах"""
        try:
            url = 'https://apis.roblox.com/payments-gateway/v1/payment-profiles'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {'card_count': len(data)}
        except Exception as e:
            print(f"Card info error: {e}")
        
        return {'card_count': 0}

    async def get_inventory_privacy(self, session, cookie):
        """Настройки приватности инвентаря"""
        try:
            url = 'https://apis.roblox.com/user-settings-api/v1/user-settings/settings-and-options'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data and 'whoCanSeeMyInventory' in data:
                privacy = data['whoCanSeeMyInventory']['currentValue']
                privacy_map = {
                    'AllUsers': 'Everyone',
                    'FriendsFollowingAndFollowers': 'Friends & Followers',
                    'FriendsAndFollowing': 'Friends & Following',
                    'Friends': 'Friends',
                    'NoOne': 'No One'
                }
                return {'inventory_privacy': privacy_map.get(privacy, 'Unknown')}
        except Exception as e:
            print(f"Inventory privacy error: {e}")
        
        return {'inventory_privacy': 'Unknown'}

    async def get_trade_privacy(self, session, cookie):
        """Настройки приватности трейда"""
        try:
            url = 'https://accountsettings.roblox.com/v1/trade-privacy'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                privacy = data.get('tradePrivacy')
                privacy_map = {
                    'AllUsers': 'Everyone',
                    'FriendsFollowingAndFollowers': 'Friends & Followers',
                    'FriendsAndFollowing': 'Friends & Following',
                    'Friends': 'Friends',
                    'NoOne': 'No One'
                }
                return {'trade_privacy': privacy_map.get(privacy, 'Unknown')}
        except Exception as e:
            print(f"Trade privacy error: {e}")
        
        return {'trade_privacy': 'Unknown'}

    async def get_can_trade(self, session, cookie, user_id):
        """Возможность трейдить"""
        try:
            url = f'https://www.roblox.com/users/{user_id}/profile'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            # Это упрощенная проверка - в реальности нужно парсить HTML
            return {'can_trade': True}  # По умолчанию True
        except Exception as e:
            print(f"Can trade error: {e}")
        
        return {'can_trade': False}

    async def get_sessions_info(self, session, cookie):
        """Информация о сессиях"""
        try:
            url = 'https://apis.roblox.com/token-metadata-service/v1/sessions'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data and 'sessions' in data:
                return {'sessions_count': len(data['sessions'])}
        except Exception as e:
            print(f"Sessions info error: {e}")
        
        return {'sessions_count': 0}

    async def get_email_info(self, session, cookie, user_id):
        """Информация о email"""
        try:
            url = 'https://accountsettings.roblox.com/v1/email'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                email_set = data.get('emailAddress') is not None
                email_verified = data.get('verified', False)
                
                if not email_set:
                    status = 'No'
                elif email_set and email_verified:
                    status = 'Yes'
                else:
                    status = 'Setted'
                
                return {'email_status': status}
        except Exception as e:
            print(f"Email info error: {e}")
        
        return {'email_status': 'Unknown'}

    async def get_phone_info(self, session, cookie):
        """Информация о телефоне"""
        try:
            url = 'https://accountinformation.roblox.com/v1/phone'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {'phone_status': 'Yes' if data.get('phone') else 'No'}
        except Exception as e:
            print(f"Phone info error: {e}")
        
        return {'phone_status': 'No'}

    async def get_pin_info(self, session, cookie, user_id):
        """Информация о PIN коде"""
        try:
            url = f'https://accountsettings.roblox.com/v1/users/{user_id}/pin'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {'pin_enabled': data.get('isEnabled', False)}
        except Exception as e:
            print(f"PIN info error: {e}")
        
        return {'pin_enabled': False}

    async def get_groups_info(self, session, cookie, user_id):
        """Информация о группах"""
        try:
            url = f'https://groups.roblox.com/v1/users/{user_id}/groups/roles?includeLocked=true'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data and 'data' in data:
                groups_owned = 0
                total_members = 0
                
                for group in data['data']:
                    if group['role']['rank'] == 255:  # Владелец
                        groups_owned += 1
                    total_members += group['group']['memberCount']
                
                return {
                    'groups_owned': groups_owned,
                    'groups_members': total_members,
                    'groups_pending': 0,  # Упрощенно
                    'groups_funds': 0     # Упрощенно
                }
        except Exception as e:
            print(f"Groups info error: {e}")
        
        return {'groups_owned': 0, 'groups_members': 0, 'groups_pending': 0, 'groups_funds': 0}

    async def get_age_info(self, session, cookie, user_id):
        """Информация о возрасте"""
        try:
            url = f'https://users.roblox.com/v1/users/{user_id}'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                # Упрощенная проверка возраста
                return {
                    'above_13': 'Yes',  # По умолчанию
                    'verified_age': 'No'  # Упрощенно
                }
        except Exception as e:
            print(f"Age info error: {e}")
        
        return {'above_13': 'Unknown', 'verified_age': 'No'}

    async def get_voice_info(self, session, cookie):
        """Информация о голосовом чате"""
        try:
            url = 'https://voice.roblox.com/v1/settings'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {'voice_enabled': 'Yes' if data.get('isVerifiedForVoice') else 'No'}
        except Exception as e:
            print(f"Voice info error: {e}")
        
        return {'voice_enabled': 'No'}

    async def get_roblox_badges(self, session, cookie, user_id):
        """Бейджи Roblox"""
        try:
            url = f'https://accountinformation.roblox.com/v1/users/{user_id}/roblox-badges'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                return {'roblox_badges_count': len(data)}
        except Exception as e:
            print(f"Roblox badges error: {e}")
        
        return {'roblox_badges_count': 0}

    def calculate_account_age(self, created_date_str):
        """Расчет возраста аккаунта"""
        try:
            created_date = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
            now = datetime.now()
            
            age_delta = now - created_date
            age_days = age_delta.days
            age_years = age_days / 365.25
            
            return {
                'account_age_days': age_days,
                'account_age_years': round(age_years, 1),
                'formatted_date': created_date.strftime('%Y-%m-%d')
            }
        except:
            return {'account_age_days': 0, 'account_age_years': 0, 'formatted_date': 'Unknown'}

    def calculate_account_value(self, account_info):
        """Расчет стоимости аккаунта"""
        try:
            robux = account_info.get('robux_balance', 0) or 0
            rap_value = account_info.get('rap_value', 0) or 0
            age_years = account_info.get('account_age_years', 0) or 0
            friends_count = account_info.get('friends_count', 0) or 0
            premium = account_info.get('premium', False)
            
            value = robux * 0.0035
            value += rap_value * 0.001
            value += age_years * 200
            value += friends_count * 2
            
            if premium:
                value += 300
                
            return round(max(value, 5), 2)
        except Exception as e:
            print(f"Account value calculation error: {e}")
            return 5.0

    async def check_single_cookie(self, cookie):
        """Проверка одной куки"""
        clean_cookie = self.clean_cookie(cookie)
        if not clean_cookie:
            return {
                'valid': False,
                'cookie': cookie,
                'error': 'Invalid cookie format',
                'checked_at': datetime.now().isoformat()
            }
        
        try:
            account_info = await self.get_account_info(clean_cookie)
            
            if account_info:
                return {
                    'valid': True,
                    'cookie': clean_cookie,
                    'account_info': account_info,
                    'checked_at': datetime.now().isoformat()
                }
            else:
                return {
                    'valid': False,
                    'cookie': clean_cookie,
                    'error': 'Authentication failed - invalid cookie',
                    'checked_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'valid': False,
                'cookie': clean_cookie,
                'error': f'Check error: {str(e)}',
                'checked_at': datetime.now().isoformat()
            }

    async def check_multiple_cookies(self, cookies):
        """Проверка нескольких куки"""
        valid_cookies = []
        
        for cookie in cookies:
            clean_cookie = self.clean_cookie(cookie)
            if clean_cookie and clean_cookie not in valid_cookies:
                valid_cookies.append(clean_cookie)
        
        if not valid_cookies:
            return [{
                'valid': False,
                'cookie': "",
                'error': "No valid cookies found",
                'checked_at': datetime.now().isoformat()
            }]
        
        semaphore = asyncio.Semaphore(2)
        
        async def check_with_semaphore(cookie):
            async with semaphore:
                await asyncio.sleep(1)
                return await self.check_single_cookie(cookie)
        
        tasks = [check_with_semaphore(cookie) for cookie in valid_cookies]
        results = await asyncio.gather(*tasks)
        
        return results

def async_to_sync(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

checker = AdvancedRobloxChecker()

@app.route('/')
def index():
    session_id = get_user_id()
    update_user_session(session_id)
    return render_template('index.html')

@app.route('/api/global_stats')
def api_global_stats():
    try:
        stats = get_global_stats()
        stats['active_users'] = get_active_users_count()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Stats error: {str(e)}'}), 500

@app.route('/api/history')
def api_history():
    try:
        user_id = get_user_id()
        update_user_session(user_id)
        history = get_user_history(user_id, 20)
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/check', methods=['POST'])
@async_to_sync
async def api_check_cookies():
    try:
        user_id = get_user_id()
        update_user_session(user_id)
        
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
        
        cookies = data['cookies']
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies = [c.strip() for c in cookies if c.strip()]
        
        if not cookies:
            return jsonify({'error': 'No valid cookies provided'}), 400
        
        if len(cookies) > 100:
            return jsonify({'error': 'Too many cookies. Maximum 100 per request.'}), 400
        
        results = await checker.check_multiple_cookies(cookies)
        
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S_') + ''.join(random.choices('0123456789abcdef', k=8))
        valid_count = len([r for r in results if r.get('valid', False)])
        
        save_check_session(session_id, user_id, len(cookies), valid_count, results)
        
        return jsonify({
            'total': len(results),
            'valid': valid_count,
            'invalid': len(results) - valid_count,
            'results': results,
            'session_id': session_id,
            'checked_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/download/<session_id>')
def api_download_results(session_id):
    try:
        user_id = get_user_id()
        update_user_session(user_id)
        
        results = get_session_results(session_id, user_id)
        if not results:
            return jsonify({'error': 'Results not found'}), 404
        
        valid_cookies = [r for r in results if r.get('valid')]
        if not valid_cookies:
            return jsonify({'error': 'No valid cookies'}), 400
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            cookies_content = "\n".join([r['cookie'] for r in valid_cookies])
            zip_file.writestr('valid_cookies.txt', cookies_content)
            
            detailed_report = {
                'check_date': datetime.now().isoformat(),
                'session_id': session_id,
                'summary': {
                    'total_checked': len(results),
                    'valid': len(valid_cookies),
                    'invalid': len([r for r in results if not r['valid']])
                },
                'valid_accounts': []
            }
            
            for result in valid_cookies:
                acc = result.get('account_info', {})
                detailed_report['valid_accounts'].append({
                    'username': acc.get('username', 'N/A'),
                    'user_id': acc.get('user_id', 'N/A'),
                    'robux': acc.get('total_robux', 0),
                    'premium': acc.get('premium', False),
                    'account_age': acc.get('account_age_days', 0),
                    'friends': acc.get('friends_count', 0),
                    'account_value': acc.get('account_value', 0),
                    'created_date': acc.get('formatted_date', 'Unknown')
                })
            
            zip_file.writestr('detailed_report.json', json.dumps(detailed_report, indent=2, ensure_ascii=False))
        
        zip_buffer.seek(0)
        filename = f'roblox_cookies_{session_id}.zip'
        
        return send_file(zip_buffer, as_attachment=True, download_name=filename, mimetype='application/zip')
        
    except Exception as e:
        return jsonify({'error': f'Archive error: {str(e)}'}), 500

@app.route('/api/session/<session_id>')
def api_get_session(session_id):
    try:
        user_id = get_user_id()
        update_user_session(user_id)
        
        results = get_session_results(session_id, user_id)
        if results:
            valid_count = len([r for r in results if r.get('valid', False)])
            return jsonify({
                'total': len(results),
                'valid': valid_count,
                'invalid': len(results) - valid_count,
                'results': results
            })
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/delete/<session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    try:
        user_id = get_user_id()
        update_user_session(user_id)
        
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('DELETE FROM check_history WHERE session_id = ? AND user_id = ?', (session_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Delete failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)