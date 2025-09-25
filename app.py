from flask import Flask, render_template, request, jsonify
import os
import requests
import time
from datetime import datetime

app = Flask(__name__)

class RobloxCookieChecker:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://users.roblox.com/v1/users/authenticated"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def check_cookie(self, cookie):
        try:
            headers = self.headers.copy()
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'
            
            response = self.session.get(self.base_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    'valid': True,
                    'username': user_data.get('name', 'N/A'),
                    'user_id': user_data.get('id', 'N/A'),
                    'display_name': user_data.get('displayName', 'N/A'),
                    'robux': self.get_robux_balance(cookie),
                    'premium': self.check_premium(cookie),
                    'cookie': cookie[:20] + '...' if len(cookie) > 20 else cookie
                }
            else:
                return {
                    'valid': False,
                    'error': f'HTTP {response.status_code}',
                    'cookie': cookie[:20] + '...' if len(cookie) > 20 else cookie
                }
                
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'cookie': cookie[:20] + '...' if len(cookie) > 20 else cookie
            }
    
    def get_robux_balance(self, cookie):
        try:
            headers = self.headers.copy()
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'
            
            response = self.session.get(
                'https://economy.roblox.com/v1/user/currency',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('robux', 0)
            return 0
        except:
            return 0
    
    def check_premium(self, cookie):
        try:
            headers = self.headers.copy()
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'
            
            response = self.session.get(
                'https://premiumfeatures.roblox.com/v1/users/premium/membership',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('isPremium', False)
            return False
        except:
            return False
    
    def check_multiple(self, cookies_list):
        results = []
        for cookie in cookies_list:
            if cookie.strip():
                result = self.check_cookie(cookie.strip())
                results.append(result)
                time.sleep(0.5)
        return results

checker = RobloxCookieChecker()

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
        
        if len(cookies) > 50:
            return jsonify({'error': 'Too many cookies. Maximum 50 per request.'}), 400
        
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
            'results': results
        })
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', False))