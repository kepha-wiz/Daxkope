import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, jsonify, abort)
from sqlalchemy import func

from config import Config
from models import (db, User, Wallet, Transaction, Machine, UserMachine,
                    Deposit, Withdrawal, Referral, Raffle, RaffleEntry, ScamReport,
                    generate_referral_code, generate_reference)

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = app.config['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


# ---------------------------
# Helpers
# ---------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def format_ugx(value):
    try:
        return f"UGX {int(value):,}"
    except (TypeError, ValueError):
        return "UGX 0"


@app.context_processor
def inject_globals():
    return {
        'current_user': current_user(),
        'format_ugx': format_ugx,
        'machines_config': app.config['MACHINES'],
        'now': datetime.utcnow(),
    }


def record_transaction(user, tx_type, amount, description, status='completed'):
    """Create an immutable transaction and update wallet accordingly."""
    wallet = user.wallet
    balance_before = wallet.balance
    
    if tx_type in ('deposit', 'bonus', 'return', 'referral', 'raffle'):
        wallet.balance += amount
    elif tx_type in ('purchase', 'withdrawal'):
        wallet.balance -= amount
    
    tx = Transaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        balance_before=balance_before,
        balance_after=wallet.balance,
        description=description,
        status=status,
        reference=generate_reference()
    )
    db.session.add(tx)
    wallet.updated_at = datetime.utcnow()
    db.session.commit()
    return tx


def ensure_wallet(user):
    if not user.wallet:
        w = Wallet(user_id=user.id)
        db.session.add(w)
        db.session.commit()
        db.session.refresh(user)


def seed_database():
    """Populate demo data — clearly marked as simulation."""
    if User.query.first():
        return
    
    # Seed machine catalogue
    for m in app.config['MACHINES']:
        db.session.add(Machine(
            id=m['id'], name=m['name'], price=m['price'],
            simulation_target=m['simulation_target'],
            duration_days=m['duration_days'],
            description=m['description'],
            icon=m['icon'], tier=m['tier']
        ))
    
    # Admin user
    admin = User(
        full_name='System Administrator',
        email=app.config['ADMIN_EMAIL'],
        phone='+256700000000',
        is_admin=True,
        profile_completed=True
    )
    admin.set_password('Admin@2026!')
    db.session.add(admin)
    db.session.flush()
    db.session.add(Wallet(user_id=admin.id))
    
    # Demo users
    demo1 = User(full_name='Jane Nakato', email='jane@demo.com', phone='+256771111111', profile_completed=True)
    demo1.set_password('Demo@1234')
    demo2 = User(full_name='Peter Ochieng', email='peter@demo.com', phone='+256772222222', referred_by_id=None, profile_completed=True)
    demo2.set_password('Demo@1234')
    db.session.add_all([demo1, demo2])
    db.session.flush()
    
    for u in [demo1, demo2]:
        db.session.add(Wallet(user_id=u.id, balance=50000))
    
    db.session.commit()
    
    # Seed an active raffle
    r = Raffle(
        name='Weekly AI Infrastructure Raffle',
        prize_amount=app.config['RAFFLE_DEFAULT_PRIZE'],
        closes_at=datetime.utcnow() + timedelta(days=app.config['RAFFLE_DEFAULT_DURATION_DAYS'])
    )
    db.session.add(r)
    db.session.commit()
    print("[seed] Demo data created. Admin login:", app.config['ADMIN_EMAIL'], "/ Admin@2026!")


# ---------------------------
# Public routes
# ---------------------------

