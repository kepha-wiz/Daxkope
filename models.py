from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string

db = SQLAlchemy()


def generate_referral_code():
    alphabet = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(alphabet) for _ in range(5))
    return f"CFFA-{suffix}"


def generate_reference(prefix="TXN"):
    return f"{prefix}-{secrets.token_hex(5).upper()}"


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    referral_code = db.Column(db.String(20), unique=True, default=generate_referral_code)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    profile_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    wallet = db.relationship('Wallet', backref='user', uselist=False, cascade="all, delete-orphan")
    transactions = db.relationship('Transaction', backref='user', cascade="all, delete-orphan")
    user_machines = db.relationship('UserMachine', backref='user', cascade="all, delete-orphan")
    deposits = db.relationship('Deposit', backref='user', cascade="all, delete-orphan")
    withdrawals = db.relationship('Withdrawal', backref='user', cascade="all, delete-orphan")
    referrals_made = db.relationship('User', backref=db.backref('referrer', remote_side=[id]))
    raffle_entries = db.relationship('RaffleEntry', backref='user', cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def total_portfolio_value(self):
        active_value = sum(um.current_simulated_value for um in self.user_machines if um.status == 'active')
        return (self.wallet.balance if self.wallet else 0) + active_value
    
    @property
    def active_machine_count(self):
        return sum(1 for um in self.user_machines if um.status == 'active')


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    bonus_balance = db.Column(db.Float, default=0.0)
    investment_balance = db.Column(db.Float, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # deposit, bonus, purchase, return, withdrawal, referral, raffle
    amount = db.Column(db.Float, nullable=False)
    balance_before = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(50), default=generate_reference)
    description = db.Column(db.String(255))
    status = db.Column(db.String(20), default='completed')  # pending, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Machine(db.Model):
    """Master machine catalogue — populated from config."""
    id = db.Column(db.String(10), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    simulation_target = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    tier = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)


class UserMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    machine_id = db.Column(db.String(10), db.ForeignKey('machine.id'), nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    simulated_target = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    machine = db.relationship('Machine')
    
    @property
    def progress_percent(self):
        now = datetime.utcnow()
        total = (self.end_date - self.start_date).total_seconds()
        if total <= 0:
            return 100.0
        elapsed = (now - self.start_date).total_seconds()
        return min(100.0, max(0.0, (elapsed / total) * 100))
    
    @property
    def days_elapsed(self):
        return (datetime.utcnow() - self.start_date).days
    
    @property
    def days_remaining(self):
        return max(0, (self.end_date - datetime.utcnow()).days)
    
    @property
    def current_simulated_value(self):
        progress = self.progress_percent / 100.0
        base = self.purchase_price
        gain = (self.simulated_target - self.purchase_price) * progress
        return base + gain


class Deposit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(20), nullable=False)
    reference_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)


class Withdrawal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(20), nullable=False)
    mobile_number = db.Column(db.String(20), nullable=False)
    fee = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)


class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reward_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_given')
    referred = db.relationship('User', foreign_keys=[referred_id])


class Raffle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    prize_amount = db.Column(db.Float, nullable=False)
    closes_at = db.Column(db.DateTime, nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_closed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    entries = db.relationship('RaffleEntry', backref='raffle', cascade="all, delete-orphan")
    winner = db.relationship('User')


class RaffleEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey('raffle.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    entries = db.Column(db.Integer, default=1)
    reason = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ScamReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_name = db.Column(db.String(120))
    reporter_contact = db.Column(db.String(120))
    scammer_name = db.Column(db.String(120), nullable=False)
    scammer_contact = db.Column(db.String(200))
    platform = db.Column(db.String(100))
    method = db.Column(db.String(200))
    amount_involved = db.Column(db.Float)
    description = db.Column(db.Text, nullable=False)
    evidence = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')  # new, reviewed, resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
