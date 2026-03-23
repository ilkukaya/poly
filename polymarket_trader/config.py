"""
POLYMARKET PAPER TRADING SYSTEM - CONFIG
=========================================
Start: March 23, 2026
Initial Capital: $30.00 USDC
Target: Grow to $250-600+ by April 30, 2026
Strategy: Multi-category, disciplined risk management
"""

import os
from datetime import datetime

# === CAPITAL & RISK ===
INITIAL_CAPITAL = 30.00
MAX_POSITION_PCT = 0.15          # Max 15% of bankroll per position
MIN_POSITION_SIZE = 1.00         # Polymarket min order ~$1-5
MAX_OPEN_POSITIONS = 8           # Max concurrent positions
KELLY_FRACTION = 0.25            # Quarter-Kelly for safety (start conservative)
MAX_DAILY_LOSS_PCT = 0.20        # Stop trading if down 20% in a day
STOP_LOSS_PCT = 0.50             # Cut position if down 50% from entry

# === EDGE THRESHOLDS ===
MIN_EDGE_PCT = 0.05              # Minimum 5% edge to enter
HIGH_CONFIDENCE_EDGE = 0.12      # 12%+ edge = higher conviction
MIN_LIQUIDITY = 5000             # Don't enter markets with < $5k liquidity

# === COMMISSION / FEES ===
# Polymarket: No trading fees on CLOB, but ~2% on winnings withdrawal
WINNING_FEE_PCT = 0.02           # 2% on net profit when redeeming
SLIPPAGE_PCT = 0.005             # Estimated 0.5% slippage on entry/exit

# === CATEGORIES TO TRADE ===
TRADEABLE_CATEGORIES = [
    "Sports", "Basketball", "NCAA", "NBA", "Soccer", "NHL", "Hockey",
    "MLS", "Football", "Baseball", "Esports", "Games",
    "Politics", "Elections", "World Elections", "Global Elections",
    "Geopolitics", "World", "Middle East",
    "Crypto", "Finance", "Economics",
    "Culture", "Entertainment", "Tech",
]

# === API ===
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# === FILE PATHS ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
TRADE_LOG_FILE = os.path.join(BASE_DIR, "trade_log.json")
SCAN_LOG_FILE = os.path.join(BASE_DIR, "scan_log.json")

# === PHASE MANAGEMENT ===
# Phase 1: $30-100  -> Quarter Kelly, max 15% per position, penny picking focus
# Phase 2: $100-500 -> Third Kelly, max 12% per position, diversified
# Phase 3: $500+    -> Half Kelly, max 10% per position, portfolio approach
def get_phase(bankroll):
    if bankroll < 100:
        return {
            "phase": 1,
            "name": "Survival",
            "kelly_fraction": 0.25,
            "max_position_pct": 0.15,
            "max_open": 6,
            "description": "Conservative. Penny picking + high-conviction value bets only."
        }
    elif bankroll < 500:
        return {
            "phase": 2,
            "name": "Growth",
            "kelly_fraction": 0.33,
            "max_position_pct": 0.12,
            "max_open": 8,
            "description": "Diversified. Add momentum and calendar plays."
        }
    else:
        return {
            "phase": 3,
            "name": "Scale",
            "kelly_fraction": 0.50,
            "max_position_pct": 0.10,
            "max_open": 12,
            "description": "Full portfolio. All strategies active."
        }

START_DATE = "2026-03-23"
TARGET_DATE = "2026-04-30"
