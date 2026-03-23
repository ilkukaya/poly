"""
PORTFOLIO MANAGER
Paper trading portfolio with full tracking.
"""

import json
import os
from datetime import datetime, timezone
from config import (
    INITIAL_CAPITAL, PORTFOLIO_FILE, TRADE_LOG_FILE,
    WINNING_FEE_PCT, SLIPPAGE_PCT, get_phase, STOP_LOSS_PCT
)

def _now():
    return datetime.now(timezone.utc).isoformat()

def _load_json(filepath, default=None):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default if default is not None else {}

def _save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)


class Portfolio:
    def __init__(self):
        self.state = _load_json(PORTFOLIO_FILE, self._default_state())
        self.trades = _load_json(TRADE_LOG_FILE, [])
    
    def _default_state(self):
        return {
            "created_at": _now(),
            "initial_capital": INITIAL_CAPITAL,
            "cash": INITIAL_CAPITAL,
            "positions": {},       # market_id -> position details
            "closed_markets": [],  # list of market_ids we already traded (no re-entry)
            "total_realized_pnl": 0.0,
            "total_fees_paid": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "peak_equity": INITIAL_CAPITAL,
            "max_drawdown": 0.0,
            "daily_pnl": {},       # date -> pnl
            "last_updated": _now(),
        }
    
    def save(self):
        self.state["last_updated"] = _now()
        _save_json(PORTFOLIO_FILE, self.state)
        _save_json(TRADE_LOG_FILE, self.trades)
    
    @property
    def cash(self):
        return self.state["cash"]
    
    @property
    def positions(self):
        return self.state["positions"]
    
    def equity(self, current_prices=None):
        """Total portfolio value = cash + mark-to-market positions."""
        total = self.state["cash"]
        for mid, pos in self.state["positions"].items():
            if current_prices and mid in current_prices:
                price = current_prices[mid]
            else:
                price = pos.get("current_price", pos["entry_price"])
            total += pos["shares"] * price
        return total
    
    def open_position(self, market_id, question, side, entry_price, 
                      amount_usd, shares, category="other", strategy="manual",
                      edge=0.0, confidence=0.0, notes=""):
        """Open a new paper position."""
        
        # PREVENT RE-ENTRY: skip markets we already traded
        closed_list = self.state.get("closed_markets", [])
        if market_id in closed_list:
            print(f"[SKIP] Already traded {question[:40]} — no re-entry")
            return False
        
        # PREVENT DUPLICATE: skip if already have this position open
        if market_id in self.state["positions"]:
            print(f"[SKIP] Already have open position in {question[:40]}")
            return False
        
        # Apply slippage to entry
        if side == "YES":
            actual_entry = min(entry_price * (1 + SLIPPAGE_PCT), 0.99)
        else:
            actual_entry = min(entry_price * (1 + SLIPPAGE_PCT), 0.99)
        
        actual_shares = amount_usd / actual_entry
        actual_cost = amount_usd
        
        if actual_cost > self.state["cash"]:
            print(f"[PORTFOLIO] Insufficient funds. Need ${actual_cost:.2f}, have ${self.state['cash']:.2f}")
            return False
        
        # Deduct cash
        self.state["cash"] -= actual_cost
        
        # Record position
        position = {
            "market_id": market_id,
            "question": question,
            "side": side,
            "entry_price": actual_entry,
            "current_price": actual_entry,
            "shares": actual_shares,
            "cost_basis": actual_cost,
            "category": category,
            "strategy": strategy,
            "edge_at_entry": edge,
            "confidence": confidence,
            "notes": notes,
            "opened_at": _now(),
            "stop_loss": actual_entry * (1 - STOP_LOSS_PCT),
            "status": "open",
        }
        
        self.state["positions"][market_id] = position
        self.state["total_trades"] += 1
        
        # Log trade
        trade = {
            "action": "OPEN",
            "market_id": market_id,
            "question": question,
            "side": side,
            "price": actual_entry,
            "shares": actual_shares,
            "amount_usd": actual_cost,
            "strategy": strategy,
            "edge": edge,
            "category": category,
            "timestamp": _now(),
            "cash_after": self.state["cash"],
        }
        self.trades.append(trade)
        
        print(f"[TRADE] OPEN {side} | {question[:60]}")
        print(f"        Price: {actual_entry:.3f} | Shares: {actual_shares:.1f} | Cost: ${actual_cost:.2f}")
        print(f"        Strategy: {strategy} | Edge: {edge:.1%} | Cash left: ${self.state['cash']:.2f}")
        
        self.save()
        return True
    
    def close_position(self, market_id, exit_price, reason="manual"):
        """Close a position and realize P&L."""
        if market_id not in self.state["positions"]:
            print(f"[PORTFOLIO] Position {market_id} not found")
            return False
        
        pos = self.state["positions"][market_id]
        
        # Apply slippage to exit
        if reason == "resolved_win":
            actual_exit = 1.0  # Full payout
        elif reason == "resolved_loss":
            actual_exit = 0.0  # Total loss
        else:
            actual_exit = exit_price * (1 - SLIPPAGE_PCT)
        
        # Calculate P&L
        proceeds = pos["shares"] * actual_exit
        
        # Apply winning fee if profitable
        pnl = proceeds - pos["cost_basis"]
        if pnl > 0 and reason == "resolved_win":
            fee = pnl * WINNING_FEE_PCT
            proceeds -= fee
            pnl -= fee
            self.state["total_fees_paid"] += fee
        
        # Update cash
        self.state["cash"] += proceeds
        
        # Update stats
        self.state["total_realized_pnl"] += pnl
        if pnl > 0:
            self.state["winning_trades"] += 1
        else:
            self.state["losing_trades"] += 1
        
        # Track daily P&L
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.state["daily_pnl"][today] = self.state["daily_pnl"].get(today, 0) + pnl
        
        # Update peak equity and drawdown
        eq = self.equity()
        if eq > self.state["peak_equity"]:
            self.state["peak_equity"] = eq
        drawdown = (self.state["peak_equity"] - eq) / self.state["peak_equity"]
        if drawdown > self.state["max_drawdown"]:
            self.state["max_drawdown"] = drawdown
        
        # Log trade
        trade = {
            "action": "CLOSE",
            "market_id": market_id,
            "question": pos["question"],
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": actual_exit,
            "shares": pos["shares"],
            "cost_basis": pos["cost_basis"],
            "proceeds": proceeds,
            "pnl": pnl,
            "pnl_pct": pnl / pos["cost_basis"] * 100 if pos["cost_basis"] > 0 else 0,
            "reason": reason,
            "strategy": pos["strategy"],
            "category": pos["category"],
            "hold_time": pos["opened_at"],
            "timestamp": _now(),
            "cash_after": self.state["cash"],
        }
        self.trades.append(trade)
        
        print(f"[TRADE] CLOSE {pos['side']} | {pos['question'][:60]}")
        print(f"        Entry: {pos['entry_price']:.3f} → Exit: {actual_exit:.3f}")
        print(f"        P&L: ${pnl:+.2f} ({pnl/pos['cost_basis']*100:+.1f}%) | Reason: {reason}")
        print(f"        Cash: ${self.state['cash']:.2f}")
        
        # Remove position and add to closed list
        del self.state["positions"][market_id]
        if "closed_markets" not in self.state:
            self.state["closed_markets"] = []
        if market_id not in self.state["closed_markets"]:
            self.state["closed_markets"].append(market_id)
            # Keep only last 200 to prevent unbounded growth
            if len(self.state["closed_markets"]) > 200:
                self.state["closed_markets"] = self.state["closed_markets"][-200:]
        
        self.save()
        return True
    
    def update_position_price(self, market_id, current_price):
        """Update mark-to-market price for a position."""
        if market_id in self.state["positions"]:
            self.state["positions"][market_id]["current_price"] = current_price
    
    def check_stop_losses(self, current_prices):
        """Check all positions for stop loss triggers."""
        to_close = []
        for mid, pos in self.state["positions"].items():
            if mid in current_prices:
                current = current_prices[mid]
                self.update_position_price(mid, current)
                
                if current <= pos["stop_loss"]:
                    to_close.append((mid, current))
        
        for mid, price in to_close:
            print(f"[STOP LOSS] Triggered for {mid}")
            self.close_position(mid, price, reason="stop_loss")
    
    def get_position_sizing(self, edge, win_prob):
        """Calculate position size using fractional Kelly criterion.
        
        For prediction markets:
        - We buy shares at price `p` (entry_price)
        - If correct, each share pays $1
        - edge = our estimated prob - market price
        - win_prob = our estimated probability of the outcome
        """
        phase = get_phase(self.equity())
        
        # Cap win_prob to sensible range
        win_prob = max(0.01, min(win_prob, 0.99))
        
        # Simplified Kelly for binary markets:
        # f = edge / (1 - entry_price)
        # where entry_price ≈ win_prob - edge (the market price)
        # This simplifies to: f = edge / odds_against
        
        entry_price = max(win_prob - edge, 0.01)
        entry_price = min(entry_price, 0.99)
        
        # Potential profit per dollar risked
        profit_ratio = (1.0 - entry_price) / entry_price
        loss_ratio = 1.0  # Can lose entire stake
        
        # Kelly: f = (p * profit_ratio - q) / profit_ratio
        q = 1 - win_prob
        kelly = (win_prob * profit_ratio - q) / profit_ratio
        
        if kelly <= 0:
            return 0
        
        # Apply fraction
        fraction = phase["kelly_fraction"]
        sized_kelly = kelly * fraction
        
        # Cap at max position %
        max_amount = self.equity() * phase["max_position_pct"]
        kelly_amount = self.equity() * sized_kelly
        
        amount = min(kelly_amount, max_amount)
        amount = max(amount, 0)  # No negative
        
        # Don't exceed available cash
        amount = min(amount, self.state["cash"] * 0.90)  # Keep 10% reserve
        
        # Minimum position size
        if amount < 1.0:
            return 0
        
        return round(amount, 2)
    
    def summary(self, current_prices=None):
        """Print portfolio summary."""
        eq = self.equity(current_prices)
        phase = get_phase(eq)
        
        print("=" * 70)
        print("POLYMARKET PAPER TRADING - PORTFOLIO SUMMARY")
        print("=" * 70)
        print(f"Phase: {phase['phase']} - {phase['name']} ({phase['description'][:50]})")
        print(f"Cash:           ${self.state['cash']:>10.2f}")
        print(f"Positions:      {len(self.state['positions']):>10d}")
        
        # Show positions
        unrealized = 0
        if self.state["positions"]:
            print("\n  Open Positions:")
            for mid, pos in self.state["positions"].items():
                curr = pos.get("current_price", pos["entry_price"])
                if current_prices and mid in current_prices:
                    curr = current_prices[mid]
                pos_value = pos["shares"] * curr
                pos_pnl = pos_value - pos["cost_basis"]
                unrealized += pos_pnl
                pnl_pct = pos_pnl / pos["cost_basis"] * 100 if pos["cost_basis"] > 0 else 0
                emoji = "🟢" if pos_pnl >= 0 else "🔴"
                print(f"  {emoji} {pos['question'][:50]}")
                print(f"     {pos['side']} @ {pos['entry_price']:.3f} → {curr:.3f} | "
                      f"${pos_value:.2f} ({pnl_pct:+.1f}%) | {pos['strategy']}")
        
        print(f"\nEquity:         ${eq:>10.2f}")
        print(f"Unrealized P&L: ${unrealized:>+10.2f}")
        print(f"Realized P&L:   ${self.state['total_realized_pnl']:>+10.2f}")
        print(f"Total P&L:      ${unrealized + self.state['total_realized_pnl']:>+10.2f}")
        print(f"Return:         {(eq / INITIAL_CAPITAL - 1) * 100:>+9.1f}%")
        print(f"Fees Paid:      ${self.state['total_fees_paid']:>10.2f}")
        print(f"Win Rate:       ", end="")
        total = self.state["winning_trades"] + self.state["losing_trades"]
        if total > 0:
            print(f"{self.state['winning_trades']}/{total} ({self.state['winning_trades']/total*100:.0f}%)")
        else:
            print("N/A (no closed trades)")
        print(f"Max Drawdown:   {self.state['max_drawdown']*100:>9.1f}%")
        print(f"Peak Equity:    ${self.state['peak_equity']:>10.2f}")
        print("=" * 70)
        
        return {
            "equity": eq,
            "cash": self.state["cash"],
            "positions_count": len(self.state["positions"]),
            "unrealized_pnl": unrealized,
            "realized_pnl": self.state["total_realized_pnl"],
            "return_pct": (eq / INITIAL_CAPITAL - 1) * 100,
        }
