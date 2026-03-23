"""
MARKET SCANNER & TRADE EXECUTOR
Main entry point: scans markets, finds signals, executes paper trades.
"""

import json
import sys
from datetime import datetime, timezone
from api import fetch_active_markets, fetch_market_by_id
from strategies import run_all_strategies, filter_signals
from portfolio import Portfolio
from config import SCAN_LOG_FILE, get_phase


def run_scan(execute=True, verbose=True):
    """Full market scan + optional trade execution."""
    
    print(f"\n{'='*70}")
    print(f"POLYMARKET SCANNER - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*70}")
    
    # 1. Load portfolio
    portfolio = Portfolio()
    eq = portfolio.equity()
    phase = get_phase(eq)
    print(f"\nPhase {phase['phase']}: {phase['name']} | Equity: ${eq:.2f} | Cash: ${portfolio.cash:.2f}")
    print(f"Open positions: {len(portfolio.positions)}/{phase['max_open']}")
    
    # 2. Fetch markets
    print(f"\nFetching active markets...")
    markets = fetch_active_markets(limit=500, min_volume_24h=500, min_liquidity=2000)
    print(f"Found {len(markets)} tradeable markets")
    
    # Category breakdown
    from collections import Counter
    cats = Counter(m['category'] for m in markets)
    print(f"Categories: {dict(cats.most_common(10))}")
    
    # 3. Update existing position prices
    market_prices = {}
    for m in markets:
        mid = str(m['id'])
        market_prices[mid] = m['yes_price']  # Will need to flip for NO positions
    
    # Update positions with current prices
    for mid, pos in portfolio.positions.items():
        if mid in market_prices:
            if pos['side'] == 'YES':
                portfolio.update_position_price(mid, market_prices[mid])
            else:
                portfolio.update_position_price(mid, 1 - market_prices[mid])
    
    # 4. Check stop losses
    portfolio.check_stop_losses(market_prices)
    
    # 5. Run strategies
    print(f"\nRunning strategies...")
    all_signals = run_all_strategies(markets)
    print(f"Raw signals found: {len(all_signals)}")
    
    # 6. Filter & rank
    actionable = filter_signals(all_signals, portfolio)
    print(f"Actionable signals: {len(actionable)}")
    
    # 7. Display top signals
    if verbose and actionable:
        print(f"\n{'─'*70}")
        print("TOP SIGNALS:")
        print(f"{'─'*70}")
        for i, s in enumerate(actionable[:15]):
            print(f"\n  #{i+1} [{s.strategy}] {s.market['question'][:60]}")
            print(f"      {s.side} @ {s.entry_price:.3f} | Edge: {s.edge:.1%} | "
                  f"Conf: {s.confidence:.0%} | Score: {s.score:.4f}")
            print(f"      Category: {s.market.get('category','?')} | "
                  f"Liq: ${s.market.get('liquidity',0):,.0f} | "
                  f"Vol24h: ${s.market.get('volume_24h',0):,.0f}")
            if hasattr(s, 'suggested_size'):
                print(f"      Suggested size: ${s.suggested_size:.2f}")
            print(f"      {s.notes[:80]}")
    
    # 8. Execute trades if enabled
    trades_made = []
    if execute and actionable:
        print(f"\n{'─'*70}")
        print("EXECUTING TRADES:")
        print(f"{'─'*70}")
        
        for s in actionable:
            size = getattr(s, 'suggested_size', 0)
            if size < 1.0:
                continue
            
            # Check we still have cash
            if portfolio.cash < size:
                print(f"\n  [SKIP] Insufficient cash for {s.market['question'][:40]}")
                continue
            
            # Calculate shares
            shares = size / s.entry_price
            
            success = portfolio.open_position(
                market_id=str(s.market['id']),
                question=s.market['question'],
                side=s.side,
                entry_price=s.entry_price,
                amount_usd=size,
                shares=shares,
                category=s.market.get('category', 'other'),
                strategy=s.strategy,
                edge=s.edge,
                confidence=s.confidence,
                notes=s.notes,
            )
            
            if success:
                trades_made.append(s.to_dict())
    
    # 9. Save scan log
    scan_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "markets_scanned": len(markets),
        "signals_found": len(all_signals),
        "actionable_signals": len(actionable),
        "trades_executed": len(trades_made),
        "equity_before": eq,
        "equity_after": portfolio.equity(),
        "cash_after": portfolio.cash,
    }
    
    # Append to scan log
    try:
        with open(SCAN_LOG_FILE, 'r') as f:
            scan_log = json.load(f)
    except:
        scan_log = []
    scan_log.append(scan_entry)
    with open(SCAN_LOG_FILE, 'w') as f:
        json.dump(scan_log, f, indent=2)
    
    # 10. Final summary
    portfolio.summary()
    
    return {
        "signals": [s.to_dict() for s in actionable],
        "trades": trades_made,
        "equity": portfolio.equity(),
        "scan_entry": scan_entry,
    }


