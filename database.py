from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class UserSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), unique=True, nullable=False)
    browser_info = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CookieCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('user_session.session_id'))
    check_id = db.Column(db.String(36), unique=True, nullable=False)
    cookie_data = db.Column(db.Text)
    result_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Статистика для сортировки
    account_age = db.Column(db.Integer)
    balance = db.Column(db.Float)
    rap = db.Column(db.Float)
    total_spent = db.Column(db.Float)
    has_2fa = db.Column(db.Boolean)
    has_premium = db.Column(db.Boolean)
    has_phone = db.Column(db.Boolean)
    has_card = db.Column(db.Boolean)