import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'cffa-dev-secret-change-me-in-production')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@cashflowfuture.ai')
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Simulation rules (all values are UGX, purely demonstrative)
    DEPOSIT_BONUS = 3000          # Promotional simulation bonus per approved deposit
    REFERRAL_REWARD = 3000        # Simulation reward per qualifying referral
    WITHDRAWAL_FEE_PERCENT = 2.0  # Simulated withdrawal fee %
    MIN_DEPOSIT = 5000
    MAX_DEPOSIT = 5000000
    MIN_WITHDRAWAL = 10000
    
    # Machine tiers — centralised so they can change without code edits
    MACHINES = [
        {
            "id": "A1",
            "name": "AI Compute Node A1",
            "price": 25000,
            "simulation_target": 250000,
            "duration_days": 60,
            "description": "Entry-level simulated AI inference node. Ideal for first-time explorers of digital infrastructure concepts.",
            "icon": "cpu",
            "tier": "Starter"
        },
        {
            "id": "A2",
            "name": "AI Compute Node A2",
            "price": 50000,
            "simulation_target": 500000,
            "duration_days": 60,
            "description": "Mid-tier simulated node with enhanced throughput modelling. Demonstrates scaling dynamics.",
            "icon": "server",
            "tier": "Growth"
        },
        {
            "id": "A3",
            "name": "AI Compute Node A3",
            "price": 100000,
            "simulation_target": 1000000,
            "duration_days": 60,
            "description": "Premium simulated infrastructure tier. Models high-performance compute scenarios.",
            "icon": "chip",
            "tier": "Premium"
        },
    ]
    
    # Raffle configuration
    RAFFLE_DEFAULT_PRIZE = 100000
    RAFFLE_DEFAULT_DURATION_DAYS = 7
    
    # Raffle entry rewards (action -> entries)
    RAFFLE_ENTRY_RULES = {
        "daily_login": 1,
        "buy_machine": 3,
        "invite_friend": 2,
        "complete_profile": 1,
    }
    
    # Supported simulated payment methods
    PAYMENT_METHODS = [
        {"id": "mtn", "name": "MTN Mobile Money", "simulated": True},
        {"id": "airtel", "name": "Airtel Money", "simulated": True},
  ]
