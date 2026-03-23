"""
DASHBOARD EXPORT
Generates dashboard_data.json for the web dashboard.
Also can push to Google Sheets (optional).
"""

import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def export_dashboard():
    # Load data
    try:
        with open(os.path.join(BASE_DIR, "portfolio.json")) as f:
            portfolio = json.load(f)
    except:
        portfolio = {"cash": 30.0, "positions": {}, "total_realized_pnl": 0,
                     "winning_trades": 0, "losing_trades": 0, "daily_pnl": {},
                     "total_fees_paid": 0, "peak_equity": 30, "max_drawdown": 0,
                     "initial_capital": 30}
    
    try:
        with open(os.path.join(BASE_DIR, "trade_log.json")) as f:
            trades = json.load(f)
    except:
        trades = []
    
    try:
        with open(os.path.join(BASE_DIR, "scan_log.json")) as f:
            scans = json.load(f)
    except:
        scans = []
    
    # Calculate equity
    equity = portfolio["cash"]
    positions = []
    for mid, pos in portfolio.get("positions", {}).items():
        curr_price = pos.get("current_price", pos["entry_price"])
        pos_value = pos["shares"] * curr_price
        pnl = pos_value - pos["cost_basis"]
        pnl_pct = (pnl / pos["cost_basis"] * 100) if pos["cost_basis"] > 0 else 0
        equity += pos_value
        
        positions.append({
            "market_id": mid,
            "question": pos["question"],
            "side": pos["side"],
            "entry_price": round(pos["entry_price"], 4),
            "current_price": round(curr_price, 4),
            "cost": round(pos["cost_basis"], 2),
            "value": round(pos_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 1),
            "strategy": pos["strategy"],
            "category": pos.get("category", "other"),
            "opened_at": pos["opened_at"],
        })
    
    # Closed trades summary
    closed = [t for t in trades if t.get("action") == "CLOSE"]
    
    # Equity curve from scan log
    equity_curve = []
    for s in scans:
        equity_curve.append({
            "timestamp": s["timestamp"],
            "equity": round(s.get("equity_after", s.get("equity_before", 30)), 2),
        })
    # Add current
    equity_curve.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "equity": round(equity, 2),
    })
    
    # Strategy performance
    strategy_stats = {}
    for t in closed:
        strat = t.get("strategy", "unknown")
        if strat not in strategy_stats:
            strategy_stats[strat] = {"wins": 0, "losses": 0, "total_pnl": 0, "trades": 0}
        strategy_stats[strat]["trades"] += 1
        strategy_stats[strat]["total_pnl"] += t.get("pnl", 0)
        if t.get("pnl", 0) > 0:
            strategy_stats[strat]["wins"] += 1
        else:
            strategy_stats[strat]["losses"] += 1
    
    # Category breakdown
    category_stats = {}
    for t in closed:
        cat = t.get("category", "other")
        if cat not in category_stats:
            category_stats[cat] = {"wins": 0, "losses": 0, "total_pnl": 0}
        category_stats[cat]["total_pnl"] += t.get("pnl", 0)
        if t.get("pnl", 0) > 0:
            category_stats[cat]["wins"] += 1
        else:
            category_stats[cat]["losses"] += 1
    
    # Build dashboard data
    dashboard = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "equity": round(equity, 2),
            "cash": round(portfolio["cash"], 2),
            "initial_capital": portfolio.get("initial_capital", 30),
            "total_return_pct": round((equity / portfolio.get("initial_capital", 30) - 1) * 100, 2),
            "realized_pnl": round(portfolio.get("total_realized_pnl", 0), 2),
            "unrealized_pnl": round(equity - portfolio["cash"] - sum(p["cost"] for p in positions), 2),
            "total_trades": len(trades),
            "winning_trades": portfolio.get("winning_trades", 0),
            "losing_trades": portfolio.get("losing_trades", 0),
            "win_rate": round(portfolio["winning_trades"] / max(portfolio["winning_trades"] + portfolio["losing_trades"], 1) * 100, 1),
            "fees_paid": round(portfolio.get("total_fees_paid", 0), 2),
            "peak_equity": round(portfolio.get("peak_equity", 30), 2),
            "max_drawdown_pct": round(portfolio.get("max_drawdown", 0) * 100, 2),
            "open_positions": len(positions),
            "days_active": max((datetime.now(timezone.utc) - datetime.fromisoformat(portfolio.get("created_at", datetime.now(timezone.utc).isoformat()))).days, 1),
        },
        "positions": positions,
        "equity_curve": equity_curve,
        "recent_trades": trades[-20:],  # Last 20 trades
        "strategy_stats": strategy_stats,
        "category_stats": category_stats,
        "daily_pnl": portfolio.get("daily_pnl", {}),
    }
    
    # Save
    output_path = os.path.join(BASE_DIR, "dashboard_data.json")
    with open(output_path, "w") as f:
        json.dump(dashboard, f, indent=2, default=str)
    
    print(f"[DASHBOARD] Exported to {output_path}")
    print(f"[DASHBOARD] Equity: ${equity:.2f} | Return: {dashboard['summary']['total_return_pct']:+.1f}%")
    
    return dashboard


if __name__ == "__main__":
    export_dashboard()