def check_resolutions():
    """
    SMART POSITION MANAGER
    Runs every scan cycle. Handles:
    1. Market resolved → close at $1 or $0
    2. Take profit → price moved enough, lock in gains
    3. Market about to expire + in profit → exit early
    4. Stop loss → cut losses (but NOT for penny picks near resolution)
    """
    portfolio = Portfolio()
    
    if not portfolio.positions:
        print("[CHECK] No open positions.")
        return []
    
    markets = fetch_active_markets(limit=500, min_volume_24h=0, min_liquidity=0)
    
    # Build lookup by ID
    market_lookup = {}
    for m in markets:
        market_lookup[str(m['id'])] = m
    
    actions_taken = []
    
    for mid, pos in list(portfolio.positions.items()):
        m = market_lookup.get(mid)
        question = pos['question'][:50]
        side = pos['side']
        entry = pos['entry_price']
        cost = pos['cost_basis']
        strategy = pos.get('strategy', '')
        
        # ─── CASE 1: Market not in active list → check if resolved ───
        if m is None:
            print(f"[CHECK] {question} — not in active list, checking API directly...")
            
            # Try direct API lookup to get actual resolved outcome
            resolved_market = fetch_market_by_id(mid)
            
            if resolved_market and resolved_market.get('closed'):
                winner = resolved_market.get('resolved_winner')
                if winner == side:
                    print(f"  → CONFIRMED WIN: {side} won!")
                    portfolio.close_position(mid, 1.0, reason="resolved_win")
                    actions_taken.append(("resolved_win", mid))
                elif winner is not None:
                    print(f"  → CONFIRMED LOSS: {winner} won, we had {side}")
                    portfolio.close_position(mid, 0.01, reason="resolved_loss")
                    actions_taken.append(("resolved_loss", mid))
                else:
                    # Closed but can't determine winner from prices
                    print(f"  → Closed but outcome unclear, assuming WIN for high-entry penny pick")
                    if entry > 0.75:
                        portfolio.close_position(mid, 1.0, reason="resolved_win")
                        actions_taken.append(("resolved_win", mid))
                    else:
                        portfolio.close_position(mid, entry, reason="resolved_unknown")
                        actions_taken.append(("resolved_unknown", mid))
            elif resolved_market and not resolved_market.get('closed'):
                # Market exists but not closed — might have low liquidity
                # Don't close, just log and skip
                print(f"  → Market still open but not in active filter. Keeping position.")
            else:
                # Can't find market at all — very rare
                print(f"  → Market not found anywhere. Assuming WIN for penny pick (entry={entry:.3f})")
                if entry > 0.75:
                    portfolio.close_position(mid, 1.0, reason="resolved_win")
                    actions_taken.append(("resolved_win", mid))
                else:
                    portfolio.close_position(mid, entry, reason="resolved_unknown")
                    actions_taken.append(("resolved_unknown", mid))
            continue
        
        # Get current price for our side
        yes_p = m['yes_price']
        no_p = m['no_price']
        current = yes_p if side == "YES" else no_p
        
        # Update mark-to-market
        portfolio.update_position_price(mid, current)
        
        # ─── CASE 2: Price at extreme = RESOLVED ───
        if yes_p >= 0.98:
            if side == "YES":
                print(f"[WIN] {question} — YES resolved at {yes_p:.3f}")
                portfolio.close_position(mid, 1.0, reason="resolved_win")
            else:
                print(f"[LOSS] {question} — YES hit {yes_p:.3f}, we had NO")
                portfolio.close_position(mid, 0.01, reason="resolved_loss")
            actions_taken.append(("resolved", mid))
            continue
        
        if yes_p <= 0.02:
            if side == "NO":
                print(f"[WIN] {question} — NO resolved (YES at {yes_p:.3f})")
                portfolio.close_position(mid, 1.0, reason="resolved_win")
            else:
                print(f"[LOSS] {question} — YES dropped to {yes_p:.3f}, we had YES")
                portfolio.close_position(mid, 0.01, reason="resolved_loss")
            actions_taken.append(("resolved", mid))
            continue
        
        # ─── CASE 3: TAKE PROFIT ───
        unrealized_pnl_pct = (current - entry) / entry if entry > 0 else 0
        
        # If price > 96¢ and we're in profit, take it
        if current >= 0.96 and unrealized_pnl_pct > 0.02:
            print(f"[TAKE PROFIT] {question} — {entry:.3f} → {current:.3f} ({unrealized_pnl_pct:.1%})")
            portfolio.close_position(mid, current, reason="take_profit")
            actions_taken.append(("take_profit", mid))
            continue
        
        # If gain > 15%, take profit regardless
        if unrealized_pnl_pct >= 0.15:
            print(f"[TAKE PROFIT] {question} — {entry:.3f} → {current:.3f} ({unrealized_pnl_pct:.1%})")
            portfolio.close_position(mid, current, reason="take_profit")
            actions_taken.append(("take_profit", mid))
            continue
        
        # ─── CASE 4: STOP LOSS (but NOT for penny picks) ───
        # Penny picks are meant to be held to resolution
        # Only cut if price drops drastically (below 50% of entry)
        if strategy == "PENNY_PICK":
            # Only stop out if price drops below 50¢ (catastrophic reversal)
            if current < 0.50:
                print(f"[STOP LOSS] {question} — penny pick crashed to {current:.3f}")
                portfolio.close_position(mid, current, reason="stop_loss")
                actions_taken.append(("stop_loss", mid))
                continue
        else:
            # Non-penny-pick: cut at 35% loss
            if unrealized_pnl_pct <= -0.35:
                print(f"[CUT LOSS] {question} — {entry:.3f} → {current:.3f} ({unrealized_pnl_pct:.1%})")
                portfolio.close_position(mid, current, reason="cut_loss")
                actions_taken.append(("cut_loss", mid))
                continue
        
        # ─── CASE 5: TIME-BASED EXIT ───
        end_str = m.get('end_date', '')
        if end_str:
            try:
                from datetime import datetime, timezone
                if 'T' in end_str:
                    end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                else:
                    end_dt = datetime.strptime(end_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                hours_left = (end_dt - now).total_seconds() / 3600
                
                # Market expires in < 1 hour and we're in profit → exit
                if hours_left < 1 and unrealized_pnl_pct > 0.01:
                    print(f"[TIME EXIT] {question} — {hours_left:.1f}h left, profit {unrealized_pnl_pct:.1%}")
                    portfolio.close_position(mid, current, reason="time_exit_profit")
                    actions_taken.append(("time_exit", mid))
                    continue
            except:
                pass
    
    portfolio.save()
    
    if actions_taken:
        print(f"\n[CHECK] Actions taken: {len(actions_taken)}")
        for action, mid in actions_taken:
            print(f"  → {action}: {mid}")
    else:
        print(f"[CHECK] All {len(portfolio.positions)} positions stable.")
    
    return actions_taken


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    
    if mode == "scan":
        run_scan(execute=True, verbose=True)
    elif mode == "check":
        check_resolutions()
    elif mode == "status":
        p = Portfolio()
        p.summary()
    elif mode == "dry":
        run_scan(execute=False, verbose=True)
    else:
        print(f"Usage: python scanner.py [scan|check|status|dry]")