@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        referral_code = request.form.get('referral_code', '').strip().upper()
        
        if not all([full_name, email, phone, password]):
            flash('All fields are required.', 'error')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('register'))
        
        referrer = None
        if referral_code:
            referrer = User.query.filter_by(referral_code=referral_code).first()
            if not referrer:
                flash('Invalid referral code. Continuing without referral.', 'warning')
        
        user = User(
            full_name=full_name, email=email, phone=phone,
            referred_by_id=referrer.id if referrer else None
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(Wallet(user_id=user.id))
        
        # Award referral reward
        if referrer:
            ref = Referral(referrer_id=referrer.id, referred_id=user.id,
                           reward_amount=app.config['REFERRAL_REWARD'])
            db.session.add(ref)
            db.session.flush()
            ensure_wallet(referrer)
            record_transaction(referrer, 'referral', app.config['REFERRAL_REWARD'],
                               f"Referral reward for inviting {full_name}")
            flash(f"Referrer {referrer.full_name} received a {format_ugx(app.config['REFERRAL_REWARD'])} simulation reward.", 'success')
        
        db.session.commit()
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session.permanent = True
            flash(f'Welcome back, {user.full_name.split()[0]}!', 'success')
            return redirect(url_for('admin_dashboard') if user.is_admin else url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing'))


# ---------------------------
# Dashboard
# ---------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    ensure_wallet(user)
    active_machines = [um for um in user.user_machines if um.status == 'active']
    recent_tx = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(6).all()
    return render_template('dashboard.html', user=user, active_machines=active_machines, recent_tx=recent_tx)


# ---------------------------
# Machines
# ---------------------------

@app.route('/machines')
@login_required
def machines():
    user = current_user()
    ensure_wallet(user)
    catalogue = Machine.query.filter_by(is_active=True).all()
    return render_template('machines.html', machines=catalogue, user=user)


@app.route('/machines/<machine_id>')
@login_required
def machine_detail(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    user = current_user()
    ensure_wallet(user)
    owned = UserMachine.query.filter_by(user_id=user.id, machine_id=machine_id, status='active').first()
    return render_template('machine_detail.html', machine=machine, owned=owned, user=user)


@app.route('/machines/<machine_id>/buy', methods=['POST'])
@login_required
def buy_machine(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    user = current_user()
    ensure_wallet(user)
    
    if user.wallet.balance < machine.price:
        flash(f'Insufficient balance. You need {format_ugx(machine.price)}.', 'error')
        return redirect(url_for('machine_detail', machine_id=machine_id))
    
    um = UserMachine(
        user_id=user.id,
        machine_id=machine.id,
        purchase_price=machine.price,
        simulated_target=machine.simulation_target,
        end_date=datetime.utcnow() + timedelta(days=machine.duration_days)
    )
    db.session.add(um)
    user.wallet.investment_balance += machine.price
    record_transaction(user, 'purchase', machine.price,
                       f"Purchased simulated {machine.name}")
    flash(f'Successfully acquired {machine.name}. Simulation started.', 'success')
    return redirect(url_for('dashboard'))


# ---------------------------
# Wallet
# ---------------------------

@app.route('/wallet')
@login_required
def wallet():
    user = current_user()
    ensure_wallet(user)
    return render_template('wallet.html', user=user)


@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    user = current_user()
    ensure_wallet(user)
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            flash('Invalid amount.', 'error')
            return redirect(url_for('deposit'))
        method = request.form.get('method')
        reference_id = request.form.get('reference_id', '').strip()
        
        if amount < app.config['MIN_DEPOSIT'] or amount > app.config['MAX_DEPOSIT']:
            flash(f'Amount must be between {format_ugx(app.config["MIN_DEPOSIT"])} and {format_ugx(app.config["MAX_DEPOSIT"])}.', 'error')
            return redirect(url_for('deposit'))
        if method not in [m['id'] for m in app.config['PAYMENT_METHODS']]:
            flash('Invalid payment method.', 'error')
            return redirect(url_for('deposit'))
        if not reference_id:
            flash('Please enter a simulated transaction reference.', 'error')
            return redirect(url_for('deposit'))
        
        d = Deposit(user_id=user.id, amount=amount, method=method, reference_id=reference_id)
        db.session.add(d)
        db.session.commit()
        flash('Deposit request submitted. Awaiting admin review (simulation).', 'success')
        return redirect(url_for('wallet'))
    return render_template('deposit.html', user=user, methods=app.config['PAYMENT_METHODS'])


@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    user = current_user()
    ensure_wallet(user)
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            flash('Invalid amount.', 'error')
            return redirect(url_for('withdraw'))
        method = request.form.get('method')
        mobile = request.form.get('mobile_number', '').strip()
        
        if amount < app.config['MIN_WITHDRAWAL']:
            flash(f'Minimum withdrawal is {format_ugx(app.config["MIN_WITHDRAWAL"])}.', 'error')
            return redirect(url_for('withdraw'))
        if amount > user.wallet.balance:
            flash('Insufficient balance.', 'error')
            return redirect(url_for('withdraw'))
        if method not in [m['id'] for m in app.config['PAYMENT_METHODS']]:
            flash('Invalid method.', 'error')
            return redirect(url_for('withdraw'))
        if len(mobile) < 10:
            flash('Please enter a valid mobile number.', 'error')
            return redirect(url_for('withdraw'))
        
        fee = amount * (app.config['WITHDRAWAL_FEE_PERCENT'] / 100)
        net = amount - fee
        w = Withdrawal(user_id=user.id, amount=amount, method=method,
                       mobile_number=mobile, fee=fee, net_amount=net)
        db.session.add(w)
        # Reserve funds
        user.wallet.balance -= amount
        tx = Transaction(
            user_id=user.id, type='withdrawal', amount=amount,
            balance_before=amount + user.wallet.balance,
            balance_after=user.wallet.balance,
            description=f'Withdrawal request to {mobile}',
            status='pending', reference=generate_reference('WDR')
        )
        db.session.add(tx)
        db.session.commit()
        flash('Withdrawal request submitted. Awaiting admin review (simulation).', 'success')
        return redirect(url_for('wallet'))
    return render_template('withdraw.html', user=user, methods=app.config['PAYMENT_METHODS'])


@app.route('/transactions')
@login_required
def transactions():
    user = current_user()
    txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).all()
    return render_template('transactions.html', transactions=txs)


# ---------------------------
# Referrals
# ---------------------------

@app.route('/referrals')
@login_required
def referrals():
    user = current_user()
    ensure_wallet(user)
    given = Referral.query.filter_by(referrer_id=user.id).all()
    total_earned = sum(r.reward_amount for r in given)
    referral_url = request.host_url + f'?ref={user.referral_code}'
    return render_template('referrals.html', user=user, referrals=given,
                           total_earned=total_earned, referral_url=referral_url)


# ---------------------------
# Raffle
# ---------------------------

@app.route('/raffle')
@login_required
def raffle():
    user = current_user()
    ensure_wallet(user)
    active = Raffle.query.filter_by(is_closed=False).order_by(Raffle.closes_at.asc()).first()
    past = Raffle.query.filter_by(is_closed=True).order_by(Raffle.closes_at.desc()).limit(5).all()
    my_entries = 0
    if active:
        my_entries = sum(e.entries for e in RaffleEntry.query.filter_by(raffle_id=active.id, user_id=user.id).all())
    return render_template('raffle.html', user=user, active=active, past=past, my_entries=my_entries)


@app.route('/raffle/enter', methods=['POST'])
@login_required
def enter_raffle():
    user = current_user()
    ensure_wallet(user)
    reason = request.form.get('reason', 'daily_login')
    entries = app.config['RAFFLE_ENTRY_RULES'].get(reason, 1)
    active = Raffle.query.filter_by(is_closed=False).order_by(Raffle.closes_at.asc()).first()
    if not active:
        flash('No active raffle at the moment.', 'info')
        return redirect(url_for('raffle'))
    
    existing = RaffleEntry.query.filter_by(raffle_id=active.id, user_id=user.id, reason=reason).first()
    if existing:
        flash('You have already claimed entries for this action.', 'info')
        return redirect(url_for('raffle'))
    
    e = RaffleEntry(raffle_id=active.id, user_id=user.id, entries=entries, reason=reason)
    db.session.add(e)
    db.session.commit()
    flash(f'+{entries} simulated raffle entries added.', 'success')
    return redirect(url_for('raffle'))


# ---------------------------
# Profile
# ---------------------------

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    ensure_wallet(user)
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name).strip()
        user.phone = request.form.get('phone', user.phone).strip()
        user.profile_completed = True
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)


# ---------------------------
# Scam Awareness
# ---------------------------

@app.route('/scam-awareness')
def scam_awareness():
    recent = ScamReport.query.filter_by(status='resolved').order_by(ScamReport.created_at.desc()).limit(10).all()
    return render_template('scam_report.html', recent=recent, submitted=False)


@app.route('/scam-awareness/report', methods=['POST'])
def submit_scam_report():
    data = request.form
    if not data.get('scammer_name') or not data.get('description'):
        flash('Scammer name and description are required.', 'error')
        return redirect(url_for('scam_awareness'))
    
    report = ScamReport(
        reporter_name=data.get('reporter_name', '').strip() or None,
        reporter_contact=data.get('reporter_contact', '').strip() or None,
        scammer_name=data.get('scammer_name', '').strip(),
        scammer_contact=data.get('scammer_contact', '').strip() or None,
        platform=data.get('platform', '').strip() or None,
        method=data.get('method', '').strip() or None,
        amount_involved=float(data['amount_involved']) if data.get('amount_involved') else None,
        description=data.get('description', '').strip(),
        evidence=data.get('evidence', '').strip() or None,
    )
    db.session.add(report)
    db.session.commit()
    flash('Thank you. Your report has been received. Our team will review it.', 'success')
    return redirect(url_for('scam_awareness'))


# ---------------------------
# Admin
# ---------------------------

@app.route('/admin')
@admin_required
def admin_dashboard():
    users = User.query.filter(User.is_admin == False).order_by(User.created_at.desc()).all()
    pending_deposits = Deposit.query.filter_by(status='pending').order_by(Deposit.created_at.asc()).all()
    pending_withdrawals = Withdrawal.query.filter_by(status='pending').order_by(Withdrawal.created_at.asc()).all()
    reports = ScamReport.query.filter_by(status='new').order_by(ScamReport.created_at.desc()).limit(10).all()
    return render_template('admin.html', users=users, pending_deposits=pending_deposits,
                           pending_withdrawals=pending_withdrawals, reports=reports,
                           tab='overview')


@app.route('/admin/deposits')
@admin_required
def admin_deposits():
    deposits = Deposit.query.order_by(Deposit.created_at.desc()).all()
    return render_template('admin.html', deposits=deposits, tab='deposits')


@app.route('/admin/deposits/<int:dep_id>/<action>', methods=['POST'])
@admin_required
def process_deposit(dep_id, action):
    d = Deposit.query.get_or_404(dep_id)
    if d.status != 'pending':
        flash('Already processed.', 'info')
        return redirect(url_for('admin_deposits'))
    user = User.query.get(d.user_id)
    ensure_wallet(user)
    
    if action == 'approve':
        d.status = 'approved'
        d.processed_at = datetime.utcnow()
        record_transaction(user, 'deposit', d.amount, f'Deposit via {d.method} (ref {d.reference_id})')
        # Promotional simulation bonus
        record_transaction(user, 'bonus', app.config['DEPOSIT_BONUS'],
                           f'Promotional simulation bonus — not a guaranteed return')
        flash(f'Deposit approved. {format_ugx(app.config["DEPOSIT_BONUS"])} promotional bonus credited.', 'success')
    elif action == 'reject':
